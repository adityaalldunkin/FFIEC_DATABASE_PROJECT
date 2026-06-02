"""Phase 6: public FastAPI over archived and parsed data."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from ffiec_cdr.db import connect, init_db
from ffiec_cdr.search import (
    compare_periods,
    get_filing_detail,
    latest_updates,
    search_facts_by_concept,
    search_filings,
    search_institutions,
)

app = FastAPI(
    title="FFIEC CDR Public Data Platform",
    description="Search Call Report filings ingested from the FFIEC Public Web Service.",
    version="1.0.0",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/institutions/search")
def api_search_institutions(
    q: str = Query("", description="Name or RSSD substring"),
    state: str | None = None,
    limit: int = Query(50, le=200),
) -> list[dict]:
    with connect() as conn:
        return search_institutions(conn, q, state=state, limit=limit)


@app.get("/filings/search")
def api_search_filings(
    id_rssd: int | None = None,
    period: str | None = None,
    data_series: str | None = None,
    limit: int = Query(50, le=200),
) -> list[dict]:
    with connect() as conn:
        return search_filings(
            conn, id_rssd=id_rssd, period=period, data_series=data_series, limit=limit
        )


@app.get("/filings/{filing_id}")
def api_filing_detail(filing_id: int) -> dict:
    with connect() as conn:
        detail = get_filing_detail(conn, filing_id)
    if not detail:
        raise HTTPException(404, "Filing not found")
    return detail


@app.get("/filings/{filing_id}/download")
def api_download_source(filing_id: int) -> FileResponse:
    with connect() as conn:
        row = conn.execute("SELECT file_path FROM filings WHERE id = ?", (filing_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Filing not found")
    path = Path(row["file_path"])
    if not path.is_file():
        raise HTTPException(404, "Source file missing on disk")
    return FileResponse(path, filename=path.name)


@app.get("/facts/search")
def api_search_facts(
    concept: str = Query(..., description="Concept name substring, e.g. Assets"),
    limit: int = Query(100, le=500),
) -> list[dict]:
    with connect() as conn:
        return search_facts_by_concept(conn, concept, limit=limit)


@app.get("/institutions/{id_rssd}/compare")
def api_compare(
    id_rssd: int,
    concept: str = Query(..., description="Concept substring across periods"),
) -> list[dict]:
    with connect() as conn:
        return compare_periods(conn, id_rssd, concept)


@app.get("/updates/latest")
def api_latest_updates(limit: int = Query(20, le=100)) -> list[dict]:
    with connect() as conn:
        return latest_updates(conn, limit=limit)
