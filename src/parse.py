"""DVC stage `parse`: pull four income-statement lines out of each 10-K.

Reads  data/raw/sec-edgar-filings/<TICKER>/<FORM>/<ACCESSION>/primary-document.html
       (output of `download`)
Writes data/parsed/income_statement.csv   one row per company x filing x line
"""

import argparse
import csv
import html
import re
from datetime import datetime
from pathlib import Path

import yaml

# Statement line -> how its row starts in the text (companies word it differently).
# The first number after it is the latest fiscal year.
LINES = {
    "Revenues": r"(?:Revenues|Total net sales)",  # Netflix | Apple
    "Operating income": r"Operating income",
    "Net income": r"Net income",
    "Diluted EPS": r"Earnings per share: Basic .*? Diluted",
}
NUMBER = r"\$?\s*(\(\s*[\d,.]+\s*\)|[\d,.]+)"  # 39,000,966 or ( 718,733 ) or 19.83
SCALES = {"thousands": 1e3, "millions": 1e6, "billions": 1e9}


def statement_text(doc: Path) -> str:
    """Return the income statement as one line of plain text."""
    text = doc.read_text(encoding="utf-8", errors="ignore")
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text)
    # re.I: Netflix writes "(in thousands", Apple "(In millions"
    start = re.search(r"CONSOLIDATED STATEMENTS OF OPERATIONS \(in ", text, re.I).start()
    return text[start : start + 3000]


def to_number(raw: str) -> float:
    """'39,000,966' -> 39000966.0 and '( 718,733 )' -> -718733.0"""
    value = float(re.sub(r"[^\d.]", "", raw))
    return -value if raw.startswith("(") else value


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--params", default="params.yaml")
    ap.add_argument("--input", default="data/raw")
    ap.add_argument("--out", default="data/parsed")
    args = ap.parse_args()
    p = yaml.safe_load(Path(args.params).read_text(encoding="utf-8"))["parse"]

    rows = []
    for doc in sorted(Path(args.input).rglob("primary-document.html")):
        ticker = doc.parents[2].name  # .../<TICKER>/<FORM>/<ACCESSION>/primary-document.html
        text = statement_text(doc)
        unit = re.search(r"\(in (\w+)", text, re.I).group(1).lower()  # thousands, millions
        scale = SCALES[unit] if p["apply_scale"] else 1.0
        # "Year ended December 31, 2024" (Netflix) or "Years ended September 28, 2024" (Apple)
        year_end = re.search(r"Years? ended (\w+ \d+, \d{4})", text).group(1)
        period = datetime.strptime(year_end, "%B %d, %Y").date().isoformat()
        for line, label in LINES.items():
            raw = re.search(label + r"\s*" + NUMBER, text).group(1)
            value = to_number(raw) * scale
            rows.append([ticker, doc.parent.name, period, line, raw, unit, value])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "income_statement.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ticker", "accession", "period_end", "line", "raw", "unit", "value"])
        w.writerows(rows)
    print(f"parsed {len(rows)} lines from {len(rows) // len(LINES)} filing(s)")


if __name__ == "__main__":
    main()
