# Agent Runtime (R3) - bounded agent loop with an explicit autonomy + cost budget.
from dataclasses import dataclass, field

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent Runtime", version="0.1.0")
SERVICE, RELEASE = "agent_runtime", "R3"


@dataclass
class AutonomyBudget:
    # Autonomy is BOTH a safety budget and a cost budget (syllabus, Session 6).
    max_steps: int = 6
    max_tool_calls: int = 8
    max_cost_usd: float = 0.25
    require_approval_for: tuple = ("place_order",)


@dataclass
class RunState:
    steps: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0
    trace: list = field(default_factory=list)


class Goal(BaseModel):
    goal: str


def within_budget(s: RunState, b: AutonomyBudget) -> bool:
    return s.steps < b.max_steps and s.tool_calls < b.max_tool_calls and s.cost_usd < b.max_cost_usd


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.post("/run")
def run(g: Goal):
    budget, state = AutonomyBudget(), RunState()
    # TODO: real plan/act loop calling tool_registry via the model_gateway.
    while within_budget(state, budget):
        state.steps += 1
        state.trace.append({"step": state.steps, "action": "noop", "reason": "stub"})
        break  # stub stops immediately; a real loop stops on goal/failure/budget.
    return {
        "goal": g.goal,
        "stopped_reason": "stub",
        "steps": state.steps,
        "cost_usd": state.cost_usd,
        "trace": state.trace,
    }
