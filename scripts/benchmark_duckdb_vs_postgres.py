"""Time the same SQL in DuckDB and in Postgres, on the same table.

Reads  table sec_fsds_all in data/facts/facts.duckdb and in Postgres, both built by
           python scripts/load_sec_fsds.py --source ... --tickers all --table sec_fsds_all
Writes reports/benchmark_duckdb_vs_postgres.json   timings, sizes and settings
       and prints a comparison table

Every query runs once to warm caches, then --runs times; the median is reported, and the
two engines' answers are checked against each other before anything is timed.
  DuckDB:   wall-clock time of execute + fetch in this process.
  Postgres: the server's own "Execution Time" from EXPLAIN (ANALYZE, TIMING OFF), run with
            psql inside the Postgres container, so it leaves out the network and the result
            transfer. That favours Postgres a little, which keeps the comparison conservative.
Postgres keeps its stock settings and gets the indexes load_sec_fsds.py builds. Answers and
sizes are read through DuckDB's postgres extension.

Run from the repo root, with Postgres up (docker compose up -d postgres):
    python scripts/benchmark_duckdb_vs_postgres.py
"""

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import time
from pathlib import Path

import duckdb
from dotenv import load_dotenv

DEFAULT_DSN = "dbname=fis user=fis password=fis host=localhost port=5432"  # docker-compose.yml's dev db
REVENUE_TAGS = "('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax')"

# (name, kind, SQL with {t} for the table). Each ORDER BY breaks ties, so both engines
# must return the same rows in the same order.
QUERIES = [
    ("Count every number", "full scan",
     "SELECT count(*) FROM {t}"),
    ("Top 10 tags by count", "group by",
     "SELECT tag, count(*) AS n FROM {t} GROUP BY tag ORDER BY n DESC, tag LIMIT 10"),
    ("Largest annual revenue per company", "filter + group by",
     "SELECT company, max(value) AS revenue FROM {t} "
     f"WHERE tag IN {REVENUE_TAGS} AND quarters = 4 AND segments IS NULL "
     "GROUP BY company ORDER BY revenue DESC, company LIMIT 10"),
    ("Distinct companies and tags", "distinct count",
     "SELECT count(DISTINCT cik) AS companies, count(DISTINCT tag) AS tags FROM {t}"),
    ("Numbers and average value per form and unit", "multi-column group by",
     "SELECT form, unit, count(*) AS n, avg(value) AS mean FROM {t} "
     "GROUP BY form, unit ORDER BY n DESC, form, unit LIMIT 10"),
    ("One company's revenue history", "index lookup",
     "SELECT value_date, value FROM {t} WHERE ticker = 'NFLX' AND tag = 'Revenues' "
     "AND segments IS NULL ORDER BY value_date, value"),
]


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def same(a: list[tuple], b: list[tuple]) -> bool:
    """Row-by-row equality, allowing float rounding from different summation orders."""
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        for x, y in zip(ra, rb):
            if isinstance(x, float) or isinstance(y, float):
                if not math.isclose(float(x), float(y), rel_tol=1e-9):
                    return False
            elif str(x) != str(y):
                return False
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--table", default="sec_fsds_all")
    p.add_argument("--duckdb", default="data/facts/facts.duckdb")
    p.add_argument("--runs", type=int, default=5, help="timed runs per query, after one warm-up")
    p.add_argument("--out", default="reports/benchmark_duckdb_vs_postgres.json")
    p.add_argument("--pg-service", default="postgres", help="docker compose service that runs Postgres")
    p.add_argument("--pg-user", default="fis")
    p.add_argument("--pg-db", default="fis")
    args = p.parse_args()
    load_dotenv(Path(".env"))  # PG_DSN, if set

    duck = duckdb.connect(args.duckdb, read_only=True)
    pg = duckdb.connect()  # only a client here: every Postgres query runs inside Postgres
    pg.execute("LOAD postgres")
    pg.execute(f"ATTACH {sql_text(os.environ.get('PG_DSN', DEFAULT_DSN))} AS pg (TYPE postgres)")

    def pg_rows(sql: str) -> list[tuple]:
        return pg.execute(f"SELECT * FROM postgres_query('pg', {sql_text(sql)})").fetchall()

    def pg_times(sql: str, n: int) -> list[float]:
        """Server-side ms for n runs of sql, after one warm-up, in a single psql session."""
        script = f"EXPLAIN (ANALYZE, TIMING OFF) {sql};\n" * (n + 1)
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", args.pg_service, "psql", "-U", args.pg_user, "-d", args.pg_db,
             "-At", "-v", "ON_ERROR_STOP=1"],
            input=script, capture_output=True, text=True, check=True,
        ).stdout
        return [float(ms) for ms in re.findall(r"Execution Time: ([\d.]+) ms", out)][1:]

    def duck_ms(sql: str) -> float:
        started = time.perf_counter()
        duck.execute(sql).fetchall()
        return (time.perf_counter() - started) * 1000

    rows = duck.execute(f"SELECT count(*) FROM {args.table}").fetchone()[0]
    print(f"{args.table}: {rows:,} rows in both databases; median of {args.runs} runs after a warm-up\n")

    results = []
    for name, kind, template in QUERIES:
        sql = template.format(t=args.table)
        if not same(duck.execute(sql).fetchall(), pg_rows(sql)):
            raise SystemExit(f"DuckDB and Postgres disagree on: {name}")
        duck_ms(sql)  # warm-up
        d = statistics.median(duck_ms(sql) for _ in range(args.runs))
        g = statistics.median(pg_times(sql, args.runs))
        results.append({"query": name, "kind": kind, "sql": sql, "duckdb_ms": round(d, 2), "postgres_ms": round(g, 2),
                        "faster": "duckdb" if g >= d else "postgres", "times_faster": round(max(d, g) / min(d, g), 1)})

    w = max(len(r["query"]) for r in results)
    print(f"{'Query':<{w}}  {'DuckDB':>10}  {'Postgres':>10}  Faster")
    for r in results:
        faster = f"{'DuckDB' if r['faster'] == 'duckdb' else 'Postgres'} {r['times_faster']:,.1f}x"
        print(f"{r['query']:<{w}}  {r['duckdb_ms']:>8.2f}ms  {r['postgres_ms']:>8.2f}ms  {faster}")

    pg_size = pg_rows(f"SELECT pg_total_relation_size('{args.table}'), pg_relation_size('{args.table}')")[0]
    settings = {k: pg_rows(f"SELECT current_setting('{k}')")[0][0]
                for k in ("server_version", "shared_buffers", "max_parallel_workers_per_gather")}
    sizes = {"duckdb_file_bytes": Path(args.duckdb).stat().st_size,
             "postgres_table_bytes": int(pg_size[1]), "postgres_table_with_indexes_bytes": int(pg_size[0])}
    print(f"\nstorage: facts.duckdb file {sizes['duckdb_file_bytes'] / 1e6:,.0f} MB (all its tables) | "
          f"Postgres table {sizes['postgres_table_bytes'] / 1e6:,.0f} MB, "
          f"{sizes['postgres_table_with_indexes_bytes'] / 1e6:,.0f} MB with indexes")
    print(f"settings: DuckDB {duckdb.__version__}, {duck.execute('SELECT current_setting(?)', ['threads']).fetchone()[0]}"
          f" threads | Postgres {settings['server_version']}, shared_buffers {settings['shared_buffers']}, "
          f"{settings['max_parallel_workers_per_gather']} parallel workers per query")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "table": args.table, "rows": rows, "runs": args.runs, "duckdb_version": duckdb.__version__,
        "postgres_settings": settings, "sizes": sizes, "results": results,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
