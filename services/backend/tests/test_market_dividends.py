import pandas as pd
import pytest
from app import market
from app.main import app
from fastapi.testclient import TestClient
from yfinance.exceptions import YFRateLimitError

client = TestClient(app)


def fake_yahoo(dividends=None, error=None):
    # Replaces yf.Ticker so no request leaves the test. `dividends` is what Yahoo would return.
    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def dividends(self):
            if error is not None:
                raise error
            return dividends

    return FakeTicker


@pytest.fixture
def paying_ticker(monkeypatch):
    series = pd.Series(
        [0.25, 0.26],
        index=pd.DatetimeIndex(["2025-05-12", "2025-02-10"], tz="America/New_York"),
        name="Dividends",
    )
    monkeypatch.setattr(market.yf, "Ticker", fake_yahoo(dividends=series))


def test_returns_dividends_oldest_first(paying_ticker):
    r = client.get("/market/dividends/aapl")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["count"] == 2
    assert [d["amount"] for d in body["dividends"]] == [0.26, 0.25]
    assert body["dividends"][0]["date"].startswith("2025-02-10")
    assert body["latency_ms"] >= 0


def test_no_dividends_is_404(monkeypatch):
    empty = pd.Series([], dtype=float, index=pd.DatetimeIndex([], tz="America/New_York"))
    monkeypatch.setattr(market.yf, "Ticker", fake_yahoo(dividends=empty))
    assert client.get("/market/dividends/ZZZZ").status_code == 404


def test_rate_limit_is_503(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", fake_yahoo(error=YFRateLimitError()))
    assert client.get("/market/dividends/AAPL").status_code == 503


def test_other_upstream_error_is_502_not_500(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", fake_yahoo(error=ValueError("bad payload")))
    assert client.get("/market/dividends/AAPL").status_code == 502


def test_invalid_ticker_is_422(paying_ticker):
    assert client.get("/market/dividends/bad%20ticker!").status_code == 422
