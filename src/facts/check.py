"""Print what is in the fact store and check its Case Study 2 rules. Read-only.

Reads  data/facts/facts.duckdb    (output of src/facts/build.py)

Run from the repo root:  python src/facts/check.py
"""

import argparse

import duckdb


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default="data/facts/facts.duckdb")
    args = p.parse_args()

    with duckdb.connect(args.db, read_only=True) as con:
        con.sql("SHOW TABLES").show()
        con.sql("""
            SELECT entity_id, metric, "end", value, unit, tier
            FROM facts ORDER BY entity_id, "end", metric
        """).show(max_rows=50)
        con.sql("SELECT fact_id, citation FROM facts LIMIT 2").show(max_width=200)
        con.sql("SELECT count(*) AS claims FROM claims").show()
        # Both counts must be 0: every fact has a tier and a citation, and no claim is a fact.
        con.sql("""
            SELECT count(*) FILTER (WHERE tier IS NULL OR citation IS NULL) AS missing_tier_or_citation,
                   count(*) FILTER (WHERE tier > 3)                         AS claims_in_facts
            FROM facts
        """).show()


if __name__ == "__main__":
    main()
