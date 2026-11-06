/* =====================================================================
   Snowsight demo: 8 years of stock prices, zero data loading
   ---------------------------------------------------------------------
   Data: SNOWFLAKE_CURATED_DATA_FREE, a free Snowflake Marketplace share.
         Nobody loaded anything: the provider's data is shared into our
         account and we query it in place.

   How to run: Snowsight > Projects > Workspaces (or Worksheets) > new SQL file,
   paste this file, put the cursor inside one statement and press
   Ctrl+Enter to run just that statement. Work top to bottom.
   ===================================================================== */


-- 0. Context: which role, which compute, which data -------------------
USE ROLE ACCOUNTADMIN;          -- fine for a personal trial; use a narrower role for students
USE WAREHOUSE COMPUTE_WH;       -- compute is separate from storage: this is the "engine"
USE SCHEMA SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE;


-- 1. How big is it? ---------------------------------------------------
-- ~170 million rows, answered in a couple of seconds on an X-Small warehouse.
SELECT COUNT(*) AS row_count
FROM STOCK_PRICE_TIMESERIES;




-- 2. What does a row look like? ---------------------------------------
-- "Long" format: one row per ticker, per variable, per day.
SELECT *
FROM STOCK_PRICE_TIMESERIES
WHERE ticker = 'AAPL'
ORDER BY date DESC, variable
LIMIT 10;

SELECT variable, variable_name, COUNT(*) AS row_count,
       MIN(date) AS first_date, MAX(date) AS last_date
FROM STOCK_PRICE_TIMESERIES
GROUP BY variable, variable_name
ORDER BY variable;


-- 3. Chart it: Apple's adjusted close since 2018 ----------------------
-- After it runs, click "Chart" above the results: Line, X = DATE, Y = CLOSE.
SELECT date, value AS close
FROM STOCK_PRICE_TIMESERIES
WHERE ticker = 'AAPL'
  AND variable = 'post-market_close_adjusted'
ORDER BY date;


-- 4. Why "adjusted" matters: NVIDIA's 10-for-1 split on 2024-06-10 -----
-- The raw close drops ~90% overnight. The adjusted close does not.
SELECT date,
       MAX(IFF(variable = 'post-market_close',          value, NULL)) AS close_raw,
       MAX(IFF(variable = 'post-market_close_adjusted', value, NULL)) AS close_adjusted
FROM STOCK_PRICE_TIMESERIES
WHERE ticker = 'NVDA'
  AND variable IN ('post-market_close', 'post-market_close_adjusted')
  AND date BETWEEN '2024-06-03' AND '2024-06-14'
GROUP BY date
ORDER BY date;


-- 5. Long -> wide: one row per ticker per day -------------------------
-- The shape analysts (and pandas) want. Conditional aggregation = a pivot.
SELECT ticker, date,
       MAX(IFF(variable = 'all-day_high_adjusted',      value, NULL)) AS high,
       MAX(IFF(variable = 'all-day_low_adjusted',       value, NULL)) AS low,
       MAX(IFF(variable = 'post-market_close_adjusted', value, NULL)) AS close,
       MAX(IFF(variable = 'nasdaq_volume',              value, NULL)) AS nasdaq_volume
FROM STOCK_PRICE_TIMESERIES
WHERE ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA')
GROUP BY ticker, date
ORDER BY ticker, date;


