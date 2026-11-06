"""Snowpark demo: the stock analysis from snowsight_demo.sql, written as Python DataFrames.

Run from snowflake-lab/:

    ../.venv/Scripts/python.exe snowpark_demo.py

Snowpark turns DataFrame code into SQL and runs it inside Snowflake, on the warehouse.
Only small results travel back to this laptop: the 170M-row view never leaves Snowflake.
"""

from snowflake.snowpark import Window
from snowflake.snowpark.functions import abs as abs_
from snowflake.snowpark.functions import col, iff, lag, lit, max_by, min_by, row_number, year
from snowflake.snowpark.functions import max as max_
from snowflake.snowpark.functions import round as round_
from snowflake.snowpark.functions import sum as sum_
from snowflake.snowpark.types import FloatType, StringType

from sf_session import get_session

SOURCE = "SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE.STOCK_PRICE_TIMESERIES"
TARGET_SCHEMA = "DEMO_DB.MARKET"
MAG7 = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]
# Before this date the ticker META was a different security (see snowsight_demo.sql, step 6).
META_LISTED = "2022-06-09"
MOVES = ["big down", "down", "flat", "up", "big up"]


def section(title: str) -> None:
    print(f"\n=== {title} {'=' * max(3, 72 - len(title))}")


def classify_move(pct: float) -> str:
    """Plain Python. Registered as a UDF below, it runs on Snowflake's servers."""
    if pct is None:
        return None
    if pct >= 5:
        return "big up"
    if pct > 0.5:
        return "up"
    if pct > -0.5:
        return "flat"
    if pct > -5:
        return "down"
    return "big down"


def pick(variable: str, name: str):
    """One pivoted column: the VALUE of a single VARIABLE (conditional aggregation)."""
    return max_(iff(col("VARIABLE") == variable, col("VALUE"), lit(None))).alias(name)


session = get_session()
session.query_tag = "snowpark-demo"  # filter on this in Snowsight > Monitoring > Query History

with session.query_history() as history:
    section("1. Connected")
    user, role, warehouse = session.sql(
        "select current_user(), current_role(), current_warehouse()"
    ).collect()[0]
    print(f"user {user} | role {role} | warehouse {warehouse}")

    section("2. A DataFrame is a lazy query, not data")
    prices = session.table(SOURCE)
    mag7 = prices.filter(
        col("TICKER").isin(MAG7)
        & ~((col("TICKER") == "META") & (col("DATE") < lit(META_LISTED)))
    )
    print("Nothing has run yet. This is the SQL Snowpark will send when we ask for results:\n")
    print(mag7.queries["queries"][-1])

    section("3. Long -> wide, one row per ticker per day")
    daily = mag7.group_by("TICKER", "DATE").agg(
        pick("all-day_high_adjusted", "HIGH"),
        pick("all-day_low_adjusted", "LOW"),
        pick("post-market_close_adjusted", "CLOSE"),
        pick("nasdaq_volume", "NASDAQ_VOLUME"),
    )
    daily.sort(col("TICKER"), col("DATE").desc()).show(5)

    section("4. Window functions: the 10 biggest one-day moves")
    by_ticker = Window.partition_by("TICKER").order_by("DATE")
    returns = daily.with_column(
        "PCT_MOVE", round_((col("CLOSE") / lag("CLOSE").over(by_ticker) - 1) * 100, 2)
    ).filter(col("PCT_MOVE").is_not_null())
    biggest = returns.with_column(
        "RANK", row_number().over(Window.order_by(abs_(col("PCT_MOVE")).desc()))
    ).filter(col("RANK") <= 10)
    biggest.select("RANK", "TICKER", "DATE", "CLOSE", "PCT_MOVE").sort("RANK").show(10)

    section("5. A Python UDF: our function runs inside Snowflake")
    # Temporary UDFs live in the session's schema, so make sure we have one of our own.
    session.sql("create database if not exists DEMO_DB").collect()
    session.sql(f"create schema if not exists {TARGET_SCHEMA}").collect()
    session.use_schema(TARGET_SCHEMA)
    classify = session.udf.register(
        classify_move,
        name="CLASSIFY_MOVE",
        input_types=[FloatType()],
        return_type=StringType(),
        replace=True,
    )
    labeled = returns.with_column("MOVE", classify(col("PCT_MOVE")))
    labeled.group_by("TICKER").agg(
        *[sum_(iff(col("MOVE") == m, 1, 0)).alias(m.upper().replace(" ", "_")) for m in MOVES]
    ).sort("TICKER").show()

    section("6. Year-by-year returns, pulled into pandas")
    yearly = (
        daily.filter(col("DATE") >= lit("2019-01-01"))
        .with_column("YEAR", year(col("DATE")))
        .group_by("TICKER", "YEAR")
        .agg(
            round_((max_by("CLOSE", "DATE") / min_by("CLOSE", "DATE") - 1) * 100, 1).alias(
                "PCT_RETURN"
            )
        )
    )
    table = yearly.to_pandas().pivot(index="YEAR", columns="TICKER", values="PCT_RETURN")
    print("% return, first to last close of each year (computed in Snowflake, shaped in pandas):\n")
    print(table.to_string())

    section("7. Write the results back as a table")
    target = f"{TARGET_SCHEMA}.MAG7_RETURNS"
    labeled.write.save_as_table(target, mode="overwrite")
    rows = session.table(target).count()
    print(f"Saved {rows:,} rows to {target}. Open it in Snowsight: Data > Databases > DEMO_DB.")

section("8. What actually ran")
print(f"{len(history.queries)} SQL statements were generated and run in Snowflake for this demo.")
print("See them in Snowsight > Monitoring > Query History, filtered by query tag 'snowpark-demo'.")

session.close()
