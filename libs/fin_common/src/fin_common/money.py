from decimal import ROUND_HALF_EVEN, Decimal


class Money:
    # Never use float for money. Decimal + explicit currency.
    def __init__(self, amount, currency: str = "USD"):
        self.amount = Decimal(str(amount)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        self.currency = currency

    def __repr__(self):
        return f"Money({self.amount}, {self.currency!r})"