-- 6. Window functions: the 10 biggest one-day moves -------------------
-- LAG = yesterday's close. QUALIFY filters on a window function (Snowflake SQL).
WITH closes AS (
    SELECT ticker, date, value AS close
    FROM STOCK_PRICE_TIMESERIES
    WHERE ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA')
      AND variable = 'post-market_close_adjusted'
),
moves AS (
    SELECT ticker, date, close,
           close / LAG(close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS daily_return
    FROM closes
)
SELECT ticker, date, ROUND(close, 2) AS close, ROUND(daily_return * 100, 2) AS pct_move
FROM moves
WHERE daily_return IS NOT NULL
QUALIFY ROW_NUMBER() OVER (ORDER BY ABS(daily_return) DESC) <= 10
ORDER BY ABS(daily_return) DESC;

-- META +1404% on 2022-06-09? That never happened. Ticker reuse:
--   * 2021-06-30 .. 2022-01-28: "META" was the Roundhill Ball Metaverse ETF (~$12),
--     which then moved to ticker METV.
--   * Facebook traded as FB and only became META on 2022-06-09.
-- LAG compared Meta's first close (183.10) with the ETF's last close in January (12.17).
-- Lesson: a ticker is not a company. Always check where a series really starts.
SELECT date, value AS close
FROM STOCK_PRICE_TIMESERIES
WHERE ticker = 'META'
  AND variable = 'post-market_close_adjusted'
  AND date BETWEEN '2022-01-24' AND '2022-06-14'
ORDER BY date;

-- 6b. Same query, keeping only Meta Platforms' rows for META ----------
WITH closes AS (
    SELECT ticker, date, value AS close
    FROM STOCK_PRICE_TIMESERIES
    WHERE ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA')
      AND variable = 'post-market_close_adjusted'
      AND NOT (ticker = 'META' AND date < '2022-06-09')
),
moves AS (
    SELECT ticker, date, close,
           close / LAG(close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS daily_return
    FROM closes
)
SELECT ticker, date, ROUND(close, 2) AS close, ROUND(daily_return * 100, 2) AS pct_move
FROM moves
WHERE daily_return IS NOT NULL
QUALIFY ROW_NUMBER() OVER (ORDER BY ABS(daily_return) DESC) <= 10
ORDER BY ABS(daily_return) DESC;


-- 7. Year-by-year performance (first to last close of each year) ------
-- Chart: Bar, X = YEAR, Y = PCT_RETURN, Series = TICKER.
SELECT ticker,
       YEAR(date) AS year,
       ROUND((MAX_BY(value, date) / MIN_BY(value, date) - 1) * 100, 1) AS pct_return
FROM STOCK_PRICE_TIMESERIES
WHERE ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA')
  AND variable = 'post-market_close_adjusted'
  AND NOT (ticker = 'META' AND date < '2022-06-09')
  AND date >= '2019-01-01'
GROUP BY ticker, year
ORDER BY year, ticker;


-- 8. Result cache -----------------------------------------------------
-- Run query 7 again. It returns instantly: open "Query details" / Query Profile
-- and it shows QUERY RESULT REUSE (no warehouse time, no credits).


-- 9. Make it ours: copy the 7 tickers into our own database -----------
-- Shared data is read-only, so we materialize a small table we control.
-- Note: CREATE DATABASE / CREATE SCHEMA also switch your worksheet's context to the
-- new schema, so from here on the share is referenced by its full name.
CREATE DATABASE IF NOT EXISTS DEMO_DB;
CREATE SCHEMA IF NOT EXISTS DEMO_DB.MARKET;

CREATE OR REPLACE TABLE DEMO_DB.MARKET.MAG7_DAILY AS
SELECT ticker, date,
       MAX(IFF(variable = 'all-day_high_adjusted',      value, NULL)) AS high,
       MAX(IFF(variable = 'all-day_low_adjusted',       value, NULL)) AS low,
       MAX(IFF(variable = 'post-market_close_adjusted', value, NULL)) AS close,
       MAX(IFF(variable = 'nasdaq_volume',              value, NULL)) AS nasdaq_volume
FROM SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE.STOCK_PRICE_TIMESERIES
WHERE ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA')
  AND NOT (ticker = 'META' AND date < '2022-06-09')
GROUP BY ticker, date;

SELECT ticker, COUNT(*) AS trading_days, MIN(date) AS first_date, MAX(date) AS last_date
FROM DEMO_DB.MARKET.MAG7_DAILY
GROUP BY ticker
ORDER BY ticker;


-- 10. Zero-copy clone: an instant "dev copy" --------------------------
-- No data is copied: the clone points at the same micro-partitions until one side changes.
CREATE OR REPLACE TABLE DEMO_DB.MARKET.MAG7_DAILY_DEV CLONE DEMO_DB.MARKET.MAG7_DAILY;

SELECT COUNT(*) AS dev_rows FROM DEMO_DB.MARKET.MAG7_DAILY_DEV;


-- 11. Time Travel: "accidentally" delete Tesla, then look back in time -
DELETE FROM DEMO_DB.MARKET.MAG7_DAILY WHERE ticker = 'TSLA';
SET delete_qid = LAST_QUERY_ID();          -- remember which statement did the damage

SELECT ticker, COUNT(*) AS trading_days    -- TSLA is gone
FROM DEMO_DB.MARKET.MAG7_DAILY
GROUP BY ticker ORDER BY ticker;

SELECT ticker, COUNT(*) AS trading_days    -- the table as it was just before the DELETE
FROM DEMO_DB.MARKET.MAG7_DAILY BEFORE (STATEMENT => $delete_qid)
GROUP BY ticker ORDER BY ticker;

INSERT INTO DEMO_DB.MARKET.MAG7_DAILY      -- put it back from the past
SELECT * FROM DEMO_DB.MARKET.MAG7_DAILY BEFORE (STATEMENT => $delete_qid)
WHERE ticker = 'TSLA';


-- 12. UNDROP: dropped tables are recoverable too ----------------------
DROP TABLE DEMO_DB.MARKET.MAG7_DAILY_DEV;
UNDROP TABLE DEMO_DB.MARKET.MAG7_DAILY_DEV;

SELECT COUNT(*) AS dev_rows_after_undrop FROM DEMO_DB.MARKET.MAG7_DAILY_DEV;


-- 13. After running snowpark_demo.py ----------------------------------
-- The Python script writes DEMO_DB.MARKET.MAG7_RETURNS. Query it here, and open
-- Monitoring > Query History filtered by query tag 'snowpark-demo' to see the SQL
-- that Snowpark generated from the DataFrame code.
-- SELECT * FROM DEMO_DB.MARKET.MAG7_RETURNS ORDER BY ABS(pct_move) DESC LIMIT 20;


-- Cleanup (when you are done with the demo) ---------------------------
-- DROP DATABASE IF EXISTS DEMO_DB;
