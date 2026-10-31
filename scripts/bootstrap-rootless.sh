#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ingress_files=()
if [[ "${1:-}" == "--coolify" ]]; then
    ingress_files=(-f compose.coolify.yaml)
    mkdir -p .runtime
    touch .runtime/use-private-ingress
elif [[ -n "${1:-}" ]]; then
    printf '%s\n' 'Usage: bash scripts/bootstrap-rootless.sh [--coolify]' >&2
    exit 2
fi
bash scripts/start-docker-rootless.sh
python3 - <<'PY'
import os, secrets, tempfile
from pathlib import Path
directory=Path('.secrets')
directory.mkdir(mode=0o700, exist_ok=True)
directory.chmod(0o700)
canonical=directory/'api_key'
if not canonical.exists():
    fd=os.open(canonical, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as output: output.write('cv_'+secrets.token_urlsafe(40)+'\n')
fd,temporary=tempfile.mkstemp(prefix='.rootless-',dir=directory)
with os.fdopen(fd,'w') as output: output.write(canonical.read_text())
os.chmod(temporary,0o444)
os.replace(temporary,directory/'rootless_api_key')
PY
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml "${ingress_files[@]}" -f compose.bootstrap.yaml up --wait --wait-timeout 90 --build ollama
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml "${ingress_files[@]}" -f compose.bootstrap.yaml exec -T ollama /bin/sh -ec 'ollama pull "$OLLAMA_MODEL"'
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml "${ingress_files[@]}" up --wait --wait-timeout 90 --build --force-recreate ollama api gateway
printf '%s\n' 'Rootless containers started on loopback with the private runtime network.'
