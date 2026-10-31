#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
exec docker --host "unix://$project_dir/.runtime/docker-run/docker.sock" "$@"
