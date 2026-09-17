# Seed local stores with sample data. Extend per service.
from pathlib import Path

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "transactions_sample.csv"


def main():
    print(f"Would seed from {SAMPLE} (exists={SAMPLE.exists()})")


if __name__ == "__main__":
    main()
