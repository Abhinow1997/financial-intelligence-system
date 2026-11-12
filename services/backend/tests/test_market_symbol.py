import yfinance as yf
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_symbol_is_returned_upper_case_without_upstream_call(monkeypatch):
    # Any upstream call fails the test: the endpoint must not reach Yahoo Finance.
    def no_upstream(symbol):
        raise AssertionError(f"unexpected upstream call for {symbol}")

    monkeypatch.setattr(yf, "Ticker", no_upstream)
    r = client.get("/market/symbol/aapl")
    assert r.status_code == 200
    assert r.json() == {"ticker": "AAPL"}


def test_invalid_symbol_is_rejected(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", lambda symbol: 1 / 0)
    assert client.get("/market/symbol/BAD%20TICKER").status_code == 422
