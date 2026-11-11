# FIS review rules

The rulebook the **code reviewer** ([`.github/workflows/fis-code-review.md`](workflows/fis-code-review.md))
checks every pull request against. People write and change these rules. The reviewer only applies them.

How the reviewer uses this file:

- It checks **only the lines a pull request adds or changes**, never the whole codebase.
- A rule is reported as **pass**, **fail** or **n/a** (the PR touches nothing the rule covers).
- Each failure must point at a `file:line` in the PR and quote the rule ID.
- If a rule is ambiguous for a change, the reviewer reports it as `n/a` and says why. It never guesses a failure.

Exempt from all rules: `services/backend/app/demo.py`, `services/frontend/app/test.py`,
`services/frontend/app/demo_llm.py` (scratch files), and the stub endpoints already in
`services/backend/app/main.py` (`/health`, `/`, `/ask`) until R2 replaces them.

To add a rule: give it the next free ID in its section, write it as **one checkable sentence**,
and say where the existing code shows the pattern. A rule that a reviewer cannot check by reading
the diff (for example "code is clean") does not belong here.

---

## Backend: `services/backend/app/`

| ID | Rule | The pattern to copy |
|---|---|---|
| **B1** | Every new or changed endpoint declares `response_model=` with a Pydantic model. No endpoint returns a bare `dict`. | `@router.get("/quote/{ticker}", response_model=Quote, ...)` in `market.py` |
| **B2** | A ticker in a URL path uses the shared `TickerParam` type, not a plain `str`. | `def get_quote(ticker: TickerParam)` in `market.py`; `get_ticker_facts` in `facts.py` |
| **B3** | An endpoint that calls an upstream service (yfinance, the SEC) returns `latency_ms` in its response model. | `Quote.latency_ms`, `TickerFacts.latency_ms` |
| **B4** | Upstream failures become an explicit `HTTPException`: 404 for an unknown symbol or empty result, 503 when rate-limited or not configured, 502 when the upstream returned an error. An upstream exception must never escape as a 500. | `except YFRateLimitError` → 503 in `market.py`; 502/503/404 in `facts.py` |
| **B5** | A new endpoint ships with at least one test in `services/backend/tests/` that uses `TestClient`. Tests must not call the real internet: fake the upstream with `monkeypatch`. | `tests/test_facts.py` (`sec_calls` fixture) |

## Frontend: `services/frontend/app/`

| ID | Rule | The pattern to copy |
|---|---|---|
| **F1** | The backend and gateway addresses come only from `BACKEND_URL` / `GATEWAY_URL` (`os.getenv`). No other `http://localhost…` or hard-coded host in new code. | `BACKEND = os.getenv("BACKEND_URL", ...)` in `app.py` |
| **F2** | Data the dashboard displays is loaded through `fetch()`, so a failure is shown with `st.error` / `st.warning` instead of crashing the page. A status ping may call `requests` directly, but only inside `try/except` with a fallback message. | `fetch()` in `app.py`; the sidebar health pings |
| **F3** | Every `requests` call sets `timeout=`. | `requests.get(..., timeout=30)` in `fetch()` |

## General: any file

| ID | Rule | The pattern to copy |
|---|---|---|
| **G1** | No secrets, tokens, passwords, API keys or personal emails in code, and no `.env`, `.snowflake/`, `*.pem`, `*.key` or generated data files (`data/raw/`, `*.duckdb`). | `.gitignore` |
| **G2** | The pull request description names the task it completes, as `Task: #<issue number>`, and that issue has the `task` label. | `.github/pull_request_template.md` |
