"""Build the fact store.

Reads  reports/xbrl_check.csv     (output of `evaluate`: the SEC's XBRL value for each line)
Writes data/facts/facts.duckdb    table `facts` (tiers 1-3) and table `claims` (tiers 4-5)

Every fact carries a tier and a citation (Case Study 2, Part 1). For now the only source is
the XBRL check, so every row is a tier-1 public fact; data-room loaders add tier-3 facts and
tier-4/5 claims later.

The file is shared with the backend's /facts API, which saves tickers it fetched from the SEC
into the same `facts` table. So a rebuild replaces only this script's own rows (the ones whose
`extractor` is PIPELINE_EXTRACTOR) and leaves the API's rows alone; where both hold the same
fact, the pipeline's copy wins.

Run from the repo root:  python src/facts/build.py
"""

import argparse
from pathlib import Path

import duckdb

PIPELINE_EXTRACTOR = "companyfacts (src/evaluate.py)"  # tags the rows this script owns

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id     VARCHAR PRIMARY KEY,
    deal_id     VARCHAR NOT NULL,           -- public, deal_a, deal_b, kestrel
    entity_id   VARCHAR,
    concept     VARCHAR,                    -- XBRL concept
    metric      VARCHAR,                    -- name from config/metrics_vocab.yaml
    value       DOUBLE,
    unit        VARCHAR,
    period_type VARCHAR,                    -- duration or instant
    "start"     DATE,
    "end"       DATE,                       -- END is a SQL keyword, so always quote it
    dims        JSON,
    decimals    INTEGER,
    tier        TINYINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
    source_type VARCHAR,
    doc_id      VARCHAR,
    citation    JSON NOT NULL,
    extractor   VARCHAR,
    lineage     JSON
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id    VARCHAR PRIMARY KEY,
    deal_id     VARCHAR NOT NULL,
    entity_id   VARCHAR,
    metric      VARCHAR,
    value       DOUBLE,
    unit        VARCHAR,
    qualifier   VARCHAR,                    -- adjusted, run-rate, pro forma, LTM, FY
    period_type VARCHAR,
    "start"     DATE,
    "end"       DATE,
    tier        TINYINT NOT NULL CHECK (tier BETWEEN 4 AND 5),
    source_type VARCHAR,
    doc_id      VARCHAR,
    block_id    VARCHAR,
    citation    JSON NOT NULL,              -- page + bbox of the claim
    extractor   VARCHAR,
    lineage     JSON
);
"""

# One row of xbrl_check.csv -> one tier-1 fact. `xbrl` is the SEC's full-dollar value;
# `parsed` is in the filing's printed scale, so it is not used here. OR REPLACE: if the API
# already saved this fact (same fact_id), the pipeline's row takes its place.
LOAD_XBRL = """
INSERT OR REPLACE INTO facts BY NAME
SELECT
    md5(concat_ws('|', accession, concept, period_end)) AS fact_id,   -- same id every rebuild
    'public'                          AS deal_id,
    ticker                            AS entity_id,
    'us-gaap:' || concept             AS concept,
    CASE line WHEN 'Revenues'         THEN 'revenue'
              WHEN 'Operating income' THEN 'operating_income'
              WHEN 'Net income'       THEN 'net_income'
              WHEN 'Diluted EPS'      THEN 'eps_diluted' END AS metric,
    xbrl                              AS value,
    CASE WHEN line = 'Diluted EPS' THEN 'USD/shares' ELSE 'USD' END AS unit,
    'duration'                        AS period_type,
    CAST(period_end AS DATE)          AS "end",
    1                                 AS tier,
    'edgar_xbrl'                      AS source_type,
    accession                         AS doc_id,
    json_object('kind', 'ixbrl_context', 'doc_id', accession,
                'concept', 'us-gaap:' || concept, 'period_end', period_end) AS citation,
    'companyfacts (src/evaluate.py)'  AS extractor,
    json_object('parents', [accession], 'source', 'reports/xbrl_check.csv') AS lineage
FROM read_csv('{csv}', header = true)
WHERE xbrl IS NOT NULL
"""


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--csv", default="reports/xbrl_check.csv")
    p.add_argument("--out", default="data/facts/facts.duckdb")
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(out)) as con:
        con.execute(SCHEMA)
        con.begin()  # one transaction: a failed load never leaves the store half-empty
        con.execute("DELETE FROM facts WHERE extractor = ?", [PIPELINE_EXTRACTOR])
        con.execute(LOAD_XBRL.format(csv=Path(args.csv).as_posix()))
        con.commit()
        n, total = con.execute(
            "SELECT count(*) FILTER (WHERE extractor = ?), count(*) FROM facts", [PIPELINE_EXTRACTOR]
        ).fetchone()
    print(f"duckdb {duckdb.__version__}: wrote {n} pipeline facts to {out} ({total} facts in the file)")


if __name__ == "__main__":
    main()
