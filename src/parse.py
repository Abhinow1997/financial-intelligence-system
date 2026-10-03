"""DVC stage `parse`: pull four income-statement lines out of each 10-K.

Reads  data/raw/sec-edgar-filings/<TICKER>/<FORM>/<ACCESSION>/primary-document.html
       (output of `download`)
Writes data/parsed/income_statement.csv   one row per company x filing x line

Companies word their statements differently (Netflix "Revenues", Apple "Total net
sales", Microsoft "Total revenue"), so instead of matching wording we use the Inline
XBRL tags every 10-K wraps around its numbers. Each tag names the concept, the period
and the scale the number is printed in, so this works for any company that files
Inline XBRL, which every US-listed company has done since 2021.
"""

import argparse
import csv
import html
import re
from datetime import date
from pathlib import Path

import yaml

# Statement line -> XBRL concepts it may be tagged with, tried in order.
LINES = {
    "Revenues": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                 "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"),
    "Operating income": ("OperatingIncomeLoss",),
    "Net income": ("NetIncomeLoss",),
    "Diluted EPS": ("EarningsPerShareDiluted",),
}
UNITS = {0: "units", 3: "thousands", 6: "millions", 9: "billions"}

CONTEXT = re.compile(
    r'<(?:\w+:)?context\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</(?:\w+:)?context>', re.S | re.I
)
START = re.compile(r"<(?:\w+:)?startDate>\s*([\d-]+)\s*<", re.I)
END = re.compile(r"<(?:\w+:)?endDate>\s*([\d-]+)\s*<", re.I)
FACT = re.compile(r"<ix:nonFraction\b([^>]*?)(?<!/)>(.*?)</ix:nonFraction>", re.S | re.I)
ATTR = re.compile(r'([\w:-]+)="([^"]*)"')


def full_year_contexts(raw: str) -> dict:
    """Context id -> period end, for full-year periods of the whole company."""
    out = {}
    for cid, body in CONTEXT.findall(raw):
        if re.search(r"<(?:\w+:)?segment\b", body, re.I):
            continue  # a breakdown (segment, product line), not the company total
        start, end = START.search(body), END.search(body)
        if start and end:
            days = (date.fromisoformat(end.group(1)) - date.fromisoformat(start.group(1))).days
            if days > 350:  # a full year, not a quarter
                out[cid] = end.group(1)
    return out


def tagged_numbers(raw: str) -> list[dict]:
    """Every full-year tagged number: its concept, period, scale and printed text."""
    contexts = full_year_contexts(raw)
    found = []
    for attrs, inner in FACT.findall(raw):
        a = dict(ATTR.findall(attrs))
        if a.get("contextRef") in contexts:
            found.append({
                "concept": a.get("name", "").split(":")[-1],
                "period_end": contexts[a["contextRef"]],
                "scale": int(a.get("scale", "0")),
                "negative": a.get("sign") == "-",
                "shown": html.unescape(re.sub(r"<[^>]+>", "", inner)).strip(),
            })
    return found


def pick(numbers: list[dict], concepts: tuple):
    """The latest year's number for the first of `concepts` the company uses.

    The same number can be printed several times (statement, MD&A, notes); prefer
    the most precise printing (smallest scale), which is usually the statement's.
    """
    for concept in concepts:
        candidates = [n for n in numbers if n["concept"] == concept]
        if candidates:
            latest = max(n["period_end"] for n in candidates)
            return min((n for n in candidates if n["period_end"] == latest),
                       key=lambda n: n["scale"])
    return None


def to_number(shown: str, negative: bool) -> float:
    """'39,000,966' -> 39000966.0; a dash (no digits) means zero."""
    digits = re.sub(r"[^\d.]", "", shown)
    value = float(digits) if digits else 0.0
    return -value if negative else value


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
        accession = doc.parent.name
        numbers = tagged_numbers(doc.read_text(encoding="utf-8", errors="ignore"))
        for line, concepts in LINES.items():
            n = pick(numbers, concepts)
            if n is None:
                print(f"{ticker} {accession}: no tagged value for {line}")
                rows.append([ticker, accession, "", line, "", "", "", ""])
                continue
            # Deliberate demo bug: with apply_scale false the printed number is kept
            # as-is, ignoring that it is shown in thousands or millions.
            scale = 10 ** n["scale"] if p["apply_scale"] else 1
            value = to_number(n["shown"], n["negative"]) * scale
            unit = UNITS.get(n["scale"], f"1e{n['scale']}")
            rows.append([ticker, accession, n["period_end"], line, n["concept"],
                         n["shown"], unit, value])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "income_statement.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ticker", "accession", "period_end", "line", "concept", "raw", "unit",
                    "value"])
        w.writerows(rows)
    print(f"parsed {len(rows)} lines from {len(rows) // len(LINES)} filing(s)")


if __name__ == "__main__":
    main()
