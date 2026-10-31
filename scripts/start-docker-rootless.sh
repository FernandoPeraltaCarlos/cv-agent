#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if bash scripts/docker-rootless.sh info >/dev/null 2>&1; then
    printf '%s\n' 'Project rootless Docker is already running.'
    exit 0
fi
for binary in dockerd-rootless.sh rootlesskit newuidmap slirp4netns; do
    command -v "$binary" >/dev/null || { printf 'Missing rootless prerequisite: %s\n' "$binary" >&2; exit 1; }
done
mkdir -p .runtime/docker-run .runtime/docker-data .runtime/docker-exec
chmod 700 .runtime/docker-run
if systemctl --user is-enabled agent-cv-docker.service >/dev/null 2>&1; then
    systemctl --user start agent-cv-docker.service
else
    nohup env XDG_RUNTIME_DIR="$PWD/.runtime/docker-run" dockerd-rootless.sh \
        --host "unix://$PWD/.runtime/docker-run/docker.sock" \
        --data-root "$PWD/.runtime/docker-data" --exec-root "$PWD/.runtime/docker-exec" \
        > .runtime/docker-daemon.log 2>&1 < /dev/null &
    printf '%s\n' "$!" > .runtime/docker-daemon.pid
fi
for attempt in {1..30}; do
    if bash scripts/docker-rootless.sh info >/dev/null 2>&1; then
        printf '%s\n' 'Project rootless Docker started. The existing Docker context/daemon was not changed.'
        exit 0
    fi
    sleep 1
done
printf '%s\n' 'Rootless Docker did not start; inspect .runtime/docker-daemon.log.' >&2
exit 1
