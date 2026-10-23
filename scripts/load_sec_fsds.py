"""Load a slice of an SEC Financial Statement Data Set into Postgres and DuckDB.

Reads  <source>/sub.txt, num.txt, tag.txt   one unzipped quarter (e.g. 2026q1.zip) from
       https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets,
       either in a local folder or under an S3 prefix (s3://bucket/path)
Writes table sec_fsds_numbers (or --table), in two places:
         Postgres public.sec_fsds_numbers
         DuckDB   data/facts/facts.duckdb, next to the `facts` table
       every number the chosen tickers' 10-K and 10-Q filings reported that quarter,
       one row per number, with its readable label. With --tickers all it keeps every
       number every company filed that quarter (about 3.7 million rows), which is the
       table scripts/benchmark_duckdb_vs_postgres.py times queries against.

DuckDB scans the tab-separated files where they are (num.txt is about half a GB), straight
from S3 when the source is an s3:// prefix, joins them, keeps the chosen companies, and
writes the result to both databases. Demo data: not a DVC stage, and not part of `facts`.

AWS credentials come from the environment or the repo's .env file (AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY, AWS_REGION); see .env.example. Nothing secret is printed or stored.

Run from the repo root, with Postgres up (docker compose up -d postgres):
    # upload the local files to S3 once, then load from S3
    python scripts/load_sec_fsds.py --source s3://pdfparserdataset/sec_fsds/2026q1 \
        --upload-from ../datasets/sec_fsds_2026q1
    # or load from a local folder
    python scripts/load_sec_fsds.py --source ../datasets/sec_fsds_2026q1
    # every company, for the benchmark
    python scripts/load_sec_fsds.py --source s3://pdfparserdataset/sec_fsds/2026q1 \
        --tickers all --table sec_fsds_all
"""

import argparse
import os
import time
from pathlib import Path

import duckdb
import requests
import yaml
from dotenv import load_dotenv

DEFAULT_TICKERS = "AAPL,NFLX,MSFT,NVDA,GOOGL,AMZN,META"
DEFAULT_DSN = "dbname=fis user=fis password=fis host=localhost port=5432"  # docker-compose.yml's dev db
DEFAULT_DUCKDB = "data/facts/facts.duckdb"
FILES = ("sub.txt", "num.txt", "tag.txt")
DEFAULT_TABLE = "sec_fsds_numbers"
TSV = "delim = '\t', header = true, quote = '', escape = ''"  # SEC files: tabs, no quoting

NUM_COLUMNS = {"adsh": "VARCHAR", "tag": "VARCHAR", "version": "VARCHAR", "ddate": "VARCHAR",
               "qtrs": "INTEGER", "uom": "VARCHAR", "segments": "VARCHAR", "coreg": "VARCHAR",
               "value": "DOUBLE", "footnote": "VARCHAR"}

SELECT_NUMBERS = """
SELECT
    o.ticker,
    s.cik,
    s.name                                       AS company,
    s.form,
    s.fy                                         AS fiscal_year,
    s.fp                                         AS fiscal_period,
    try_strptime(s.period::VARCHAR, '%Y%m%d')::DATE AS period_end,
    try_strptime(s.filed::VARCHAR, '%Y%m%d')::DATE  AS filed,
    n.adsh                                       AS accession,
    n.tag,
    t.tlabel                                     AS label,
    n.version                                    AS taxonomy,
    try_strptime(n.ddate, '%Y%m%d')::DATE        AS value_date,
    n.qtrs                                       AS quarters,   -- 0 = point in time, 1 = a quarter, 4 = a year
    n.uom                                        AS unit,
    n.segments,                                                 -- NULL = the whole company
    n.value,
    ?                                            AS source
FROM num n
JOIN sub s USING (adsh)
{ticker_join} tickers o USING (cik)
LEFT JOIN tag t ON t.tag = n.tag AND t.version = n.version
WHERE {where}
"""
CHOSEN = {"ticker_join": "JOIN", "where": "s.form IN ('10-K', '10-Q') AND n.coreg IS NULL AND n.value IS NOT NULL"}
EVERYTHING = {"ticker_join": "LEFT JOIN", "where": "n.value IS NOT NULL"}  # companies without a ticker too


