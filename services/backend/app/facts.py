# Facts endpoints backed by DuckDB (Case Study 2 fact store).
# Everything lives in one file, data/facts/facts.duckdb. src/facts/build.py writes the
# pipeline's facts into it; a ticker that isn't there yet is fetched once from the SEC
# companyfacts API and saved into the same `facts` table, so the next request is served
# from DuckDB. The `extractor` column records who wrote each row, which is how a rebuild
# replaces only its own rows and how responses say where a number came from.
from __future__ import annotations

import json
import os
import threading
import time
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import duckdb
import requests
import yaml
from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from pydantic import BaseModel

router = APIRouter(prefix="/facts", tags=["facts"])

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[3] if len(_HERE.parents) > 3 else Path.cwd()  # services/backend/app/ -> repo
FACTS_DB = Path(os.environ.get("FACTS_DB", REPO_ROOT / "data" / "facts" / "facts.duckdb"))

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
API_EXTRACTOR = "sec companyfacts api (services/backend/app/facts.py)"  # tags the rows this API saves

TickerParam = Annotated[
    str,
    PathParam(pattern=r"^[A-Za-z0-9.\-]{1,10}$", description="Stock ticker, e.g. AAPL or BRK-B"),
]


class Metric(str, Enum):
    REVENUE = "revenue"
    OPERATING_INCOME = "operating_income"
    NET_INCOME = "net_income"
    EPS_DILUTED = "eps_diluted"


# Metric -> (companyfacts unit, XBRL concepts tried in order): the lines src/parse.py reads.
METRICS: dict[Metric, tuple[str, tuple[str, ...]]] = {
    Metric.REVENUE: ("USD", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                             "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet")),
    Metric.OPERATING_INCOME: ("USD", ("OperatingIncomeLoss",)),
    Metric.NET_INCOME: ("USD", ("NetIncomeLoss",)),
    Metric.EPS_DILUTED: ("USD/shares", ("EarningsPerShareDiluted",)),
}

# Same table and rules as `facts` in src/facts/build.py; whichever runs first creates it.
FACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id     VARCHAR PRIMARY KEY,
    deal_id     VARCHAR NOT NULL,
    entity_id   VARCHAR,
    concept     VARCHAR,
    metric      VARCHAR,
    value       DOUBLE,
    unit        VARCHAR,
    period_type VARCHAR,
    "start"     DATE,
    "end"       DATE,
    dims        JSON,
    decimals    INTEGER,
    tier        TINYINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
    source_type VARCHAR,
    doc_id      VARCHAR,
    citation    JSON NOT NULL,
    extractor   VARCHAR,
    lineage     JSON
);
"""

STAGE = """
CREATE TEMP TABLE incoming (
    ticker VARCHAR, accession VARCHAR, concept VARCHAR, metric VARCHAR, value DOUBLE,
    unit VARCHAR, period_start DATE, period_end DATE, source_url VARCHAR
)
"""

# One staged companyfacts value -> one tier-1 fact, the same shape src/facts/build.py writes.
# OR IGNORE: a fact the pipeline already holds (same fact_id) keeps the pipeline's row.
LOAD_INCOMING = """
INSERT OR IGNORE INTO facts BY NAME
SELECT
    md5(concat_ws('|', accession, concept, period_end)) AS fact_id,   -- the id build.py would give it
    'public'                 AS deal_id,
    ticker                   AS entity_id,
    'us-gaap:' || concept    AS concept,
    metric,
    value,
    unit,
    'duration'               AS period_type,
    period_start             AS "start",
    period_end               AS "end",
    1                        AS tier,
    'edgar_xbrl'             AS source_type,
    accession                AS doc_id,
    json_object('kind', 'ixbrl_context', 'doc_id', accession,
                'concept', 'us-gaap:' || concept, 'period_end', period_end) AS citation,
    ?                        AS extractor,
    json_object('parents', [accession], 'source', source_url) AS lineage
FROM incoming
"""

# Only public EDGAR facts: a ticker lookup must never surface data-room (deal) facts.
READ = """
SELECT fact_id, metric, concept, value, unit, "end" AS period_end, tier, doc_id, citation, extractor
FROM facts
WHERE entity_id = ? AND deal_id = 'public'
ORDER BY "end" DESC, metric
"""

SUMMARY = """
SELECT entity_id AS ticker,
       CASE WHEN extractor = ? THEN 'sec_cache' ELSE 'fact_store' END AS source,
       count(*) AS facts,
       max("end") AS latest_period_end
FROM facts
WHERE deal_id = 'public'
GROUP BY ALL
ORDER BY ticker, source
"""

# fact_store: built by the pipeline. sec_cache: saved by this API on an earlier request.
# sec_live: fetched from the SEC by this request (and saved for next time).
Source = Literal["fact_store", "sec_cache", "sec_live"]


class Fact(BaseModel):
    fact_id: str
    metric: str
    concept: str | None = None
    value: float
    unit: str
    period_end: date
    tier: int
    doc_id: str | None = None
    citation: dict[str, Any]


class TickerFacts(BaseModel):
    ticker: str
    source: Source
    count: int
    facts: list[Fact]
    latency_ms: int


class TickerSummary(BaseModel):
    ticker: str
    source: Source
    facts: int
    latest_period_end: date


_fetch_lock = threading.Lock()  # one SEC fetch at a time, so a ticker is never written twice
_cik_by_ticker: dict[str, int] = {}


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _open() -> duckdb.DuckDBPyConnection:
    # Always read-write, even for reads: DuckDB refuses two connections to one file with
    # different settings, and a request may need to save facts. The file is opened only for
    # the length of a request, so the pipeline and other tools can use it in between.
    try:
        con = duckdb.connect(str(FACTS_DB))
    except duckdb.IOException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Can't open {FACTS_DB.name}; another program may have it open "
                   f"(VS Code Database Client, DuckDB CLI, a notebook, build.py). {e}",
        ) from None
    con.execute(FACTS_SCHEMA)
    return con


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _read(ticker: str) -> tuple[list[Fact], bool]:
    """The ticker's public facts, and whether any of them came from the pipeline."""
    if not FACTS_DB.exists():
        return [], False
    with _open() as con:
        rows = _rows(con, READ, [ticker])
    facts = [Fact(**{**row, "citation": json.loads(row["citation"])}) for row in rows]
    return facts, any(row["extractor"] != API_EXTRACTOR for row in rows)


