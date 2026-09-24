# Market data endpoints backed by yfinance (Lab 01).
# Yahoo Finance is an unauthenticated upstream: it rate-limits aggressively and
# returns an empty frame rather than an error for unknown symbols, so every
# handler here translates upstream failure into an explicit HTTP status.
from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field
from yfinance.exceptions import YFRateLimitError

router = APIRouter(prefix="/market", tags=["market"])

TickerParam = Annotated[
    str,
    Path(pattern=r"^[A-Za-z0-9.\-^]{1,12}$", description="Yahoo symbol, e.g. AAPL or ^GSPC"),
]


class Period(str, Enum):
    FIVE_DAYS = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    FIVE_YEARS = "5y"
    MAX = "max"


class Interval(str, Enum):
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class Quote(BaseModel):
    ticker: str
    currency: str | None = None
    price: float
    previous_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    latency_ms: int


class Bar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class History(BaseModel):
    ticker: str
    period: Period
    interval: Interval
    count: int
    bars: list[Bar]
    latency_ms: int


class Fundamentals(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    trailing_eps: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    summary: str | None = None
    latency_ms: int


class CompareRequest(BaseModel):
    tickers: list[str] = Field(min_length=2, max_length=5, examples=[["AAPL", "MSFT", "NVDA"]])
    period: Period = Period.SIX_MONTHS


class CompareRow(BaseModel):
    ticker: str
    start_price: float
    end_price: float
    return_pct: float


class CompareResponse(BaseModel):
    period: Period
    results: list[CompareRow]
    best: str
    latency_ms: int


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _rate_limited() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Upstream (Yahoo Finance) rate limit hit. Back off and retry.",
    )


def _fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        frame = yf.Ticker(ticker).history(period=period, interval=interval)
    except YFRateLimitError:
        raise _rate_limited() from None
    if frame.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No data for '{ticker}' at period={period}, interval={interval}. "
                "The symbol may be unknown, or the period/interval combination "
                "may exceed what Yahoo serves (e.g. 1h data is capped at ~2 years)."
            ),
        )
    return frame


def _optional(source: Any, key: str) -> Any:
    # yfinance raises rather than returning None when a field is absent for a symbol.
    try:
        value = source[key]
    except (KeyError, TypeError, IndexError):
        return None
    return None if pd.isna(value) else value


@router.get("/quote/{ticker}", response_model=Quote, summary="Latest price snapshot")
def get_quote(ticker: TickerParam) -> Quote:
    """Cheap snapshot via `fast_info` — one lightweight upstream call."""
    started = time.perf_counter()
    symbol = ticker.upper()

    try:
        fast = yf.Ticker(symbol).fast_info
        price = _optional(fast, "lastPrice")
    except YFRateLimitError:
        raise _rate_limited() from None

    if price is None:
        raise HTTPException(status_code=404, detail=f"Unknown or delisted symbol '{symbol}'.")

    previous = _optional(fast, "previousClose")
    change = price - previous if previous else None
    volume = _optional(fast, "lastVolume")

    return Quote(
        ticker=symbol,
        currency=_optional(fast, "currency"),
        price=price,
        previous_close=previous,
        change=change,
        change_pct=(change / previous * 100) if change is not None and previous else None,
        day_high=_optional(fast, "dayHigh"),
        day_low=_optional(fast, "dayLow"),
        volume=int(volume) if volume is not None else None,
        market_cap=_optional(fast, "marketCap"),
        latency_ms=_elapsed_ms(started),
    )


@router.get("/history/{ticker}", response_model=History, summary="OHLCV time series")
def get_history(
    ticker: TickerParam,
    period: Period = Period.SIX_MONTHS,
    interval: Interval = Interval.DAILY,
) -> History:
    """Query params are `Enum`-typed, so FastAPI rejects bad values with a 422."""
    started = time.perf_counter()
    symbol = ticker.upper()
    frame = _fetch_history(symbol, period.value, interval.value)

    bars = [
        Bar(
            timestamp=row.Index.to_pydatetime(),
            open=row.Open,
            high=row.High,
            low=row.Low,
            close=row.Close,
            volume=int(row.Volume),
        )
        for row in frame.itertuples()
    ]

    return History(
        ticker=symbol,
        period=period,
        interval=interval,
        count=len(bars),
        bars=bars,
        latency_ms=_elapsed_ms(started),
    )


@router.get("/fundamentals/{ticker}", response_model=Fundamentals, summary="Company profile")
def get_fundamentals(ticker: TickerParam) -> Fundamentals:
    """Uses `.info`, which is a much heavier upstream call than `fast_info`."""
    started = time.perf_counter()
    symbol = ticker.upper()

    try:
        info = yf.Ticker(symbol).info
    except YFRateLimitError:
        raise _rate_limited() from None

    if not info or _optional(info, "symbol") is None:
        raise HTTPException(status_code=404, detail=f"No profile for symbol '{symbol}'.")

    return Fundamentals(
        ticker=symbol,
        name=_optional(info, "longName"),
        sector=_optional(info, "sector"),
        industry=_optional(info, "industry"),
        country=_optional(info, "country"),
        website=_optional(info, "website"),
        market_cap=_optional(info, "marketCap"),
        trailing_pe=_optional(info, "trailingPE"),
        forward_pe=_optional(info, "forwardPE"),
        trailing_eps=_optional(info, "trailingEps"),
        dividend_yield=_optional(info, "dividendYield"),
        beta=_optional(info, "beta"),
        week52_high=_optional(info, "fiftyTwoWeekHigh"),
        week52_low=_optional(info, "fiftyTwoWeekLow"),
        summary=_optional(info, "longBusinessSummary"),
        latency_ms=_elapsed_ms(started),
    )


@router.post("/compare", response_model=CompareResponse, summary="Rank symbols by return")
def compare(req: CompareRequest) -> CompareResponse:
    """Request body validated by Pydantic: 2-5 symbols, known period."""
    started = time.perf_counter()

    rows: list[CompareRow] = []
    for raw in req.tickers:
        symbol = raw.upper()
        closes = _fetch_history(symbol, req.period.value, Interval.DAILY.value)["Close"]
        start_price, end_price = float(closes.iloc[0]), float(closes.iloc[-1])
        rows.append(
            CompareRow(
                ticker=symbol,
                start_price=start_price,
                end_price=end_price,
                return_pct=(end_price - start_price) / start_price * 100,
            )
        )

    rows.sort(key=lambda row: row.return_pct, reverse=True)
    return CompareResponse(
        period=req.period,
        results=rows,
        best=rows[0].ticker,
        latency_ms=_elapsed_ms(started),
    )
