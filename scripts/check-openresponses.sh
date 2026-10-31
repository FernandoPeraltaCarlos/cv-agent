#!/usr/bin/env bash
# Run upstream TEXT acceptance tests against an already running API.
set -euo pipefail
cd "$(dirname "$0")/.."
checkout=.runtime/compliance/openresponses
upstream_commit=dce9ddb91921427c2ba06901c7dfaf0cc7056799
if [[ ! -d "$checkout/.git" ]]; then
    mkdir -p .runtime/compliance
    git clone --no-checkout https://github.com/openresponses/openresponses.git "$checkout"
    git -C "$checkout" checkout "$upstream_commit"
fi
if [[ "$(git -C "$checkout" rev-parse HEAD)" != "$upstream_commit" ]]; then
    printf '%s\n' 'Unexpected upstream revision. Use the pinned official checkout.' >&2
    exit 1
fi
if [[ ! -f .runtime/compliance/node_modules/tsx/dist/cli.mjs ]]; then
    npm install --prefix .runtime/compliance --no-audit --no-fund tsx@4.23.15 zod@4.6.7
fi
mkdir -p reports
.venv/bin/python scripts/check_openresponses.py "$@" > reports/openresponses.json
printf '%s\n' 'Official text acceptance results: reports/openresponses.json'
