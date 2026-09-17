# MCP Server (R3)
# Exposes a finance capability over MCP with documented trust boundaries.
from fastapi import FastAPI

app = FastAPI(title="MCP Server", version="0.1.0")

SERVICE = "mcp_server"
RELEASE = "R3"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Exposes a finance capability over MCP with documented trust boundaries.",
        "docs": "/docs",
    }
