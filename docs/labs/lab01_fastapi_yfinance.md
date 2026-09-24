# Lab 1 — A Market Data API with FastAPI + yfinance

> **Goal:** turn a stubbed service into a real HTTP API. You will read and extend four
> endpoints in [`services/backend`](../../services/backend) that pull live market data from
> Yahoo Finance, and see the results render in the analyst dashboard.
> **Time:** ~75–90 min · **Prereqs:** [Lab 0](lab00_git_workflow.md), Python 3.12, Poetry 2.x, Docker (optional)
> **You produce:** one merged PR adding an endpoint of your own.

By the end you can: structure a FastAPI service with routers, choose between path / query /
body parameters, enforce contracts with Pydantic response models, validate closed sets with
`Enum`, and translate a flaky third-party API into honest HTTP status codes.

---

## 0. Why a service and not a notebook

You could get the same numbers in three lines of a notebook:

```python
import yfinance as yf
yf.Ticker("AAPL").history(period="6mo")
```

A notebook is where you *discover*. A service is where the rest of the system *consumes*.
The difference is the contract: a typed request in, a typed response out, a documented
failure mode, and a latency you can measure. Everything downstream in this repo — the
feature store, the RAG retriever, the agent's tools — talks over that kind of seam.

This lab lives in `services/backend` because that is the orchestration layer
([`ARCHITECTURE.md`](../../ARCHITECTURE.md) §1). In a later release the market-data pull
moves out to [`services/ingestion/market_data`](../../services/ingestion/market_data) and
the backend calls *it* instead. Starting in the backend keeps the first lab to one service.

---

## 1. Run it

Dependencies live in the **root** `pyproject.toml` and are pinned by `poetry.lock`,
so install once from the repo root:

```bash
poetry install
cd services/backend
poetry run uvicorn app.main:app --reload --port 8000
```

Confirm it's alive, then open the interactive docs:

```bash
curl http://localhost:8000/health
```

Open **http://localhost:8000/docs**. FastAPI generated that page from your type hints —
no annotations, no docs. Keep this tab open; you will use it throughout.

---

## 2. yfinance in five minutes

`yfinance` scrapes Yahoo Finance. It is free, unauthenticated, and *not* a guaranteed
service — which makes it an honest teaching target. Three calls matter:

| Call | Returns | Cost |
|---|---|---|
| `Ticker("AAPL").fast_info` | price, prev close, day high/low, market cap | **cheap** — one small request |
| `Ticker("AAPL").history(period=, interval=)` | OHLCV `DataFrame` | moderate |
| `Ticker("AAPL").info` | ~150 profile/valuation fields | **expensive** — heavy payload |

Two behaviours you must design around:

- **Unknown symbols do not raise.** `Ticker("ZZZZNOPE").history()` returns an *empty*
  DataFrame. If you forward that blindly, your API returns `200 OK` with zero rows and
  your caller cannot tell "no data" from "bad symbol".
- **Yahoo rate-limits hard.** Under load `yfinance` raises `YFRateLimitError`. Unhandled,
  that is a `500` — which tells the caller *you* are broken when in fact your upstream is.

Both are handled in [`app/market.py`](../../services/backend/app/market.py). Read on.

---

## 3. Routers — keeping `main.py` small

All four endpoints live in their own module and attach to the app as a unit:

```python
# app/market.py
router = APIRouter(prefix="/market", tags=["market"])

# app/main.py
from app.market import router as market_router
app.include_router(market_router)
```

`prefix` means every route below is automatically under `/market`. `tags` groups them
into their own section in `/docs`. When market data later moves to its own service, this
file moves with it — that is the point of the split.

---

## 4. Endpoint 1 — path parameters

```python
@router.get("/quote/{ticker}", response_model=Quote)
def get_quote(ticker: TickerParam) -> Quote:
```

Try it:

```bash
curl http://localhost:8000/market/quote/AAPL
```

Two things are doing real work here.

**`TickerParam` validates before your code runs.**

```python
TickerParam = Annotated[str, Path(pattern=r"^[A-Za-z0-9.\-^]{1,12}$")]
```

