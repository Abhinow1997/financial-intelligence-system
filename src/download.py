"""DVC stage `download`: fetch the filings pinned in params.yaml from SEC EDGAR.

Writes (the stage's output, owned by DVC and ignored by Git):
  data/raw/sec-edgar-filings/<TICKER>/<FORM>/<ACCESSION>/full-submission.txt
  data/raw/sec-edgar-filings/<TICKER>/<FORM>/<ACCESSION>/primary-document.html
  data/raw/companyfacts/<TICKER>.json  the SEC's XBRL facts for that company's filings
"""

import argparse
import json
import re
import urllib.request
from pathlib import Path

import yaml
from sec_edgar_downloader import Downloader


def fetch_companyfacts(cik: str, user_agent: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def keep_only(facts: dict, accessions: set[str]) -> dict:
    """Keep only the values reported in our filings.

    companyfacts aggregates every filing the company has ever made and grows with
    each new one, so saving it whole would make this stage's output drift over time.
    """
    kept = {}
    for concept, body in facts["facts"].get("us-gaap", {}).items():
        units = {
            unit: [v for v in values if v["accn"] in accessions]
            for unit, values in body["units"].items()
        }
        units = {unit: values for unit, values in units.items() if values}
        if units:
            kept[concept] = {"label": body.get("label"), "units": units}
    return {"cik": facts["cik"], "entityName": facts["entityName"], "us-gaap": kept}


def read_cik(submission: Path) -> str:
    """The CIK is the CENTRAL INDEX KEY line in the SEC header of full-submission.txt."""
    header = submission.read_text(encoding="utf-8", errors="ignore")[:5000]
    match = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", header)
    if not match:
        raise SystemExit(f"No CENTRAL INDEX KEY found in the SEC header of {submission}")
    return match.group(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--params", default="params.yaml")
    ap.add_argument("--out", default="data/raw")
    args = ap.parse_args()

    p = yaml.safe_load(Path(args.params).read_text(encoding="utf-8"))["download"]
    out = Path(args.out)
    user_agent = f"{p['user_agent_name']} {p['user_agent_email']}"
    dl = Downloader(p["user_agent_name"], p["user_agent_email"], out)

    # Each company has its own filing window, because fiscal years end at different times.
    for ticker, window in p["companies"].items():
        for form in p["forms"]:
            n = dl.get(form, ticker, after=window["after"], before=window["before"],
                       download_details=True)
            print(f"{ticker} {form}: downloaded {n} filing(s)")

        # The accession number is the folder name; look only inside this company's folder.
        subs = sorted((out / "sec-edgar-filings" / ticker).rglob("full-submission.txt"))
        if not subs:
            raise SystemExit(f"No filings downloaded for {ticker}: check its dates in params.yaml")
        accessions = {s.parent.name for s in subs}

        facts = keep_only(fetch_companyfacts(read_cik(subs[0]), user_agent), accessions)
        dest = out / "companyfacts" / f"{ticker}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(facts, indent=1, sort_keys=True),
                        encoding="utf-8", newline="\n")
        print(f"{ticker} companyfacts: {len(facts['us-gaap'])} concepts for {sorted(accessions)}")


if __name__ == "__main__":
    main()