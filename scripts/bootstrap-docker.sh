#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker_cmd=(docker)
if [[ "${1:-}" == "--sudo" ]]; then
    docker_cmd=(sudo docker)
elif [[ -n "${1:-}" ]]; then
    printf '%s\n' 'Usage: bash scripts/bootstrap-docker.sh [--sudo]' >&2
    exit 2
fi
if [[ ! -s .secrets/api_key ]]; then
    umask 077
    mkdir -p .secrets
    python3 -c 'import pathlib,secrets; pathlib.Path(".secrets/api_key").write_text("cv_"+secrets.token_urlsafe(40)+"\n")'
fi
"${docker_cmd[@]}" compose -f compose.yaml -f compose.bootstrap.yaml up --wait --wait-timeout 90 --build ollama
"${docker_cmd[@]}" compose -f compose.yaml -f compose.bootstrap.yaml exec -T ollama /bin/sh -ec 'ollama pull "$OLLAMA_MODEL"'
"${docker_cmd[@]}" compose -f compose.yaml up --wait --wait-timeout 90 --build --force-recreate ollama api gateway
printf '%s\n' 'Services started with private networking. Profile approval and ingress/DNS must be configured before production readiness.'