A ticker is user input crossing a trust boundary. The pattern rejects junk at the edge, so
the handler body only ever sees something ticker-shaped:

```bash
curl -i "http://localhost:8000/market/quote/'; DROP TABLE--"      # 422, never reaches yfinance
```

**`response_model=Quote` is a contract, not decoration.** It drops fields you didn't
declare, coerces types, and publishes the schema in OpenAPI. If yfinance adds a field
tomorrow, your response shape does not silently change.

Notice the response carries `latency_ms`. Every endpoint in this repo reports what it cost
to serve — that is what feeds the standing unit-economics table
([`docs/economics/`](../economics/unit_economics_template.md)).

---

## 5. Endpoint 2 — query parameters and closed sets

Path parameters identify a resource; **query parameters modify the view of it**. Period
and interval are modifiers, so they are query params:

```bash
curl "http://localhost:8000/market/history/AAPL?period=1mo&interval=1d"
```

Both are typed as `Enum` rather than `str`:

```python
class Interval(str, Enum):
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"
```

That single choice buys you three things: a `422` with a list of valid options when
someone sends `interval=banana`, a **dropdown** in `/docs` instead of a free-text box, and
an exhaustiveness guarantee inside the handler. Prove it:

```bash
curl -i "http://localhost:8000/market/history/AAPL?interval=banana"
```

> **Yahoo's own constraints still apply.** Intraday data is capped by lookback —
> `interval=1h` with `period=5y` returns nothing. The handler turns that empty frame into
> a `404` that *names the combination*, instead of an empty `200`.

---

## 6. Endpoint 3 — when the upstream call is expensive

```bash
curl http://localhost:8000/market/fundamentals/AAPL
```

Compare the `latency_ms` on this response against `/market/quote/AAPL`. Same library,
same symbol, very different cost — `fast_info` fetches a small quote blob, `.info` pulls
the entire profile. This asymmetry is the whole reason the two are separate endpoints:
a caller that only needs a price should not pay for a business summary.

That instinct — *make the caller's cost proportional to what they asked for* — is the
habit this course grades in every release.

---

## 7. Endpoint 4 — request bodies

Use a body when the input is structured, or too big for a URL:

```bash
curl -X POST http://localhost:8000/market/compare \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "NVDA"], "period": "6mo"}'
```

The body is a Pydantic model, so the constraints are declared rather than checked by hand:

```python
class CompareRequest(BaseModel):
    tickers: list[str] = Field(min_length=2, max_length=5)
    period: Period = Period.SIX_MONTHS
```

`min_length=2` (comparing one thing is meaningless) and `max_length=5` (each symbol is a
separate upstream call — this is a crude rate-limit guard). Send six tickers and read the
error; you never wrote that validation.

---

## 8. Failure is part of the interface

The status code *is* the contract. This service commits to three:

| Situation | Status | Why not something else |
|---|---|---|
| Malformed ticker, unknown `interval`, 6 tickers | **422** | Caller's fault; the request never should have been sent |
| Symbol valid-looking but Yahoo has no data | **404** | Caller's fault, but only discoverable upstream |
| `YFRateLimitError` from Yahoo | **503** | *Not* the caller's fault — a `500` would blame the wrong party, and `503` signals "retry later" |

The translation is deliberately in one place:

```python
def _fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        frame = yf.Ticker(ticker).history(period=period, interval=interval)
    except YFRateLimitError:
        raise _rate_limited() from None          # -> 503
    if frame.empty:
        raise HTTPException(status_code=404, detail=...)
    return frame
```

**Rule of thumb:** validate at the boundary — user input and third-party responses. Do
not sprinkle defensive checks through internal code that you control.

---

## 9. See it in the dashboard

The endpoints are wired into the Streamlit frontend's **Market** tab:

```bash
cd services/frontend
poetry run streamlit run app/app.py
```

Open **http://localhost:8501** and pick the *Market (Lab 01)* tab. Change the ticker and
period; the candlestick chart, the metric row, and the fundamentals panel are all reading
the JSON you just curled. Note the per-call latency printed under the chart.

