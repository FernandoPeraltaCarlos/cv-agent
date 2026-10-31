"""Use the existing secret file without placing a credential in argv or shell history."""

import argparse
import json
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8011/v1")
parser.add_argument("--key-file", type=Path, default=Path(".secrets/api_key"))
args = parser.parse_args()
headers = {"Authorization": "Bearer " + args.key_file.read_text().strip()}
with httpx.Client(base_url=args.base_url, headers=headers, timeout=60, trust_env=False) as client:
    first = client.post("/responses", json={"model": "cv-fernando", "input": "¿Qué hizo en HSBC?"})
    first.raise_for_status()
    print(json.dumps(first.json(), indent=2, ensure_ascii=False))
    with client.stream(
        "POST",
        "/responses",
        json={
            "input": "¿Y qué extensión desarrolló allí?",
            "previous_response_id": first.json()["id"],
            "stream": True,
            "store": False,
        },
    ) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines():
            print(line)
