import time
from contextlib import contextmanager


class CostMeter:
    def __init__(self):
        self.total_usd = 0.0

    def add(self, usd: float):
        self.total_usd += usd


@contextmanager
def Span(name: str):
    # Minimal span: measure latency; a real impl exports to the observability svc.
    start = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - start) * 1000)
        print(f"[span] {name} {ms}ms")
