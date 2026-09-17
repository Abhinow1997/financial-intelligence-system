#!/usr/bin/env bash
set -euo pipefail
# Start the core stack
docker compose --profile core up --build
