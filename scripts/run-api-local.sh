#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/uvicorn agent_cv.app:factory --factory --host 127.0.0.1 --port 8011 --workers 1 --no-access-log --no-proxy-headers --limit-concurrency 32
