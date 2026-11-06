-- A Snowflake-managed MCP server with two tools:
--   stock_sql             read-only SQL over daily stock prices     ("what happened")
--   earnings_call_search  keyword search over earnings-call text    ("why it happened")
-- Snowflake hosts it; clients connect over HTTP with a PAT.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS DEMO_DB;
CREATE SCHEMA IF NOT EXISTS DEMO_DB.MARKET;


-- 1. Passages: one row per paragraph of each Mag-7 earnings call since 2023 -----
-- The share stores each call as one row with the whole transcript in a JSON column.
-- FLATTEN turns its paragraphs into rows and attaches the speaker's name and role.
CREATE OR REPLACE TABLE DEMO_DB.MARKET.CALL_PASSAGES AS
WITH calls AS (
    SELECT primary_ticker, company_name, event_title, event_timestamp, transcript
    FROM SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE.COMPANY_EVENT_TRANSCRIPT_ATTRIBUTES
    WHERE primary_ticker IN ('AAPL', 'MSFT', 'NVDA', 'GOOG', 'AMZN', 'META', 'TSLA')
      AND event_type = 'Earnings Call'
      AND transcript_type = 'SPEAKERS_ANNOTATED'
      AND event_timestamp >= '2023-01-01'
    -- each call appears more than once in the share: keep one copy
    QUALIFY ROW_NUMBER() OVER (PARTITION BY primary_ticker, event_timestamp ORDER BY updated_at DESC) = 1
)
SELECT IFF(c.primary_ticker = 'GOOG', 'GOOGL', c.primary_ticker) AS ticker,   -- match the price data
       c.company_name,
       c.event_timestamp::DATE                    AS event_date,
       c.event_title,
       p.index                                    AS paragraph_num,
       sp.value:speaker_data:name::STRING         AS speaker_name,
       sp.value:speaker_data:role::STRING         AS speaker_role,
       p.value:text::STRING                       AS text
FROM calls c,
     LATERAL FLATTEN(input => c.transcript:paragraphs) p,
     LATERAL FLATTEN(input => c.transcript:speaker_mapping) sp
WHERE sp.value:speaker = p.value:speaker
  AND LENGTH(p.value:text::STRING) >= 200;      -- skip "thank you, next question" lines

SELECT ticker, COUNT(DISTINCT event_date) AS calls, COUNT(*) AS passages
FROM DEMO_DB.MARKET.CALL_PASSAGES
GROUP BY ticker ORDER BY ticker;


-- 2. Search procedure: the tool's logic, in plain SQL ---------------------------
-- Full-text SEARCH() (not Cortex AI): passages containing all the keywords,
-- optionally within a date window, newest first.
CREATE OR REPLACE PROCEDURE DEMO_DB.MARKET.SEARCH_EARNINGS_CALLS(
    ticker    STRING,
    keywords  STRING,
    from_date STRING DEFAULT NULL,
    to_date   STRING DEFAULT NULL)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
DECLARE
  result VARIANT;
BEGIN
  SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
           'ticker', cp.ticker, 'event_date', cp.event_date, 'event_title', cp.event_title,
           'speaker', cp.speaker_name, 'role', cp.speaker_role, 'text', cp.text))
    INTO :result
  FROM (
    SELECT * FROM DEMO_DB.MARKET.CALL_PASSAGES cp
    WHERE cp.ticker = UPPER(:ticker)
      AND SEARCH(cp.text, :keywords, SEARCH_MODE => 'AND')
      AND cp.event_date BETWEEN COALESCE(TRY_TO_DATE(:from_date), '2000-01-01'::DATE)
                            AND COALESCE(TRY_TO_DATE(:to_date),   '2100-01-01'::DATE)
    ORDER BY cp.event_date DESC, cp.paragraph_num
    LIMIT 8
  ) cp;
  RETURN COALESCE(result, ARRAY_CONSTRUCT());
END;
$$;

CALL DEMO_DB.MARKET.SEARCH_EARNINGS_CALLS('NVDA', 'data center', '2023-05-01', '2023-05-31');

-- On a paid account, semantic search (by meaning, not keywords) is one statement away:
--   CREATE CORTEX SEARCH SERVICE DEMO_DB.MARKET.EARNINGS_CALL_SEARCH
--     ON text ATTRIBUTES ticker, event_date WAREHOUSE = COMPUTE_WH TARGET_LAG = '7 days'
--     AS SELECT text, ticker, event_date, event_title, speaker_name, speaker_role
--        FROM DEMO_DB.MARKET.CALL_PASSAGES;
-- and the tool below becomes type "CORTEX_SEARCH_SERVICE_QUERY" with that identifier.
-- (Trial accounts get: "AI function EMBED_TEXT_768 is not available for trial accounts.")


-- 3. The MCP server: two tools ----------------------------------------------
CREATE OR REPLACE MCP SERVER DEMO_DB.MARKET.STOCKS_MCP
  FROM SPECIFICATION $$
    tools:
      - name: "stock_sql"
        type: "SYSTEM_EXECUTE_SQL"
        title: "Query stock prices (read-only SQL)"
        description: >
          Runs a read-only Snowflake SQL query. Daily stock prices are in
          SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE.STOCK_PRICE_TIMESERIES with columns
          TICKER, VARIABLE, DATE, VALUE (one row per ticker, variable and day, 2018-05-01 to 2026-08-06).
          Use VARIABLE = 'post-market_close_adjusted' for the split-adjusted after-hours close
          and 'nasdaq_volume' for volume. The ticker META only refers to Meta Platforms from 2022-06-09 onward.
        config:
          read_only: true
          warehouse: "COMPUTE_WH"

      - name: "earnings_call_search"
        type: "GENERIC"
        identifier: "DEMO_DB.MARKET.SEARCH_EARNINGS_CALLS"
        title: "Search earnings-call transcripts"
        description: >
          Keyword search over earnings-call transcripts from 2023 onward for AAPL, MSFT, NVDA,
          GOOGL, AMZN, META and TSLA. Returns up to 8 paragraphs that contain ALL the keywords,
          newest first, with event_date, event_title, speaker and role. Use 1-3 keywords.
          To explain a price move, set from_date and to_date to a window around the move's date.
        config:
          type: "procedure"
          warehouse: "COMPUTE_WH"
          input_schema:
            type: "object"
            properties:
              ticker:
                type: "string"
                description: "Stock ticker, e.g. NVDA"
              keywords:
                type: "string"
                description: "1-3 keywords that must all appear, e.g. data center"
              from_date:
                type: "string"
                description: "Optional start date, YYYY-MM-DD"
              to_date:
                type: "string"
                description: "Optional end date, YYYY-MM-DD"
  $$;

SHOW MCP SERVERS IN SCHEMA DEMO_DB.MARKET;

-- Clients connect to:
-- https://<org>-<account>.snowflakecomputing.com/api/v2/databases/DEMO_DB/schemas/MARKET/mcp-servers/STOCKS_MCP

-- Cleanup:
-- DROP MCP SERVER DEMO_DB.MARKET.STOCKS_MCP;
-- DROP PROCEDURE DEMO_DB.MARKET.SEARCH_EARNINGS_CALLS(STRING, STRING, STRING, STRING);
-- DROP TABLE DEMO_DB.MARKET.CALL_PASSAGES;