def user_agent() -> str:
    # SEC fair access requires a User-Agent that names you, as in the download stage.
    if agent := os.environ.get("SEC_USER_AGENT"):
        return agent
    download = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))["download"]
    return f"{download['user_agent_name']} {download['user_agent_email']}"


def ticker_ciks(tickers: list[str] | None) -> list[tuple[str, int]]:
    """(ticker, CIK) pairs from the SEC's list: the chosen tickers, or one per company if None."""
    listing = requests.get("https://www.sec.gov/files/company_tickers.json",
                           headers={"User-Agent": user_agent()}, timeout=30).json()
    pairs = [(row["ticker"].upper(), int(row["cik_str"])) for row in listing.values()]
    if tickers is None:
        first: dict[int, str] = {}
        for ticker, cik in pairs:  # a company with several share classes keeps its first-listed ticker
            first.setdefault(cik, ticker)
        return [(ticker, cik) for cik, ticker in first.items()]
    found = dict(pairs)
    missing = [t for t in tickers if t not in found]
    if missing:
        raise SystemExit(f"not in the SEC's ticker list: {', '.join(missing)}")
    return [(t, found[t]) for t in tickers]


def aws_settings() -> tuple[str, str, str, str | None]:
    key, secret = os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not key or not secret:
        raise SystemExit("set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env (see .env.example)")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-2"
    return key, secret, region, os.environ.get("AWS_SESSION_TOKEN") or None


