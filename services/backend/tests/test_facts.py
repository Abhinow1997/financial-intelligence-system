import duckdb
import pytest
from app import facts
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# A trimmed companyfacts document: two 10-Ks (the second repeats the first's year) and a 10-Q.
COMPANYFACTS = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        {"start": "2024-01-01", "end": "2024-12-31", "val": 100.0, "accn": "0000000001-25-000001", "form": "10-K"},
        {"start": "2025-01-01", "end": "2025-12-31", "val": 120.0, "accn": "0000000001-26-000001", "form": "10-K"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 100.0, "accn": "0000000001-26-000001", "form": "10-K"},
        {"start": "2025-07-01", "end": "2025-09-30", "val": 30.0, "accn": "0000000001-25-000009", "form": "10-Q"},
    ]}},
    "EarningsPerShareDiluted": {"units": {"USD/shares": [
        {"start": "2025-01-01", "end": "2025-12-31", "val": 1.5, "accn": "0000000001-26-000001", "form": "10-K"},
    ]}},
}}}


@pytest.fixture(autouse=True)
def sec_calls(tmp_path, monkeypatch):
    # The fact store lives in a temp folder, and the SEC is replaced by canned answers.
    monkeypatch.setattr(facts, "FACTS_DB", tmp_path / "facts.duckdb")
    monkeypatch.setattr(facts, "_cik_by_ticker", {})
    calls = []

    def fake_sec_get(url):
        calls.append(url)
        if url == facts.SEC_TICKERS_URL:
            return {"0": {"cik_str": 1, "ticker": "TEST", "title": "Test Corp"}}
        return COMPANYFACTS

    monkeypatch.setattr(facts, "_sec_get", fake_sec_get)
    return calls


def store_fact(deal_id):
    # A pipeline-built row (its extractor isn't the API's)
    with duckdb.connect(str(facts.FACTS_DB)) as con:
        con.execute(facts.FACTS_SCHEMA)
        con.execute(
            """INSERT INTO facts (fact_id, deal_id, entity_id, metric, value, unit, "end", tier, citation)
               VALUES (?, ?, 'AAPL', 'revenue', 391035000000, 'USD', '2024-09-28', 1, '{"kind": "ixbrl_context"}')""",
            [f"f-{deal_id}", deal_id],
        )


def test_sec_miss_fetches_once_then_serves_saved_facts(sec_calls):
    first = client.get("/facts/TEST")
    assert first.status_code == 200
    body = first.json()
    assert body["source"] == "sec_live"
    # One fact per 10-K per metric: the prior-year repeat and the 10-Q are skipped
    assert sorted((f["metric"], f["period_end"], f["value"]) for f in body["facts"]) == [
        ("eps_diluted", "2025-12-31", 1.5),
        ("revenue", "2024-12-31", 100.0),
        ("revenue", "2025-12-31", 120.0),
    ]
    assert all(f["tier"] == 1 and f["citation"]["kind"] == "ixbrl_context" for f in body["facts"])

    second = client.get("/facts/test", params={"metric": "revenue"})
    assert second.json()["source"] == "sec_cache"
    assert second.json()["count"] == 2
    assert len(sec_calls) == 2  # ticker list + companyfacts, fetched once


def test_fact_store_is_read_first(sec_calls):
    store_fact("public")
    r = client.get("/facts/aapl")
    assert r.status_code == 200
    assert r.json()["source"] == "fact_store"
    assert r.json()["count"] == 1
    assert sec_calls == []


def test_deal_facts_are_never_served():
    store_fact("deal_b")  # a data-room fact must not leak through a ticker lookup
    r = client.get("/facts/AAPL")
    assert r.status_code == 404  # not public in the store, and not a ticker the fake SEC knows


def test_unknown_metric_is_422():
    assert client.get("/facts/TEST", params={"metric": "ebitda"}).status_code == 422


def test_list_tickers():
    store_fact("public")
    client.get("/facts/TEST")
    assert client.get("/facts").json() == [
        {"ticker": "AAPL", "source": "fact_store", "facts": 1, "latest_period_end": "2024-09-28"},
        {"ticker": "TEST", "source": "sec_cache", "facts": 3, "latest_period_end": "2025-12-31"},
    ]


def test_pipeline_and_api_facts_share_one_file():
    store_fact("public")
    client.get("/facts/TEST")
    with duckdb.connect(str(facts.FACTS_DB)) as con:
        tables = con.execute("SELECT count(*) FROM duckdb_tables()").fetchone()[0]
        api_rows = con.execute("SELECT count(*) FROM facts WHERE extractor = ?", [facts.API_EXTRACTOR]).fetchone()[0]
    assert (tables, api_rows) == (1, 3)  # one `facts` table holds both kinds of row
