#!/usr/bin/env bash
# Evaluate the real model from the API container on its final private network.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports
python3 - <<'PY' | bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml exec -T api python -c 'import sys; from pathlib import Path; Path("/tmp/evaluation-cases.json").write_text(sys.stdin.read())'
import json
from pathlib import Path
cases=sum((json.loads(Path(name).read_text()) for name in ('eval/cases.json', 'eval/paraphrases.json', 'eval/consolidated.json', 'eval/employers.json')), [])
print(json.dumps(cases,ensure_ascii=False))
PY
evaluation_exit=0
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml exec -T api \
    python -m agent_cv.cli evaluate --cases /tmp/evaluation-cases.json --output /tmp/evaluation.json || evaluation_exit=$?
# Read through exec: archive/cp may not see a rootless container's tmpfs mounts.
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml exec -T api cat /tmp/evaluation.json > reports/docker-evaluation.json
exit "$evaluation_exit"