def upload(local: Path, prefix: str) -> None:
    """Copy the three files to S3, skipping any already there with the same size."""
    import s3fs  # installed with dvc[s3]

    key, secret, region, token = aws_settings()
    fs = s3fs.S3FileSystem(key=key, secret=secret, token=token, client_kwargs={"region_name": region})
    for name in FILES:
        src, dst = local / name, f"{prefix}/{name}"
        if fs.exists(dst) and fs.size(dst) == src.stat().st_size:
            print(f"already in S3: {dst}")
            continue
        started = time.perf_counter()
        fs.put_file(str(src), dst)
        print(f"uploaded {name} ({src.stat().st_size / 1e6:,.0f} MB) to {dst} in {time.perf_counter() - started:.0f}s")


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", required=True, help="folder or s3:// prefix holding sub.txt, num.txt and tag.txt")
    p.add_argument("--upload-from", help="local folder to upload to the --source S3 prefix first")
    p.add_argument("--tickers", default=DEFAULT_TICKERS, help="comma-separated, e.g. AAPL,MSFT; or `all`")
    p.add_argument("--table", default=DEFAULT_TABLE, help="table name in both databases")
    p.add_argument("--duckdb", default=DEFAULT_DUCKDB, help="DuckDB file that also gets the table")
    p.add_argument("--replace", action="store_true", help="drop and rebuild the tables if they exist")
    args = p.parse_args()

    load_dotenv(Path(".env"))  # AWS_*, PG_DSN; real environment variables win
    source = args.source.rstrip("/")
    on_s3 = source.startswith("s3://")
    table = args.table
    everything = args.tickers.strip().lower() == "all"
    tickers = None if everything else [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if args.upload_from:
        if not on_s3:
            raise SystemExit("--upload-from needs an s3:// --source to upload to")
        upload(Path(args.upload_from), source)

    con = duckdb.connect()
    if on_s3:
        key, secret, region, token = aws_settings()
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")
        con.execute(f"CREATE SECRET sec_s3 (TYPE s3, KEY_ID {sql_text(key)}, SECRET {sql_text(secret)}, "
                    f"REGION {sql_text(region)}" + (f", SESSION_TOKEN {sql_text(token)}" if token else "") + ")")

    # Both targets first, so a table that already exists stops the run before any work
    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")
    try:
        con.execute(f"ATTACH {sql_text(os.environ.get('PG_DSN', DEFAULT_DSN))} AS pg (TYPE postgres)")
    except duckdb.IOException:
        raise SystemExit("can't reach Postgres on localhost:5432: start Docker Desktop, then "
                         "`docker compose up -d postgres`") from None
    Path(args.duckdb).parent.mkdir(parents=True, exist_ok=True)
    try:
        con.execute(f"ATTACH {sql_text(Path(args.duckdb).as_posix())} AS store")
    except duckdb.IOException as e:
        raise SystemExit(f"can't open {args.duckdb}; another program has it open (VS Code Database "
                         f"Client, DuckDB CLI, a notebook). Close it and rerun.\n{e}") from None
    existing = [db for db, in con.execute(
        "SELECT database_name FROM duckdb_tables() WHERE database_name IN ('pg', 'store') AND table_name = ?",
        [table]).fetchall()]
    if existing and not args.replace:
        raise SystemExit(f"{table} already exists in {', '.join(existing)}; rerun with --replace to rebuild it")

    for name in ("sub", "tag"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv({sql_text(f'{source}/{name}.txt')}, "
                    f"{TSV}, sample_size = -1)")
    con.execute(f"CREATE VIEW num AS SELECT * FROM read_csv({sql_text(f'{source}/num.txt')}, "
                f"{TSV}, columns = {NUM_COLUMNS})")
    con.execute("CREATE TEMP TABLE tickers (ticker VARCHAR, cik BIGINT)")
    con.executemany("INSERT INTO tickers VALUES (?, ?)", ticker_ciks(tickers))

    started = time.perf_counter()
    con.execute("CREATE TEMP TABLE result AS " + SELECT_NUMBERS.format(**(EVERYTHING if everything else CHOSEN)),
                [source])
    rows = con.execute("SELECT count(*) FROM result").fetchone()[0]
    print(f"scanned {source} and kept {rows:,} numbers in {time.perf_counter() - started:.1f}s")

    started = time.perf_counter()
    if "pg" in existing:
        con.execute(f"DROP TABLE pg.public.{table}")
    con.execute(f"CREATE TABLE pg.public.{table} AS SELECT * FROM result")
    # The help a DBA would give Postgres: indexes for lookups by ticker and tag, and fresh planner stats
    for sql in (f"CREATE INDEX ON {table} (ticker, tag)", f"CREATE INDEX ON {table} (tag)", f"ANALYZE {table}"):
        con.execute(f"CALL postgres_execute('pg', {sql_text(sql)})")
    print(f"wrote {table} to Postgres in {time.perf_counter() - started:.1f}s")
    started = time.perf_counter()
    con.execute(f"CREATE OR REPLACE TABLE store.main.{table} AS SELECT * FROM result")
    print(f"wrote {table} to {args.duckdb} in {time.perf_counter() - started:.1f}s")

    con.sql(f"""
        SELECT 'postgres' AS db, count(*) AS numbers, count(DISTINCT cik) AS companies FROM pg.public.{table}
        UNION ALL
        SELECT 'duckdb', count(*), count(DISTINCT cik) FROM store.main.{table}
    """).show()
    if not everything:
        con.sql(f"""
            SELECT p.ticker, p.form, p.fiscal_period, p.numbers AS postgres, d.numbers AS duckdb
            FROM (SELECT ticker, form, fiscal_period, count(*) AS numbers FROM pg.public.{table} GROUP BY ALL) p
            JOIN (SELECT ticker, form, fiscal_period, count(*) AS numbers FROM store.main.{table} GROUP BY ALL) d
              USING (ticker, form, fiscal_period)
            ORDER BY p.ticker
        """).show()


if __name__ == "__main__":
    main()
