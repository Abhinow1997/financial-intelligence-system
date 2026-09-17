from pydantic import BaseModel


class Prediction(BaseModel):
    probability: float
    threshold: float
    decision: str
    model_version: str
