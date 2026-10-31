"""Wait for this VPS's private ingress bridge before rootless port restoration."""

import json
import os
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if (root / ".runtime/use-private-ingress").exists():
    address = os.environ.get("COOLIFY_GATEWAY_IP", "172.19.0.1")
    for _attempt in range(90):
        result = subprocess.run(
            ["/usr/sbin/ip", "-j", "-4", "address", "show"],
            capture_output=True,
            text=True,
            check=True,
        )
        interfaces = json.loads(result.stdout)
        if any(
            a.get("local") == address
            for interface in interfaces
            for a in interface.get("addr_info", [])
        ):
            break
        time.sleep(1)
    else:
        raise SystemExit(
            "The private ingress bridge is not ready; start the existing Docker daemon or check the configured gateway IP."
        )
