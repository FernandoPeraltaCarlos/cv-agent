#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export OLLAMA_HOST=127.0.0.1:11435
export OLLAMA_MODELS="${OLLAMA_MODELS:-$PWD/.runtime/models}"
export OLLAMA_NO_CLOUD=1
export OLLAMA_NOHISTORY=1
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_MAX_QUEUE=1
exec "${OLLAMA_BIN:-$PWD/.runtime/ollama/bin/ollama}" serve
