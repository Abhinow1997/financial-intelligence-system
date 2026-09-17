# Architecture

The Financial Intelligence System is a **monorepo of small Python services** behind a
single gateway, sharing a data backbone and a platform spine. It is deliberately shaped
like the syllabus's lifecycle so each release slots into an existing seam.

## 1. System context

```
                         +-----------------------------+
   Analyst  ───────────► |     frontend (Streamlit)    |
                         +--------------+--------------+
                                        │
                                        ▼
                         +-----------------------------+
                         |     gateway (FastAPI)       |  auth · routing · redaction · audit
                         +--------------+--------------+
                                        │
                                        ▼
                         +-----------------------------+
                         |     backend (orchestration) |
                         +--+------+--------+-------+---+
                            │      │        │       │
             ┌──────────────┘      │        │       └──────────────┐
             ▼                     ▼        ▼                      ▼
   analytics/model_service   rag/retriever  agents/agent_runtime   platform/*
   (predict, R1)             (ground, R2)   (act, R3)              (gateway/registry/
             ▲                     ▲        │  policy/telemetry/finops)
             │                     │        ▼
      analytics/feature_store   rag/indexer  agents/tool_registry ──► integration/* (broker, edgar, marketdata)
             ▲                     ▲
             └──────── ingestion/* (market_data · filings · news · altdata)
```

## 2. Big-data lifecycle → services

`sources → ingestion → storage → transformation → feature/context → compute → model → serving → feedback → monitoring`

| Stage | Where it lives |
|---|---|
| Sources | market data, SEC filings, news/events, alt-data |
| Ingestion | [`services/ingestion/*`](services/ingestion) (workers; batch + stream) |
| Storage | Postgres (structured), MinIO (objects/PDFs), Qdrant (vectors), Redpanda (events) |
| Transformation / features | [`services/analytics/feature_store`](services/analytics/feature_store) |
| Compute / model | [`services/analytics/model_service`](services/analytics/model_service) |
| Context / retrieval | [`services/rag/*`](services/rag) |
| Serving | [`services/backend`](services/backend), [`services/gateway`](services/gateway), [`services/frontend`](services/frontend) |
| Feedback / monitoring | [`services/platform/observability`](services/platform/observability), [`services/evaluation`](services/evaluation) |

Details: [`docs/architecture/data-lifecycle.md`](docs/architecture/data-lifecycle.md).

## 3. Three layers (application / platform / foundation)

The syllabus insists you separate **application** from **platform** from **foundation**.
That is why platform concerns are their own services, not baked into the app:

- **Application** — frontend, backend, the domain services (analytics, rag, agents).
- **Platform** — [`services/platform/*`](services/platform): model gateway (model abstraction,
  routing/cascade, prompt cache), prompt/config registry (versioned mutable artifacts),
  policy engine (approvals, HITL, kill switch), observability (traces, cost/latency, drift),
  FinOps (cost metering). Plus the [`gateway`](services/gateway) and shared retrieval.
- **Foundation** — external model providers and managed datastores.

Reference platform: [`docs/architecture/platform-reference.md`](docs/architecture/platform-reference.md).

## 4. Typed interfaces (contracts)

Services talk over HTTP with **Pydantic-typed** request/response bodies. Shared contracts
live in [`libs/fin_schemas`](libs/fin_schemas) so a tool's inputs are validated the same way
everywhere. Principle from the course: *models interpret ambiguity; software enforces rules.*

## 5. Autonomy & safety boundaries

- Tools are tagged **read-only** vs **state-changing** and **reversible** vs **irreversible**
  ([`services/agents/tool_registry`](services/agents/tool_registry)).
- The agent runs under an explicit **autonomy + cost budget** — `max_steps`, `max_tool_calls`,
  `max_cost_usd`, and an approval list ([`services/agents/agent_runtime`](services/agents/agent_runtime)).
- Any state-changing action (e.g. the [broker connector](services/integration/broker_connector))
  routes through the **policy engine** approval gate.

## 6. Cross-cutting economics

Every request can be measured for **cost** and **latency** via
[`libs/fin_telemetry`](libs/fin_telemetry); [`services/platform/finops`](services/platform/finops)
rolls those up into the standing five-line unit-economics table
([`docs/economics/unit_economics_template.md`](docs/economics/unit_economics_template.md)).

## 7. Release path (R6)

`dev → eval gate → staging → shadow → canary → limited → general → expanded autonomy`

The blocking **eval gate** is [`scripts/run_eval_gate.py`](scripts/run_eval_gate.py), wired into
CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Mutable artifacts (prompts, tool
defs, indices, model snapshots, eval sets) are versioned via the prompt/config registry.

## 8. Why a monorepo

One clone, one history, one PR review surface — the right shape for a class building **one**
system together and learning git. If a service later needs its own repo, it is already isolated
under `services/<domain>/<service>` and can be extracted with `git subtree split`.
