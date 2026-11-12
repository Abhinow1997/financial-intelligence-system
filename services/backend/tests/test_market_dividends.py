import pandas as pd
import pytest
import yfinance as yf
from app.main import app
from fastapi.testclient import TestClient
from yfinance.exceptions import YFRateLimitError

client = TestClient(app)

# Two payments as yfinance returns them: a tz-aware index and float amounts.
PAYMENTS = pd.Series(
    [0.24, 0.25],
    index=pd.DatetimeIndex(["2025-02-10", "2025-05-12"], tz="America/New_York"),
    name="Dividends",
)


def fake_yahoo(monkeypatch, *, dividends=None, error=None):
    # Replace yfinance's Ticker so no request leaves the test process.
    symbols = []

    class FakeTicker:
        def __init__(self, symbol):
            symbols.append(symbol)

        @property
        def dividends(self):
            if error is not None:
                raise error
            return dividends

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    return symbols


def test_dividend_history_is_typed_and_ordered(monkeypatch):
    symbols = fake_yahoo(monkeypatch, dividends=PAYMENTS)
    r = client.get("/market/dividends/aapl")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["count"] == 2
    assert [d["amount"] for d in body["dividends"]] == [0.24, 0.25]
    assert body["dividends"][0]["date"].startswith("2025-02-10")
    assert isinstance(body["latency_ms"], int)
    assert symbols == ["AAPL"]


def test_unknown_or_non_paying_ticker_is_404(monkeypatch):
    fake_yahoo(monkeypatch, dividends=pd.Series([], dtype=float))
    assert client.get("/market/dividends/NOPE").status_code == 404


def test_rate_limit_is_503(monkeypatch):
    fake_yahoo(monkeypatch, error=YFRateLimitError())
    assert client.get("/market/dividends/AAPL").status_code == 503


def test_other_upstream_failure_is_502_not_500(monkeypatch):
    fake_yahoo(monkeypatch, error=RuntimeError("connection reset"))
    assert client.get("/market/dividends/AAPL").status_code == 502


@pytest.mark.parametrize("bad", ["BAD%20TICKER", "A" * 13])
def test_invalid_ticker_is_rejected_before_upstream(monkeypatch, bad):
    symbols = fake_yahoo(monkeypatch, dividends=PAYMENTS)
    assert client.get(f"/market/dividends/{bad}").status_code == 422
    assert symbols == []
