"""
Thin HTTP client for the FIS backend's `/market/*` endpoints, shared by the
`fis_backend_*` DAGs.

The DAGs deliberately call the backend over HTTP instead of importing yfinance
themselves: the backend owns the upstream (Yahoo) and its error translation, and
Airflow just schedules calls against it. The one thing this module adds is the
mapping from HTTP status to Airflow's retry semantics:

* **503** (backend says Yahoo rate-limited us) and connection errors / timeouts
  (backend down or restarting) are *transient* -> raise a normal exception so the
  task retries with backoff.
* **404** (unknown symbol) and **422** (bad period/interval/body) are *permanent*
  -> `AirflowFailException`, which skips the remaining retries. Retrying cannot
  fix a typo.

This folder is listed in `dags/.airflowignore`, so the dag-processor does not try
to parse it for DAGs; it is still importable because `dags/` is on `sys.path`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from airflow.sdk.exceptions import AirflowFailException

log = logging.getLogger(__name__)

# The backend runs in the *main* compose project and Airflow in `fis-airflow`, so
# they share no Docker network. `host.docker.internal` routes back to the host,
# where the backend publishes :8000. Override with FIS_BACKEND_URL if you run the
# backend elsewhere.
BACKEND_URL = os.environ.get("FIS_BACKEND_URL", "http://host.docker.internal:8000").rstrip("/")

# `/market/fundamentals` uses yfinance's heavy `.info` call and can take 10s+.
DEFAULT_TIMEOUT_S = 60

PERMANENT_STATUSES = {400, 404, 422}


class BackendUnavailable(RuntimeError):
    """Transient failure - let Airflow retry."""


def _request(method: str, path: str, **kwargs: Any) -> dict:
    url = f"{BACKEND_URL}{path}"
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT_S)
    try:
        response = requests.request(method, url, **kwargs)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise BackendUnavailable(f"{method} {url} failed: {exc}") from exc

    if response.status_code in PERMANENT_STATUSES:
        raise AirflowFailException(
            f"{method} {url} -> {response.status_code}: {_detail(response)}"
        )
    if response.status_code >= 400:
        # 503 from the backend's rate-limit handler, or any 5xx.
        raise BackendUnavailable(
            f"{method} {url} -> {response.status_code}: {_detail(response)}"
        )
    return response.json()


def _detail(response: requests.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text[:500]


def is_healthy() -> bool:
    """True when `/health` answers 200. Never raises - used by sensors."""
    try:
        return requests.get(f"{BACKEND_URL}/health", timeout=5).ok
    except requests.RequestException as exc:
        log.info("Backend not reachable at %s: %s", BACKEND_URL, exc)
        return False


def get_quote(ticker: str) -> dict:
    return _request("GET", f"/market/quote/{ticker}")


def get_history(ticker: str, period: str = "5d", interval: str = "1d") -> dict:
    return _request(
        "GET", f"/market/history/{ticker}", params={"period": period, "interval": interval}
    )


def get_fundamentals(ticker: str) -> dict:
    return _request("GET", f"/market/fundamentals/{ticker}")


def compare(tickers: list[str], period: str = "6mo") -> dict:
    return _request("POST", "/market/compare", json={"tickers": tickers, "period": period})
