"""Keep the credential out of process arguments and compliance report output."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = os.environ.copy()
env["OPENRESPONSES_API_KEY"] = (root / ".secrets/api_key").read_text().strip()
command = [
    shutil.which("node") or "node",
    str(root / ".runtime/compliance/node_modules/tsx/dist/cli.mjs"),
    str(root / ".runtime/compliance/openresponses/bin/compliance-test.ts"),
    "--base-url",
    sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011/v1",
    "--model",
    "cv-fernando",
]
results = []
# Upstream runs templates concurrently. Execute each unchanged template in its
# own invocation to respect this CPU service's documented single-request slot.
for case_id in [
    "basic-response",
    "assistant-phase",
    "streaming-response",
    "system-prompt",
    "multi-turn",
]:
    completed = subprocess.run(
        [*command, "--filter", case_id, "--json"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    try:
        report = json.loads(completed.stdout)
        results.extend(report["results"])
    except (ValueError, KeyError):
        results.append(
            {
                "id": case_id,
                "status": "failed",
                "errors": ["Official runner did not produce a JSON report."],
            }
        )
summary = {
    "passed": sum(r["status"] == "passed" for r in results),
    "failed": sum(r["status"] == "failed" for r in results),
    "skipped": sum(r["status"] == "skipped" for r in results),
    "total": len(results),
}
output = json.dumps(
    {
        "summary": summary,
        "execution": "sequential official templates; service concurrency=1",
        "results": results,
    },
    indent=2,
    ensure_ascii=False,
)
print(output.replace(env["OPENRESPONSES_API_KEY"], "[REDACTED]"))
raise SystemExit(1 if summary["failed"] else 0)
