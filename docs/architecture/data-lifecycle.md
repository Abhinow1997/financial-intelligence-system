# Big Data Lifecycle

`sources -> ingestion -> storage -> transformation -> feature/context -> compute -> model -> serving -> feedback -> monitoring`

| Stage | Service(s) |
|---|---|
| Sources | market data, filings, news, alt-data |
| Ingestion | `services/ingestion/*` |
| Storage | postgres (structured), minio (objects), qdrant (vectors) |
| Transformation / Features | `services/analytics/feature_store` |
| Model | `services/analytics/model_service` |
| Context / Retrieval | `services/rag/*` |
| Serving | `services/backend`, `services/gateway`, `services/frontend` |
| Feedback / Monitoring | `services/platform/observability`, `services/evaluation` |
