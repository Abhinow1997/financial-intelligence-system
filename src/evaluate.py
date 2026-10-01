"""DVC stage `evaluate`: check parse's numbers against the SEC's XBRL values.

Reads  data/parsed/income_statement.csv   (output of `parse`)
       data/raw/companyfacts.json         (output of `download`: the answer key)
Writes reports/xbrl_check.csv             one row per line, with a status
       reports/metrics.json               the match rate (a DVC metrics file)
"""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

# Statement line -> the XBRL concept Netflix tags it with.
CONCEPTS = {
    "Revenues": "Revenues",
    "Operating income": "OperatingIncomeLoss",
    "Net income": "NetIncomeLoss",
    "Diluted EPS": "EarningsPerShareDiluted",
}


def xbrl_value(facts: dict, concept: str, accession: str, period_end: str):
    """The full-year value for `period_end`, as reported in that same filing.

    Match on accession, never on "fy": the same year appears in several filings,
    and Netflix's FY2025 10-K restates 2024 EPS after its 10-for-1 stock split.
    """
    for values in facts["us-gaap"].get(concept, {}).get("units", {}).values():
        for v in values:
            if v["accn"] != accession or v["end"] != period_end or "start" not in v:
                continue
            days = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
            if days > 350:  # a full year, not a quarter
                return float(v["val"])
    return None


def status(parsed: float, xbrl) -> str:
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parsed", default="data/parsed/income_statement.csv")
    ap.add_argument("--facts", default="data/raw/companyfacts.json")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    with open(args.parsed, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    checks = []
    for r in rows:
        concept = CONCEPTS[r["line"]]
        xbrl = xbrl_value(facts, concept, r["accession"], r["period_end"])
        parsed = float(r["value"])
        checks.append([r["accession"], r["period_end"], r["line"], parsed, xbrl,
                       status(parsed, xbrl)])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "xbrl_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["accession", "period_end", "line", "parsed", "xbrl", "status"])
        w.writerows(checks)

    matched = sum(c[-1] == "match" for c in checks)
    metrics = {"xbrl": {"lines": len(checks), "matched": matched,
                        "match_rate": round(matched / len(checks), 4)}}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    for c in checks:
        print(f"{c[2]:17} {c[1]}  {c[5]}")
    print(f"XBRL match rate: {matched}/{len(checks)}")


if __name__ == "__main__":
    main()