> The frontend calls the backend **directly** via `BACKEND_URL`. The architecture puts a
> gateway in between ([`ARCHITECTURE.md`](../../ARCHITECTURE.md) §1) — wiring that up,
> with auth and audit, is later-release work.

---

## 10. Run the whole thing in Docker

```bash
cp .env.example .env            # compose reads env_file: .env
docker compose up --build backend frontend gateway
```

Dashboard on **http://localhost:8501**, API on **http://localhost:8000/docs**.
`docker compose down` when finished.

---

## 11. Graded exercise (your deliverable)

Branch off `main` as `feat/lab1-<your-handle>` and add **one new endpoint** to
`services/backend/app/market.py`. Pick one:

| Endpoint | yfinance call | What it exercises |
|---|---|---|
| `GET /market/dividends/{ticker}` | `Ticker(t).dividends` | Series → typed list |
| `GET /market/news/{ticker}?limit=` | `Ticker(t).news` | optional query param with a bound |
| `GET /market/actions/{ticker}` | `Ticker(t).actions` | splits + dividends in one model |

Your endpoint must:

1. Declare a **Pydantic `response_model`** — no bare `dict` returns.
2. Reuse **`TickerParam`** for the symbol.
3. Return **`latency_ms`**, like its neighbours.
4. Return **404** when the upstream result is empty and **503** on `YFRateLimitError`.
5. Appear correctly in `/docs` under the `market` tag.

Then open a PR with the template filled, including the **AI Engineering Log**. In the PR
description, paste:

- the `curl` command and its response, and
- the `latency_ms` you measured for your endpoint vs `/market/quote/`.

**Bonus (recommended):** add a 60-second TTL cache in front of the yfinance calls and
report the before/after `latency_ms` on a repeated request. You will hit Yahoo's rate
limit during this lab — caching is the fix, and it is the first piece of FinOps work in
the course.

---

## 12. Troubleshooting

- **`YFRateLimitError` / everything returns 503** → you are genuinely rate-limited. Wait a
  few minutes and request fewer symbols. This is why the bonus exercise exists.
- **`ModuleNotFoundError: app`** → run `uvicorn` from `services/backend`, not the repo root.
- **`404` with a valid ticker** → check your period/interval combination (see §5).
- **`env file .env not found`** → `cp .env.example .env` before `docker compose up`.
- **Dashboard says "backend offline"** → the backend isn't running, or `BACKEND_URL` is
  wrong. Outside Docker it should be `http://localhost:8000`.
- **Empty chart but a working quote** → the symbol has no history at that interval; try
  `period=1mo&interval=1d`.
- **Non-US symbols** need their exchange suffix: `RELIANCE.NS`, `SHOP.TO`, `BMW.DE`.

---

## 13. Cheat sheet

```python
# path param (identifies) vs query param (modifies) vs body (structured input)
@router.get("/quote/{ticker}")                  # /market/quote/AAPL
def q(ticker: TickerParam): ...

@router.get("/history/{ticker}")                # ?period=1mo&interval=1d
def h(ticker: TickerParam, period: Period = Period.SIX_MONTHS): ...

@router.post("/compare")                        # JSON body
def c(req: CompareRequest): ...
```

```python
# typed response, published to OpenAPI, extra fields dropped
@router.get("/quote/{ticker}", response_model=Quote)

# closed set -> automatic 422 + a dropdown in /docs
class Interval(str, Enum):
    DAILY = "1d"

# boundary translation
raise HTTPException(status_code=404, detail="...")
```

```bash
# the four endpoints
curl localhost:8000/market/quote/AAPL
curl "localhost:8000/market/history/AAPL?period=1mo&interval=1d"
curl localhost:8000/market/fundamentals/AAPL
curl -X POST localhost:8000/market/compare -H "Content-Type: application/json" \
     -d '{"tickers":["AAPL","MSFT"],"period":"1y"}'
```

### Glossary

**router** a group of related routes mounted onto an app · **path param** part of the URL
path, identifies a resource · **query param** after `?`, modifies the view · **response
model** the Pydantic type FastAPI serialises and documents · **422** validation failed ·
**503** upstream unavailable, retry later.
