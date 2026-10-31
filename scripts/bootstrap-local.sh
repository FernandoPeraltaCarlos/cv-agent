#!/usr/bin/env bash
# A CPU-only user installation. Does not install system packages or change Docker permissions.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v zstd >/dev/null || { printf '%s\n' 'Install zstd to extract the official Ollama archive.' >&2; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
mkdir -p .runtime/ollama
archive=.runtime/ollama-linux-amd64.tar.zst
if [[ ! -x .runtime/ollama/bin/ollama ]]; then
    curl -fL --retry 2 --output "$archive" https://github.com/ollama/ollama/releases/download/v0.40.13/ollama-linux-amd64.tar.zst
    printf '%s\n' 'c9490e0f520be21271d969e6703f012268b1d39f8b70dd58854e5bfef7a75bb6  .runtime/ollama-linux-amd64.tar.zst' | sha256sum --check
    tar --zstd -xf "$archive" -C .runtime/ollama --wildcards --no-wildcards-match-slash \
        bin/ollama 'lib/ollama/*.so*' lib/ollama/llama-server 'lib/ollama/*LICENSE*' 'lib/ollama/*NOTICE*'
fi
if [[ ! -s .secrets/api_key ]]; then
    .venv/bin/agent-cv init-secret
fi
printf '%s\n' 'Installed. Start scripts/run-model-local.sh, pull qwen2.5:1.5b, then run the API. See README.md.'
