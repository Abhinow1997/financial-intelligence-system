# Model Service (R1) - predictive baseline + challenger.
# Serves a credit-default probability. In production this loads a versioned,
# pinned model artifact from the registry. Here it is a deterministic stub so
# the endpoint contract is real even before a model is trained.
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Model Service", version="0.1.0")
SERVICE, RELEASE = "model_service", "R1"


class Borrower(BaseModel):
    # Typed feature contract == the interface an agent tool would call.
    debt_to_income: float = Field(ge=0, le=5)
    fico: int = Field(ge=300, le=850)
    utilization: float = Field(ge=0, le=1)
    delinquencies_2y: int = Field(ge=0)


class Prediction(BaseModel):
    probability_default: float
    threshold: float
    decision: str
    model_version: str


def _baseline_score(b: Borrower) -> float:
    # Transparent logit-style stub; replace with the trained model artifact.
    z = (
        -4.0
        + 1.2 * b.debt_to_income
        + 2.5 * b.utilization
        + 0.4 * b.delinquencies_2y
        - 0.004 * (b.fico - 600)
    )
    return 1.0 / (1.0 + pow(2.718281828, -z))


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.post("/predict", response_model=Prediction)
def predict(b: Borrower):
    p = _baseline_score(b)
    threshold = 0.5  # tune with a confusion-cost matrix (see notebooks/prework_A).
    return Prediction(
        probability_default=round(p, 4),
        threshold=threshold,
        decision="decline" if p >= threshold else "approve",
        model_version="baseline-0.1.0-stub",
    )
