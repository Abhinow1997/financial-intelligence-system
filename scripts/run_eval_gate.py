# Blocking eval gate used by CI (R4/R6). Exit non-zero to fail the build.
import sys

ACCEPTANCE = {"quality_min": 0.80, "cost_max_usd": 0.25, "p95_latency_ms_max": 4000}


def run() -> dict:
    # TODO: call eval_service, compare against ACCEPTANCE thresholds.
    return {
        "quality": 0.0,
        "cost_usd": 0.0,
        "p95_latency_ms": 0,
        "passed": False,
        "note": "stub - not implemented; wire to services/evaluation",
    }


if __name__ == "__main__":
    result = run()
    print(result)
    # Skeleton must not block the very first CI run; flip to sys.exit(0 if passed).
    sys.exit(0)
