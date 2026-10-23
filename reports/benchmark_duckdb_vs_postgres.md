# DuckDB vs Postgres: query benchmark on 3.55 million SEC numbers

Run on 2026-10-22. Raw results: [`benchmark_duckdb_vs_postgres.json`](benchmark_duckdb_vs_postgres.json).

## Summary

The same 3,551,230-row table was loaded into DuckDB and Postgres and queried with identical SQL.

- **Analytical queries:** DuckDB was faster on all five, by **3.7x to 188x**. These queries scan, group, count or summarise the whole table.
- **Single-company lookup:** Postgres was **143x faster** (0.10 ms against 14.6 ms), because its index goes straight to the few matching rows.
- **Loading:** DuckDB wrote the table in **3.1 s**; Postgres took **67.8 s**, including two indexes and `ANALYZE`.
- **Storage:** DuckDB stored it in **183 MB**, the whole `facts.duckdb` file. Postgres used **1,296 MB**: a 1,200 MB table plus indexes.
- **Correctness:** both engines returned the same answers for all 6 queries.

**Conclusion:** use DuckDB for scanning and summarising large data, and Postgres for fetching a few rows by key and for many users writing at once. The project uses both for those reasons.

## Results

Median of 5 runs, after one warm-up run.

| # | Query | Type | DuckDB | Postgres | Faster |
|---|---|---|---:|---:|---|
| 1 | Count every number | full table | 0.61 ms | 97.41 ms | DuckDB 159.4x |
| 2 | Top 10 tags by count | group by | 33.44 ms | 255.50 ms | DuckDB 7.6x |
| 3 | Largest annual revenue per company | filter + group by | 44.21 ms | 163.68 ms | DuckDB 3.7x |
| 4 | Distinct companies and tags | distinct count | 28.89 ms | 5,423.10 ms | DuckDB 187.7x |
| 5 | Count and average value per form and unit | two-column group by | 19.21 ms | 498.82 ms | DuckDB 26.0x |
| 6 | One company's revenue history | index lookup | 14.57 ms | 0.10 ms | Postgres 142.9x |

### Loading and storage

| | DuckDB | Postgres |
|---|---:|---:|
| Write the 3,551,230 rows | 3.1 s | 67.8 s (includes 2 indexes and `ANALYZE`) |
| Space on disk | 183 MB (the whole `facts.duckdb`, all tables) | 1,200 MB table, 1,296 MB with indexes |

Reading the source files from S3, then joining and filtering them, took 12.4 s before either write began. That step is the same for both databases, so it isn't part of the comparison.

## What was tested

### Data

- **Source:** the SEC's Financial Statement Data Sets, quarter **2026q1**. It contains every XBRL number every US filer reported from January to March 2026.
- **Location:** the files were uploaded to `s3://pdfparserdataset/sec_fsds/2026q1/` and read from there by DuckDB.
  - `num.txt`: 559 MB, 3.69 million rows
  - `sub.txt`: filings
  - `tag.txt`: labels
- **Table:** `sec_fsds_all`, with **3,551,230 rows** covering **5,750 companies**. It keeps every number that has a value: 10-K, 10-Q and other forms, whole-company and segment rows. The same table exists in:
  - Postgres: `public.sec_fsds_all`
  - DuckDB: `data/facts/facts.duckdb`, table `sec_fsds_all`
- **Columns:** ticker, cik, company, form, fiscal_year, fiscal_period, period_end, filed, accession, tag, label, taxonomy, value_date, quarters, unit, segments, value, source.

### Environment

| | DuckDB | Postgres |
|---|---|---|
| Version | 2.0.0 | 16.15 (`postgres:16-alpine`) |
| Runs | in the Python process (Poetry venv), on Windows 11 | in Docker Desktop (WSL 2), on the same machine |
| CPU use | 12 threads (all cores) | stock: 2 parallel workers per query |
| Memory settings | defaults | stock: `shared_buffers` 128 MB |
| Indexes | none (DuckDB keeps min/max statistics per block) | `(ticker, tag)` and `(tag)`, plus `ANALYZE` |

