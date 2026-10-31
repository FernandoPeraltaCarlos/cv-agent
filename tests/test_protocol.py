import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA = json.loads(Path("tests/schemas/openresponses-2026-04-24.json").read_text())


def validate(name, instance):
    Draft202012Validator(
        {"$ref": "#/components/schemas/" + name, "components": SCHEMA["components"]}
    ).validate(instance)


def test_response_matches_official_schema(client):
    r = client.post("/v1/responses", json={"input": "HSBC"})
    assert r.status_code == 200
    validate("ResponseResource", r.json())


@pytest.mark.parametrize("limit", [None, 10])
def test_sse_official_schema_and_lifecycle(client, limit):
    payload = {"input": "HSBC", "stream": True}
    if limit:
        payload["max_output_tokens"] = limit
    r = client.post("/v1/responses", json=payload)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: {")]
    by_type = {
        s["properties"]["type"]["enum"][0]: name
        for name, s in SCHEMA["components"]["schemas"].items()
        if name.endswith("StreamingEvent") and "enum" in s.get("properties", {}).get("type", {})
    }
    for e in events:
        validate(by_type[e["type"]], e)
    assert [e["sequence_number"] for e in events] == list(range(len(events)))
    names = [e["type"] for e in events]
    assert names[:4] == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.content_part.added",
    ]
    assert events[0]["response"]["output"] == []
    assert events[2]["item"]["content"] == []
    assert events[3]["part"]["text"] == ""
    final = events[-1]["response"]
    assert final["status"] == ("incomplete" if limit else "completed")
    assert names[-1] == "response." + final["status"]
    deltas = "".join(e["delta"] for e in events if e["type"] == "response.output_text.delta")
    assert deltas == final["output"][0]["content"][0]["text"]
    assert {e["item_id"] for e in events if "item_id" in e} == {final["output"][0]["id"]}
    if limit:
        assert len(deltas.encode()) <= limit


def test_history_preserves_assistant_phase(client):
    r = client.post(
        "/v1/responses",
        json={
            "input": [
                {
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [
                        {"type": "output_text", "text": "Previous answer", "annotations": []}
                    ],
                },
                {"role": "user", "content": [{"type": "input_text", "text": "Hola"}]},
            ]
        },
    )
    assert r.status_code == 200
    validate("ResponseResource", r.json())
    assert r.json()["output"][0]["phase"] == "final_answer"
