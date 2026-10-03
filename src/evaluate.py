"""DVC stage `evaluate`: check parse's numbers against the SEC's XBRL values.

Reads  data/parsed/income_statement.csv      (output of `parse`, which also records
                                             the XBRL concept each line is tagged with)
       data/raw/companyfacts/<TICKER>.json   (output of `download`: the answer key)
Writes reports/xbrl_check.csv                one row per line, with a status
       reports/metrics.json                  match rates (a DVC metrics file)
"""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path


def is_full_year(v: dict) -> bool:
    if "start" not in v:
        return False
    days = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
    return days > 350  # a full year, not a quarter


def xbrl_value(facts: dict, concept: str, accession: str, period_end: str):
    """The SEC's full-year value for `concept`, as reported in that same filing.

    Match on accession, never on "fy": the same year appears in several filings,
    and Netflix's FY2025 10-K restates 2024 EPS after its 10-for-1 stock split.
    """
    for values in facts["us-gaap"].get(concept, {}).get("units", {}).values():
        for v in values:
            same_filing = v["accn"] == accession and v["end"] == period_end
            if same_filing and is_full_year(v):
                return float(v["val"])
    return None


def status(parsed, xbrl) -> str:
    if parsed is None:
        return "parse_missing"
    if xbrl is None:
        return "xbrl_missing"
    if math.isclose(parsed, xbrl, rel_tol=1e-4):
        return "match"
    for k in (1_000, 1_000_000, 1_000_000_000):
        if math.isclose(parsed * k, xbrl, rel_tol=1e-4):
            return f"scale_x{k}"  # parsed is k times too small
        if math.isclose(parsed / k, xbrl, rel_tol=1e-4):
            return f"scale_/{k}"  # parsed is k times too large
    if math.isclose(-parsed, xbrl, rel_tol=1e-4):
        return "sign"
    return "mismatch"


def summary(checks: list) -> dict:
    matched = sum(c[-1] == "match" for c in checks)
    return {"lines": len(checks), "matched": matched,
            "match_rate": round(matched / len(checks), 4)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parsed", default="data/parsed/income_statement.csv")
    ap.add_argument("--facts", default="data/raw/companyfacts")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    with open(args.parsed, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    tickers = sorted({r["ticker"] for r in rows})
    facts_dir = Path(args.facts)
    facts = {
        t: json.loads((facts_dir / f"{t}.json").read_text(encoding="utf-8"))
        for t in tickers
    }

    checks = []
    for r in rows:
        parsed = float(r["value"]) if r["value"] else None
        xbrl = None
        if r["concept"]:
            xbrl = xbrl_value(facts[r["ticker"]], r["concept"], r["accession"],
                              r["period_end"])
        checks.append([r["ticker"], r["accession"], r["period_end"], r["line"],
                       r["concept"], parsed, xbrl, status(parsed, xbrl)])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "xbrl_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ticker", "accession", "period_end", "line", "concept", "parsed",
                    "xbrl", "status"])
        w.writerows(checks)

    metrics = {"xbrl": summary(checks)}
    metrics["xbrl"]["by_ticker"] = {
        t: summary([c for c in checks if c[0] == t])["match_rate"] for t in tickers
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    for c in checks:
        print(f"{c[0]:5} {c[3]:17} {c[2]}  {c[-1]}")
    xb = metrics["xbrl"]
    print(f"XBRL match rate: {xb['matched']}/{xb['lines']}  by ticker: {xb['by_ticker']}")


if __name__ == "__main__":
    main()
