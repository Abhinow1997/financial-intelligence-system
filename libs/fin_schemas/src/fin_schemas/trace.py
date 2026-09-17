from pydantic import BaseModel


class AgentStep(BaseModel):
    step: int
    action: str
    tool: str | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0
