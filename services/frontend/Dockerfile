# frontend service image
# Build context is the REPO ROOT, not this folder, because dependencies are
# resolved from the monorepo-wide pyproject.toml + poetry.lock:
#   docker build -f services/frontend/Dockerfile -t fis-frontend .
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

# Copied before the source so dependency layers stay cached across code edits.
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY services/frontend/app ./app

EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
