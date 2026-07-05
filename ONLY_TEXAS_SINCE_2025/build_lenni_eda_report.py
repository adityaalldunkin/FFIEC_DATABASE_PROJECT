#!/usr/bin/env python3
"""
Join Texas FFIEC CSVs, run Lenni-aligned EDA, export joined tables + PDF report.

Reference: lenni_contenxt.txt (Lenni ICP: TX community banks $500M–$2B, CLO buyer,
portfolio CRE/C&I focus, ~360 TX community banks).

  python build_lenni_eda_report.py
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
ANALYSIS = ROOT / "analysis"
REPORT_PDF = ANALYSIS / "Lenni_Texas_Bank_EDA_Report.pdf"

ICP_ASSETS_MIN = 500_000_000  # USD — Lenni ICP floor ($500M)
ICP_ASSETS_MAX = 2_000_000_000  # USD — Lenni ICP ceiling ($2B)
LENNI_TARGET_BANKS = 360

# Loan-line items from texas_loans_summary.csv (values in USD)
LOAN_METRICS = {
    "RCON2122": "total_loans_gross",
    "RCON2145": "total_loans_net",
    "RCON2130": "allowance_loan_losses",
    "RCON1420": "farmland_loans",
    "RCON1460": "multifamily_re_loans",
    "RCONF158": "residential_construction",
    "RCONF159": "other_construction_ld",
    "RCONF160": "owner_occupied_nonfarm_re",
    "RCONF161": "other_nonfarm_nonres_re",
    "RCONF162": "commercial_re_loans",
    "RCON1545": "credit_card_plans",
    "RCON1583": "other_consumer_loans",
    "RCON1754": "lease_financing",
    "RCON5367": "past_due_30_89",
    "RCON5368": "past_due_90_plus",
    "RCON1403": "residential_1_4_family",
    "RCON1590": "ag_production_loans",
    "RCONS439": "residential_mortgage_exposures",
    "RCONB562": "consumer_other_051",
    "RCONB539": "consumer_revolving_051",
}

# Balance-sheet items from texas_xbrl_facts.csv (values in USD)
XBRL_METRICS = {
    "RCON2170": "total_assets",
    "RCON1766": "ci_loans",
    "RCON2122": "total_loans_gross_xbrl",
}

NAVY = "#203048"
SAGE = "#5C8A4B"
GOLD = "#C19A4B"


def _clean_city(s) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return str(s).strip()


def load_base() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inst = pd.read_csv(EXPORTS / "texas_institutions.csv", dtype={"id_rssd": int})
    inst["city"] = inst["city"].map(_clean_city)
    inst["filing_type"] = inst["filing_type"].astype(str).str.strip()

    filings = pd.read_csv(EXPORTS / "texas_filings.csv", dtype={"id_rssd": int})
    filings["city"] = filings["city"].map(_clean_city)

    loans = pd.read_csv(
        EXPORTS / "texas_loans_summary.csv",
        dtype={"id_rssd": int},
        usecols=[
            "id_rssd", "institution_name", "reporting_period", "mdrm_code",
            "item_name", "value_num", "mdrm_category",
        ],
    )
    loans["value_num"] = pd.to_numeric(loans["value_num"], errors="coerce")
    return inst, filings, loans


def pivot_loan_metrics(loans: pd.DataFrame) -> pd.DataFrame:
    sub = loans[loans["mdrm_code"].isin(LOAN_METRICS.keys())].copy()
    sub["metric"] = sub["mdrm_code"].map(LOAN_METRICS)
    return sub.pivot_table(
        index=["id_rssd", "reporting_period"],
        columns="metric",
        values="value_num",
        aggfunc="max",
    ).reset_index()


def load_xbrl_metrics() -> pd.DataFrame:
    """Chunk-read 2M+ fact rows; extract balance-sheet codes."""
    path = EXPORTS / "texas_xbrl_facts.csv"
    codes = set(XBRL_METRICS.keys())
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        path,
        chunksize=250_000,
        dtype={"id_rssd": int},
        usecols=["id_rssd", "reporting_period", "concept", "value_num"],
    ):
        chunk["mdrm_code"] = chunk["concept"].str.extract(
            r"(RCON[A-Z0-9]+|RCFD[A-Z0-9]+)", expand=False
        )
        sub = chunk[chunk["mdrm_code"].isin(codes)].copy()
        if sub.empty:
            continue
        sub["metric"] = sub["mdrm_code"].map(XBRL_METRICS)
        parts.append(
            sub.groupby(["id_rssd", "reporting_period", "metric"], as_index=False)["value_num"].max()
        )
    if not parts:
        return pd.DataFrame(columns=["id_rssd", "reporting_period"])
    long = pd.concat(parts, ignore_index=True)
    long = long.groupby(["id_rssd", "reporting_period", "metric"], as_index=False)["value_num"].max()
    wide = long.pivot_table(
        index=["id_rssd", "reporting_period"],
        columns="metric",
        values="value_num",
        aggfunc="max",
    ).reset_index()
    return wide


def merge_metrics(loans_wide: pd.DataFrame, xbrl_wide: pd.DataFrame) -> pd.DataFrame:
    m = loans_wide.merge(xbrl_wide, on=["id_rssd", "reporting_period"], how="outer")
    if "total_loans_gross" not in m.columns and "total_loans_gross_xbrl" in m.columns:
        m["total_loans_gross"] = m["total_loans_gross_xbrl"]
    elif "total_loans_gross" in m.columns and "total_loans_gross_xbrl" in m.columns:
        m["total_loans_gross"] = m["total_loans_gross"].fillna(m["total_loans_gross_xbrl"])
    return m


def build_joined(inst: pd.DataFrame, filings: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    m = inst.merge(
        filings[
            ["id_rssd", "reporting_period", "retrieved_at", "file_path", "sha256", "file_size_bytes"]
        ],
        on=["id_rssd", "reporting_period"],
        how="left",
    )
    m = m.merge(metrics, on=["id_rssd", "reporting_period"], how="left")

    ta = m.get("total_assets", pd.Series(dtype=float)).replace(0, np.nan)
    tl = m.get("total_loans_gross", pd.Series(dtype=float)).replace(0, np.nan)
    m["assets_usd"] = m.get("total_assets")
    m["loans_gross_usd"] = m.get("total_loans_gross")
    m["loan_to_asset_ratio"] = tl / ta
    m["allowance_ratio"] = m.get("allowance_loan_losses", pd.Series(dtype=float)) / tl

    cre_cols = [
        c for c in [
            "commercial_re_loans", "owner_occupied_nonfarm_re", "other_nonfarm_nonres_re",
            "multifamily_re_loans", "other_construction_ld", "residential_construction",
            "farmland_loans",
        ] if c in m.columns
    ]
    if cre_cols:
        m["cre_proxy_total"] = m[cre_cols].fillna(0).sum(axis=1)
        m["cre_to_loans"] = m["cre_proxy_total"] / tl

    m["ci_to_loans"] = m.get("ci_loans", pd.Series(dtype=float)) / tl
    m["consumer_to_loans"] = (
        m.get("credit_card_plans", pd.Series(0, index=m.index)).fillna(0)
        + m.get("other_consumer_loans", pd.Series(0, index=m.index)).fillna(0)
    ) / tl

    m["icp_fit"] = (
        (m["total_assets"] >= ICP_ASSETS_MIN) & (m["total_assets"] <= ICP_ASSETS_MAX)
    ).map({True: "ICP ($500M–$2B)", False: "Outside ICP"})
    m["form_size"] = m["filing_type"].map({
        "051": "FFIEC 031 (larger)",
        "041": "FFIEC 041 (community)",
    }).fillna("Other")
    return m


def latest_snapshot(master: pd.DataFrame) -> pd.DataFrame:
    periods = master["reporting_period"].unique()
    order = sorted(periods, key=lambda p: tuple(int(x) for x in p.split("/")))
    return master[master["reporting_period"] == order[-1]].copy()


def save_joined(master: pd.DataFrame, latest: pd.DataFrame) -> None:
    EXPORTS.mkdir(exist_ok=True)
    master.to_csv(EXPORTS / "texas_master_joined.csv", index=False)
    latest.to_csv(EXPORTS / "texas_bank_profiles_latest.csv", index=False)

    loans = pd.read_csv(EXPORTS / "texas_loans_summary.csv", dtype={"id_rssd": int})
    inst_cols = master[
        ["id_rssd", "reporting_period", "name", "city", "filing_type", "form_size", "icp_fit", "total_assets"]
    ].drop_duplicates()
    loans.merge(inst_cols, on=["id_rssd", "reporting_period"], how="left").to_csv(
        EXPORTS / "texas_loans_joined_long.csv", index=False
    )


def text_page(pdf: PdfPages, title: str, body: str) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor("white")
    wrapped = "\n".join(
        textwrap.fill(line, width=95) if line.strip() else "" for line in body.split("\n")
    )
    fig.text(0.05, 0.95, title, fontsize=14, fontweight="bold", va="top", color=NAVY)
    fig.text(0.05, 0.88, wrapped, fontsize=9, va="top", family="monospace")
    plt.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def run_eda(master: pd.DataFrame, latest: pd.DataFrame, pdf: PdfPages) -> list[str]:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    summaries: list[str] = []

    lat = latest.dropna(subset=["total_assets"]).copy()
    icp = lat[lat["icp_fit"] == "ICP ($500M–$2B)"]
    lat["assets_usd_m"] = lat["total_assets"] / 1_000_000

    summaries.append(
        f"Texas FFIEC universe: {lat['id_rssd'].nunique()} banks with asset data in latest period "
        f"({latest['reporting_period'].iloc[0]}). Master joined: {len(master):,} bank-quarter rows."
    )

    # 1 Asset distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(lat["assets_usd_m"].clip(0, 10000), bins=40, color=NAVY, edgecolor="white")
    ax.axvspan(500, 2000, alpha=0.2, color=SAGE, label="Lenni ICP $500M–$2B")
    ax.set_xlabel("Total assets ($ millions)")
    ax.set_ylabel("Number of banks")
    ax.set_title("1. Asset size distribution — Texas community banks (latest quarter)")
    ax.legend()
    fig.savefig(ANALYSIS / "01_asset_distribution.png", dpi=150, bbox_inches="tight")
    pdf.savefig(fig)
    plt.close(fig)

    # 2 ICP fit
    summaries.append(
        f"Lenni ICP ($500M–$2B): {len(icp)} banks ({100 * len(icp) / len(lat):.1f}%) of {len(lat)}. "
        f"Lenni context cites ~{LENNI_TARGET_BANKS} TX community banks."
    )
    fig, ax = plt.subplots(figsize=(7, 5))
    lat["icp_fit"].value_counts().plot(kind="bar", ax=ax, color=[SAGE, GOLD])
    ax.set_title("2. Lenni ICP fit (latest quarter)")
    ax.set_ylabel("Banks")
    plt.xticks(rotation=15)
    pdf.savefig(fig)
    plt.close(fig)

    # 3 Filing type
    fig, ax = plt.subplots(figsize=(7, 5))
    lat["form_size"].value_counts().plot(kind="bar", ax=ax, color=NAVY)
    ax.set_title("3. Call Report form type (051=031 larger, 041=community)")
    pdf.savefig(fig)
    plt.close(fig)

    # 4 Loan composition (ICP)
    if len(icp) > 0:
        comp = icp[
            ["ci_loans", "cre_proxy_total", "credit_card_plans", "other_consumer_loans", "lease_financing"]
        ].fillna(0)
        fig, ax = plt.subplots(figsize=(8, 5))
        comp.sum().plot(kind="bar", ax=ax, color=GOLD)
        ax.set_title("4. Aggregate loan categories — Lenni ICP banks (USD)")
        plt.xticks(rotation=30, ha="right")
        pdf.savefig(fig)
        plt.close(fig)
        summaries.append(
            "ICP banks show substantial CRE/C&I portfolios — aligned with Lenni's commercial lending focus."
        )

    # 5 Loan-to-asset
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(lat["loan_to_asset_ratio"].dropna().clip(0, 1.2), bins=35, color=NAVY)
    ax.set_xlabel("Loans / Assets")
    ax.set_title("5. Loan-to-asset ratio distribution")
    pdf.savefig(fig)
    plt.close(fig)

    # 6 Top cities
    top_cities = lat.groupby("city")["id_rssd"].nunique().sort_values(ascending=False).head(15)
    summaries.append(
        f"Top city: {top_cities.index[0]} ({top_cities.iloc[0]} banks) — relevant for one-bank-per-market."
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    top_cities.plot(kind="barh", ax=ax, color=SAGE)
    ax.set_title("6. Top 15 cities by bank count")
    ax.invert_yaxis()
    pdf.savefig(fig)
    plt.close(fig)

    # 7 Quarterly trends
    q = master.groupby("reporting_period").agg(
        banks=("id_rssd", "nunique"),
        median_assets=("total_assets", "median"),
        median_loans=("total_loans_gross", "median"),
        icp_banks=("icp_fit", lambda s: (s == "ICP ($500M–$2B)").sum()),
    ).reset_index()
    q["period_sort"] = pd.to_datetime(q["reporting_period"])
    q = q.sort_values("period_sort")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(q["reporting_period"], q["median_assets"] / 1_000_000, marker="o", color=NAVY)
    ax1.set_ylabel("Median assets ($ millions)")
    ax1.set_title("7. Texas banking trends by quarter")
    ax2 = ax1.twinx()
    ax2.plot(q["reporting_period"], q["median_loans"] / 1_000_000, marker="s", color=GOLD)
    ax2.set_ylabel("Median loans ($ millions)")
    pdf.savefig(fig)
    plt.close(fig)

    # 8 Top ICP banks
    if len(icp) > 0:
        top = icp.nlargest(15, "total_loans_gross")
        fig, ax = plt.subplots(figsize=(10, 7))
        labels = [f"{str(r.name)[:28]} ({r.city})" for r in top.itertuples()]
        ax.barh(range(len(top)), top["total_loans_gross"] / 1_000_000, color=NAVY)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Total loans ($ millions)")
        ax.set_title("8. Top 15 Lenni ICP banks by loan portfolio")
        pdf.savefig(fig)
        plt.close(fig)

    # 9 C&I vs CRE
    if len(icp) > 5:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(
            icp["ci_loans"].fillna(0) / 1_000_000,
            icp.get("cre_proxy_total", pd.Series(0, index=icp.index)).fillna(0) / 1_000_000,
            alpha=0.6, c=SAGE, edgecolors=NAVY, linewidths=0.3,
        )
        ax.set_xlabel("C&I loans ($ millions)")
        ax.set_ylabel("CRE proxy ($ millions)")
        ax.set_title("9. C&I vs CRE exposure — Lenni ICP banks")
        pdf.savefig(fig)
        plt.close(fig)

    # 10 Allowance ratio
    fig, ax = plt.subplots(figsize=(10, 5))
    ar = lat["allowance_ratio"].replace([np.inf, -np.inf], np.nan).dropna()
    ax.hist(ar.clip(0, 0.05), bins=30, color=GOLD)
    ax.set_xlabel("Allowance / Gross loans")
    ax.set_title("10. Allowance for loan losses ratio")
    pdf.savefig(fig)
    plt.close(fig)

    # 11 Past due
    if "past_due_90_plus" in lat.columns:
        fig, ax = plt.subplots(figsize=(10, 5))
        pd90 = (lat["past_due_90_plus"].fillna(0) / lat["total_loans_gross"].replace(0, np.nan)).dropna()
        ax.hist(pd90.clip(0, 0.1), bins=30, color=NAVY)
        ax.set_xlabel("90+ day past due / gross loans")
        ax.set_title("11. Credit stress proxy (90+ past due ratio)")
        pdf.savefig(fig)
        plt.close(fig)

    # 12 Consumer vs commercial
    lat2 = lat.dropna(subset=["ci_to_loans", "consumer_to_loans"])
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        lat2["consumer_to_loans"].clip(0, 1),
        lat2["ci_to_loans"].clip(0, 1),
        alpha=0.5, c=NAVY,
    )
    ax.set_xlabel("Consumer loans / total loans")
    ax.set_ylabel("C&I loans / total loans")
    ax.set_title("12. Bank orientation: consumer vs commercial")
    pdf.savefig(fig)
    plt.close(fig)

    # 13 QoQ growth
    m_sorted = master.sort_values(["id_rssd", "reporting_period"])
    m_sorted["loan_growth"] = m_sorted.groupby("id_rssd")["total_loans_gross"].pct_change(fill_method=None)
    growth = m_sorted["loan_growth"].replace([np.inf, -np.inf], np.nan).dropna()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(growth.clip(-0.3, 0.3), bins=40, color=SAGE)
    ax.set_xlabel("Quarter-over-quarter loan growth")
    ax.set_title("13. Loan portfolio growth (QoQ)")
    pdf.savefig(fig)
    plt.close(fig)

    # 14 ICP by period
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(q["reporting_period"], q["icp_banks"], color=SAGE)
    ax.set_title("14. Lenni ICP bank count by reporting period")
    ax.set_ylabel("Banks in $500M–$2B band")
    plt.xticks(rotation=20)
    pdf.savefig(fig)
    plt.close(fig)

    # 15 Asset bands (Lenni TAM sizing)
    bins = [0, 100e6, 250e6, 500e6, 1e9, 2e9, 5e9, 50e9]
    labels = ["<$100M", "$100–250M", "$250–500M", "$500M–$1B", "$1–2B", "$2–5B", ">$5B"]
    lat["asset_band"] = pd.cut(lat["total_assets"], bins=bins, labels=labels)
    band_counts = lat["asset_band"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(10, 5))
    band_counts.plot(kind="bar", ax=ax, color=NAVY)
    ax.set_title("15. Asset band distribution (latest quarter)")
    ax.set_ylabel("Banks")
    plt.xticks(rotation=25)
    pdf.savefig(fig)
    plt.close(fig)
    band_counts.to_csv(ANALYSIS / "asset_band_counts.csv")

    # 16 ICP loan mix (median ratios)
    if len(icp) > 0:
        mix = pd.DataFrame({
            "CRE / loans": icp["cre_to_loans"].median(),
            "C&I / loans": icp["ci_to_loans"].median(),
            "Consumer / loans": icp["consumer_to_loans"].median(),
            "Residential 1-4 / loans": (icp.get("residential_1_4_family", 0) / icp["total_loans_gross"]).median(),
        }, index=["Median ICP bank"])
        fig, ax = plt.subplots(figsize=(8, 4))
        mix.T.plot(kind="bar", ax=ax, legend=False, color=GOLD)
        ax.set_title("16. Median loan-mix ratios — Lenni ICP banks")
        ax.set_ylabel("Share of gross loans")
        plt.xticks(rotation=20)
        pdf.savefig(fig)
        plt.close(fig)

    # 17 Filing panel size by quarter
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(q["reporting_period"], q["banks"], color=NAVY)
    ax.set_title("17. Texas banks filing per quarter")
    ax.set_ylabel("Unique id_rssd")
    plt.xticks(rotation=20)
    pdf.savefig(fig)
    plt.close(fig)

    # 18 CRE-to-loans distribution (ICP)
    if len(icp) > 0:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(icp["cre_to_loans"].replace([np.inf, -np.inf], np.nan).dropna().clip(0, 1), bins=25, color=SAGE)
        ax.set_xlabel("CRE proxy / gross loans")
        ax.set_title("18. CRE concentration — Lenni ICP banks")
        pdf.savefig(fig)
        plt.close(fig)

    # 19 Box plot: total loans by form_size
    fig, ax = plt.subplots(figsize=(8, 5))
    lat.boxplot(column="total_loans_gross", by="form_size", ax=ax)
    ax.set_title("19. Loan portfolio size by Call Report form")
    ax.set_ylabel("Gross loans (USD)")
    plt.suptitle("")
    pdf.savefig(fig)
    plt.close(fig)

    # 20 Top 10 ICP cities
    if len(icp) > 0:
        icp_cities = icp.groupby("city")["id_rssd"].nunique().sort_values(ascending=False).head(10)
        fig, ax = plt.subplots(figsize=(9, 5))
        icp_cities.plot(kind="barh", ax=ax, color=GOLD)
        ax.set_title("20. Top 10 cities — Lenni ICP bank count")
        ax.invert_yaxis()
        pdf.savefig(fig)
        plt.close(fig)

    # 21 Summary statistics table (text page)
    stats_cols = ["total_assets", "total_loans_gross", "ci_loans", "cre_proxy_total", "loan_to_asset_ratio"]
    stats = lat[stats_cols].describe(percentiles=[0.25, 0.5, 0.75]).round(2)
    stats.to_csv(ANALYSIS / "summary_statistics_latest.csv")
    text_page(
        pdf,
        "21. Summary statistics (latest quarter, all banks with assets)",
        stats.to_string(),
    )

    # 22 ICP prospect export
    if len(icp) > 0:
        prospect_cols = [
            "id_rssd", "name", "city", "filing_type", "total_assets", "total_loans_gross",
            "ci_loans", "cre_proxy_total", "loan_to_asset_ratio", "cre_to_loans", "ci_to_loans",
        ]
        icp[[c for c in prospect_cols if c in icp.columns]].sort_values(
            "total_loans_gross", ascending=False
        ).to_csv(ANALYSIS / "lenni_icp_prospect_list.csv", index=False)
        summaries.append(f"Exported {len(icp)} ICP banks to analysis/lenni_icp_prospect_list.csv")

    # 23 Loan category heatmap by asset band (median $M)
    heat_cols = [c for c in [
        "ci_loans", "cre_proxy_total", "residential_1_4_family",
        "credit_card_plans", "other_consumer_loans", "ag_production_loans",
    ] if c in lat.columns]
    if heat_cols:
        hm = lat.groupby("asset_band", observed=True)[heat_cols].median() / 1e6
        fig, ax = plt.subplots(figsize=(10, 6))
        im = ax.imshow(hm.values, aspect="auto", cmap="YlGn")
        ax.set_xticks(range(len(heat_cols)))
        ax.set_xticklabels(heat_cols, rotation=35, ha="right", fontsize=8)
        ax.set_yticks(range(len(hm)))
        ax.set_yticklabels(hm.index.astype(str))
        ax.set_title("23. Median loan category ($M) by asset band")
        plt.colorbar(im, ax=ax, label="$ millions")
        pdf.savefig(fig)
        plt.close(fig)

    # 24 Asset growth QoQ
    m_sorted2 = master.sort_values(["id_rssd", "reporting_period"])
    m_sorted2["asset_growth"] = m_sorted2.groupby("id_rssd")["total_assets"].pct_change(fill_method=None)
    ag = m_sorted2["asset_growth"].replace([np.inf, -np.inf], np.nan).dropna()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(ag.clip(-0.2, 0.2), bins=40, color=NAVY)
    ax.set_xlabel("Quarter-over-quarter asset growth")
    ax.set_title("24. Asset growth distribution (QoQ)")
    pdf.savefig(fig)
    plt.close(fig)

    # 25 Banks with low consumer share (portfolio lenders)
    low_consumer = lat[lat["consumer_to_loans"].fillna(1) < 0.15]
    summaries.append(
        f"{len(low_consumer)} banks ({100*len(low_consumer)/len(lat):.0f}%) have consumer loans <15% of portfolio — "
        "Lenni's commercial/portfolio-lending sweet spot."
    )
    fig, ax = plt.subplots(figsize=(7, 5))
    pd.Series({
        "Consumer <15%": len(low_consumer),
        "Consumer ≥15%": len(lat) - len(low_consumer),
    }).plot(kind="bar", ax=ax, color=[SAGE, GOLD])
    ax.set_title("25. Portfolio orientation — low vs higher consumer share")
    pdf.savefig(fig)
    plt.close(fig)

    # Market segments CSV
    opp = pd.DataFrame({
        "Segment": ["ICP ($500M–$2B)", "Below $500M", "Above $2B", "Missing asset data"],
        "Banks_latest": [
            len(icp),
            len(lat[lat["total_assets"] < ICP_ASSETS_MIN]),
            len(lat[lat["total_assets"] > ICP_ASSETS_MAX]),
            len(latest) - len(lat),
        ],
    })
    opp.to_csv(ANALYSIS / "lenni_market_segments.csv", index=False)
    summaries.append("Market segments:\n" + opp.to_string(index=False))

    return summaries


def main() -> int:
    print("Loading CSVs …")
    inst, filings, loans = load_base()
    print("Loading XBRL balance-sheet metrics (chunked) …")
    xbrl = load_xbrl_metrics()
    metrics = merge_metrics(pivot_loan_metrics(loans), xbrl)
    master = build_joined(inst, filings, metrics)
    latest = latest_snapshot(master)
    save_joined(master, latest)
    print(f"Wrote texas_master_joined.csv ({len(master):,} rows)")
    print(f"Wrote texas_bank_profiles_latest.csv ({len(latest):,} rows)")
    print(f"Wrote texas_loans_joined_long.csv")

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    with PdfPages(REPORT_PDF) as pdf:
        text_page(
            pdf,
            "Lenni Texas Community Bank — Exploratory Data Analysis",
            textwrap.dedent(f"""
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
                Data: FFIEC Call Report XBRL — Texas banks, 2025+
                Reference: lenni_contenxt.txt (Lenni / Convey by Lenni)

                PURPOSE
                Support Lenni go-to-market: Texas banks in $500M–$2B, loan portfolio profiling
                (CRE, C&I, consumer), and one-bank-per-market sales planning.

                JOINED TABLES (exports/)
                • texas_master_joined.csv — bank × quarter, wide metrics
                • texas_bank_profiles_latest.csv — latest quarter per bank
                • texas_loans_joined_long.csv — loan lines + institution fields

                JOIN KEYS: id_rssd + reporting_period
                AMOUNTS: USD (parsed from XBRL fact values).
            """),
        )
        text_page(
            pdf,
            "Analysis index (25 slices)",
            textwrap.dedent("""
                1  Asset size distribution vs Lenni ICP band
                2  ICP fit (in/out of $500M–$2B)
                3  Call Report form type (031 vs 041)
                4  Aggregate loan categories — ICP banks
                5  Loan-to-asset ratio
                6  Top cities by bank count (market planning)
                7  Quarterly median assets & loans
                8  Top 15 ICP banks by loan portfolio
                9  C&I vs CRE scatter — ICP
                10 Allowance / loans ratio
                11 90+ day past-due stress proxy
                12 Consumer vs commercial orientation
                13 Quarter-over-quarter loan growth
                14 ICP bank count by period
                15 Asset band TAM sizing
                16 Median loan-mix ratios — ICP
                17 Filing panel size by quarter
                18 CRE concentration — ICP
                19 Loan size by form type (boxplot)
                20 Top ICP cities
                21 Summary statistics table
                22 ICP prospect CSV export
                23 Loan category heatmap by asset band
                24 Asset growth QoQ
                25 Low-consumer-share banks (portfolio lenders)
            """),
        )
        text_page(
            pdf,
            "Joined table schema",
            textwrap.dedent("""
                texas_master_joined.csv columns:
                Institution: id_rssd, name, city, state, filing_type, form_size, has_filed
                Filing: retrieved_at, file_path, sha256, file_size_bytes
                Metrics (USD): total_assets (RCON2170), total_loans_gross (RCON2122),
                  ci_loans (RCON1766), cre_proxy_total, allowance_loan_losses, credit_card_plans,
                  other_consumer_loans, residential_1_4_family, past_due_90_plus, ...
                Derived: loan_to_asset_ratio, allowance_ratio, cre_to_loans, ci_to_loans,
                  consumer_to_loans, icp_fit

                JOIN: institutions → filings → loan summary pivot + XBRL balance-sheet pivot
            """),
        )
        summaries = run_eda(master, latest, pdf)
        text_page(pdf, "Executive findings", "\n\n".join(f"• {s}" for s in summaries))
        text_page(
            pdf,
            "Recommendations for Lenni",
            textwrap.dedent("""
                1. Filter texas_bank_profiles_latest.csv by icp_fit for CLO prospect lists.
                2. Use city counts for one-bank-per-market exclusivity planning.
                3. Prioritize high CRE/C&I banks — portfolio lenders, not mortgage-only shops.
                4. Layer digital-gap research (267/360 no online app) on top of this FFIEC core.
                5. Re-run build_lenni_eda_report.py after each FFIEC sync.

                LIMITATIONS: FFIEC has no online-application field; CRE proxy sums RC-C lines.
            """),
        )
        pdf.infodict()["Title"] = "Lenni Texas Bank EDA Report"

    print(f"Report: {REPORT_PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
