"""
Loan portfolio mix from FFIEC Call Report line items.

Maps Schedule RC-C (and FFIEC 051 supplemental lines) into display categories.
Residual balances that do not map to a known line item go to ``uncat``, not ag.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"

MIX_KEYS = (
    "mf",
    "inv",
    "own",
    "con",
    "ci",
    "res",
    "cons",
    "farm",
    "ag",
    "lease",
    "uncat",
)

MIX_LABELS = {
    "mf": "Multifamily",
    "inv": "Investor CRE",
    "own": "Owner-occupied CRE",
    "con": "Construction",
    "ci": "C&I / Business",
    "res": "1–4 Residential",
    "cons": "Consumer",
    "farm": "Farmland",
    "ag": "Ag production",
    "lease": "Lease financing",
    "uncat": "Unclassified",
}

MIX_COLORS = {
    "mf": "#1f9d76",
    "inv": "#2f6fed",
    "own": "#7c3aed",
    "con": "#e08a2b",
    "ci": "#db5461",
    "res": "#58b3c7",
    "cons": "#9aa6b2",
    "farm": "#8b6914",
    "ag": "#6b8e23",
    "lease": "#a78bfa",
    "uncat": "#c4ccd6",
}

# Loan product YAML ``key`` → one or more mix buckets (e.g. ag product = farm + ag).
PRODUCT_MIX_KEYS: dict[str, tuple[str, ...]] = {
    "mf": ("mf",),
    "inv": ("inv",),
    "own": ("own",),
    "con": ("con",),
    "ci": ("ci",),
    "res": ("res",),
    "cons": ("cons",),
    "oth": ("farm", "ag"),
}

SUPPLEMENTAL_XBRL_CODES = {
    "RCONS439": "residential_mortgage_exposures",
    "RCON1797": "revolving_1_4_family",
    "RCONB562": "consumer_other_051",
    "RCONB539": "consumer_revolving_051",
}


def safe_num(v, default: float = 0.0) -> float:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def mix_score(mix: dict[str, int], product_key: str) -> int:
    keys = PRODUCT_MIX_KEYS.get(product_key, (product_key,))
    return sum(mix.get(k, 0) for k in keys)


def enrich_profiles_with_supplemental(df: pd.DataFrame) -> pd.DataFrame:
    """Attach FFIEC 051 / supplemental loan lines from chunked XBRL facts."""
    path = EXPORTS / "texas_xbrl_facts.csv"
    if not path.exists() or df.empty:
        return df

    out = df.copy()
    for col in SUPPLEMENTAL_XBRL_CODES.values():
        if col not in out.columns:
            out[col] = 0.0

    rssd_set = set(out["id_rssd"].astype(int))
    period_by_rssd = out.set_index("id_rssd")["reporting_period"].astype(str).to_dict()
    code_set = set(SUPPLEMENTAL_XBRL_CODES.keys())
    values: dict[tuple[int, str], float] = {}

    for chunk in pd.read_csv(
        path,
        chunksize=250_000,
        dtype={"id_rssd": int},
        usecols=["id_rssd", "reporting_period", "concept", "value_num"],
    ):
        chunk["mdrm"] = chunk["concept"].str.extract(r"(RCON[A-Z0-9]+)", expand=False)
        sub = chunk[chunk["mdrm"].isin(code_set) & chunk["id_rssd"].isin(rssd_set)]
        if sub.empty:
            continue
        for _, row in sub.iterrows():
            rssd = int(row["id_rssd"])
            period = str(row["reporting_period"])
            if period != period_by_rssd.get(rssd):
                continue
            col = SUPPLEMENTAL_XBRL_CODES[str(row["mdrm"])]
            val = safe_num(row["value_num"])
            key = (rssd, col)
            values[key] = max(values.get(key, 0.0), val)

    for rssd in rssd_set:
        mask = out["id_rssd"] == rssd
        for col in SUPPLEMENTAL_XBRL_CODES.values():
            out.loc[mask, col] = values.get((rssd, col), 0.0)
    return out


def compute_mix_parts(row: pd.Series) -> dict[str, float]:
    """Dollar amounts per mix bucket (before percent rounding)."""
    total = safe_num(row.get("total_loans_gross"))
    if total <= 0:
        return {k: 0.0 for k in MIX_KEYS}

    res = safe_num(row.get("residential_1_4_family")) + safe_num(row.get("revolving_1_4_family"))
    res_mtg = safe_num(row.get("residential_mortgage_exposures"))
    if res_mtg > res:
        res = res_mtg

    parts = {
        "mf": safe_num(row.get("multifamily_re_loans")),
        "inv": safe_num(row.get("other_nonfarm_nonres_re")) + safe_num(row.get("commercial_re_loans")),
        "own": safe_num(row.get("owner_occupied_nonfarm_re")),
        "con": safe_num(row.get("residential_construction")) + safe_num(row.get("other_construction_ld")),
        "ci": safe_num(row.get("ci_loans")),
        "res": res,
        "cons": (
            safe_num(row.get("credit_card_plans"))
            + safe_num(row.get("other_consumer_loans"))
            + safe_num(row.get("consumer_other_051"))
            + safe_num(row.get("consumer_revolving_051"))
        ),
        "farm": safe_num(row.get("farmland_loans")),
        "ag": safe_num(row.get("ag_production_loans")),
        "lease": safe_num(row.get("lease_financing")),
    }

    accounted = sum(parts.values())
    parts["uncat"] = max(0.0, total - accounted)

    # Guard against double-counting / overlapping supplemental lines.
    bucket_sum = sum(parts.values())
    if bucket_sum > total * 1.02 and bucket_sum > 0:
        scale = total / bucket_sum
        for key in parts:
            parts[key] *= scale
        parts["uncat"] = max(0.0, total - sum(v for k, v in parts.items() if k != "uncat"))

    return parts


def compute_mix(row: pd.Series) -> dict[str, int]:
    total = safe_num(row.get("total_loans_gross"))
    if total <= 0:
        return {k: 0 for k in MIX_KEYS}

    parts = compute_mix_parts(row)
    pcts = {k: round(100 * parts[k] / total) for k in MIX_KEYS}
    drift = 100 - sum(pcts.values())
    if drift:
        adjustable = [k for k in MIX_KEYS if pcts[k] > 0]
        target = max(adjustable, key=lambda k: pcts[k]) if adjustable else "uncat"
        pcts[target] += drift
    return pcts


def mix_parts_usd(row: pd.Series) -> dict[str, float]:
    return compute_mix_parts(row)


def top_specialties(mix: dict[str, int], n: int = 3) -> list[tuple[str, int]]:
    ranked = sorted(
        ((k, v) for k, v in mix.items() if v > 0 and k != "uncat"),
        key=lambda x: -x[1],
    )
    if not ranked and mix.get("uncat", 0) > 0:
        ranked = [("uncat", mix["uncat"])]
    return [(MIX_LABELS[k], v) for k, v in ranked[:n]]


def _title_city(city: str) -> str:
    return city.strip().title() if city else "Texas"


def describe_bank(name: str, city: str, metro: str, mix: dict, assets_m: float, icp: bool) -> str:
    specs = top_specialties(mix, 2)
    spec_txt = " and ".join(f"{v}% {k.lower()}" for k, v in specs) if specs else "diversified lending"
    if mix.get("uncat", 0) >= 25 and specs:
        spec_txt += f" ({mix['uncat']}% unclassified in Call Report detail)"
    size = f"${assets_m/1000:.1f}B" if assets_m >= 1000 else f"${assets_m:.0f}M"
    icp_note = " Community bank in Lenni's core $500M–$2B segment." if icp else ""
    return (
        f"{name.strip()} is headquartered in {_title_city(city)}, Texas ({metro} market), "
        f"with roughly {size} in total assets. Based on the latest FFIEC Call Report, "
        f"its loan portfolio emphasizes {spec_txt}.{icp_note}"
    )