def _user_agent() -> str:
    # SEC fair access requires a User-Agent that names you. SEC_USER_AGENT wins;
    # otherwise use the one the `download` stage declares in params.yaml.
    if agent := os.environ.get("SEC_USER_AGENT"):
        return agent
    params = REPO_ROOT / "params.yaml"
    if params.exists():
        download = yaml.safe_load(params.read_text(encoding="utf-8"))["download"]
        return f"{download['user_agent_name']} {download['user_agent_email']}"
    raise HTTPException(status_code=503, detail="Set SEC_USER_AGENT, e.g. 'Team Name you@northeastern.edu'.")


def _sec_get(url: str) -> dict[str, Any] | None:
    """One SEC JSON document, or None if the SEC has no such document (404)."""
    try:
        resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"SEC request failed: {e}") from None
    if resp.status_code == 404:
        return None
    if resp.status_code in (403, 429):
        raise HTTPException(
            status_code=503,
            detail="SEC refused the request (rate limit or missing User-Agent). Back off and retry.",
        )
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"SEC returned HTTP {resp.status_code} for {url}.")
    return resp.json()


def _cik(ticker: str) -> int:
    if not _cik_by_ticker:
        listing = _sec_get(SEC_TICKERS_URL) or {}
        _cik_by_ticker.update({row["ticker"].upper(): int(row["cik_str"]) for row in listing.values()})
    cik = _cik_by_ticker.get(ticker)
    if cik is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' is not in the SEC's ticker list.")
    return cik


def _annual_values(companyfacts: dict[str, Any]) -> list[tuple]:
    """Each 10-K's own full-year value for each metric.

    A 10-K repeats the prior two years next to its own, all under the same accession,
    so per filing keep only the latest period: the year that filing reports.
    """
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    values = []
    for metric, (unit, concepts) in METRICS.items():
        covered: set[str] = set()  # filings an earlier concept in the list already answered
        for concept in concepts:
            own_year: dict[str, dict[str, Any]] = {}
            for v in gaap.get(concept, {}).get("units", {}).get(unit, []):
                if v.get("form") != "10-K" or "start" not in v or v["accn"] in covered:
                    continue
                if (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days < 350:
                    continue  # a quarter, not a full year
                if v["accn"] not in own_year or v["end"] > own_year[v["accn"]]["end"]:
                    own_year[v["accn"]] = v
            values += [(accn, concept, metric.value, float(v["val"]), unit, v["start"], v["end"])
                       for accn, v in own_year.items()]
            covered.update(own_year)
    return values


def _fetch_and_save(ticker: str) -> list[Fact]:
    with _fetch_lock:
        saved, _ = _read(ticker)  # another request may have fetched it meanwhile
        if saved:
            return saved
        url = SEC_FACTS_URL.format(cik=_cik(ticker))
        companyfacts = _sec_get(url)
        values = _annual_values(companyfacts) if companyfacts else []
        if not values:
            raise HTTPException(
                status_code=404,
                detail=f"The SEC has no annual 10-K facts for '{ticker}' "
                       f"({', '.join(m.value for m in Metric)}).",
            )
        FACTS_DB.parent.mkdir(parents=True, exist_ok=True)
        with _open() as con:
            con.execute(STAGE)
            con.executemany("INSERT INTO incoming VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            [(ticker, *v, url) for v in values])
            con.execute(LOAD_INCOMING, [API_EXTRACTOR])
    return _read(ticker)[0]


@router.get("", response_model=list[TickerSummary], summary="Tickers already in DuckDB")
def list_tickers() -> list[TickerSummary]:
    """What the fact store holds, by who wrote it. Makes no SEC calls."""
    if not FACTS_DB.exists():
        return []
    with _open() as con:
        return [TickerSummary(**row) for row in _rows(con, SUMMARY, [API_EXTRACTOR])]


@router.get("/{ticker}", response_model=TickerFacts, summary="Annual XBRL facts for a ticker")
def get_ticker_facts(ticker: TickerParam, metric: Metric | None = None) -> TickerFacts:
    """From the fact store if it holds the ticker; otherwise fetched from the SEC and saved there.

    `metric` is `Enum`-typed, so FastAPI rejects unknown metrics with a 422.
    """
    started = time.perf_counter()
    symbol = ticker.upper().replace(".", "-")  # the SEC lists BRK.B as BRK-B

    facts, from_pipeline = _read(symbol)
    if facts:
        source: Source = "fact_store" if from_pipeline else "sec_cache"
    else:
        source, facts = "sec_live", _fetch_and_save(symbol)

    if metric is not None:
        facts = [f for f in facts if f.metric == metric.value]
    return TickerFacts(
        ticker=symbol,
        source=source,
        count=len(facts),
        facts=facts,
        latency_ms=_elapsed_ms(started),
    )
