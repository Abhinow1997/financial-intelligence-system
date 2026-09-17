# Tool Registry (R3) - typed, validated finance tools with minimum privilege.
# Models interpret ambiguity; software (these tools) enforces rules.
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Tool Registry", version="0.1.0")
SERVICE, RELEASE = "tool_registry", "R3"


class PVInput(BaseModel):
    cash_flow: float
    rate: float = Field(gt=-1, lt=1)
    periods: int = Field(ge=1, le=100)


TOOLS = {
    "present_value": {
        "scope": "read_only",
        "reversible": True,
        "description": "Discount a single cash flow to present value.",
    },
    "place_order": {
        "scope": "state_changing",
        "reversible": False,
        "description": "Submit an order. Requires human approval (policy_engine).",
    },
}


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/tools")
def list_tools():
    return TOOLS


@app.post("/tools/present_value")
def present_value(x: PVInput):
    pv = x.cash_flow / ((1 + x.rate) ** x.periods)
    return {"present_value": round(pv, 6), "reversible": True}