### Method

1. **Answers checked first.** Each query's result from DuckDB was compared with Postgres's, row by row, allowing tiny float rounding differences. The script stops if they differ.
2. **One warm-up run per query**, so both engines had their data cached.
3. **Five timed runs per query**, keeping the median.
4. **How each engine was timed:**
   - **DuckDB:** wall-clock time to execute the query and fetch the result, inside the Python process.
   - **Postgres:** its own server-side **Execution Time** from `EXPLAIN (ANALYZE, TIMING OFF)`, run with `psql` inside the Postgres container. This leaves out network and result-transfer time, which slightly favours Postgres. The comparison is therefore conservative.

### Queries

Each `ORDER BY` breaks ties, so both engines must return the same rows in the same order.

```sql
-- 1. Count every number (full table)
SELECT count(*) FROM sec_fsds_all;

-- 2. Top 10 tags by count (group by)
SELECT tag, count(*) AS n FROM sec_fsds_all
GROUP BY tag ORDER BY n DESC, tag LIMIT 10;

-- 3. Largest annual revenue per company (filter + group by)
SELECT company, max(value) AS revenue FROM sec_fsds_all
WHERE tag IN ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax')
  AND quarters = 4 AND segments IS NULL
GROUP BY company ORDER BY revenue DESC, company LIMIT 10;

-- 4. Distinct companies and tags (distinct count)
SELECT count(DISTINCT cik) AS companies, count(DISTINCT tag) AS tags FROM sec_fsds_all;

-- 5. Count and average value per form and unit (two-column group by)
SELECT form, unit, count(*) AS n, avg(value) AS mean FROM sec_fsds_all
GROUP BY form, unit ORDER BY n DESC, form, unit LIMIT 10;

-- 6. One company's revenue history (index lookup)
SELECT value_date, value FROM sec_fsds_all
WHERE ticker = 'NFLX' AND tag = 'Revenues' AND segments IS NULL
ORDER BY value_date, value;
```

## Why the results look like this

- **DuckDB stores data by column.** A query that needs `tag` reads only the `tag` column, compressed. Postgres stores whole rows, so it reads every column of every row it touches.
- **DuckDB processes data in batches across all 12 cores.** Postgres used at most 2 extra workers per query, and `count(DISTINCT …)` runs single-threaded with a sort in Postgres. That is why query 4 takes 5.4 s there.
- **Postgres's index finds a few rows directly.** Query 6 needs only NFLX's revenue rows, and the `(ticker, tag)` index leads straight to them in 0.10 ms. DuckDB has no index on this table, so it scans the `ticker` and `tag` columns, which still takes only 14.6 ms.
- **Compression explains the size gap.** Columns of similar values, such as forms, units and tags, compress well in DuckDB, which is why the table takes about 7x less space.

## Caveats

- **Query 1 isn't a real scan in DuckDB.** DuckDB answers `count(*)` from the row counts it stores, so that result shows a design advantage rather than scan speed.
- **Postgres used stock settings inside Docker.** Raising `shared_buffers`, `work_mem` and parallel workers, or running it outside Docker, would narrow the gaps but not reverse them for analytical queries.
- **Timings vary 10 to 30% between runs.** An earlier run gave, for example, 6.1x for query 2 and 3.2x for query 3. The winner of every query never changed.
- **One machine, one dataset.** This is a demo benchmark, not a published result.

## Reproduce it

From the repo root, with Docker Desktop running and AWS keys in `.env`:

```bash
docker compose up -d postgres
```

```bash
python scripts/load_sec_fsds.py --source s3://pdfparserdataset/sec_fsds/2026q1 --tickers all --table sec_fsds_all --replace
```

```bash
python scripts/benchmark_duckdb_vs_postgres.py
```

Close any other program holding `data/facts/facts.duckdb` before you start, such as the VS Code Database Client or a DuckDB CLI session.
