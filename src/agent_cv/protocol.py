import copy
import json
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .errors import APIError


class ResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model: str | None = Field(default=None, max_length=100)
    input: str | list[dict[str, Any]]
    previous_response_id: str | None = Field(default=None, max_length=100)
    stream: bool = False
    store: bool = True
    instructions: str | None = Field(default=None, max_length=2000)
    max_output_tokens: int | None = Field(default=None, ge=1, le=4096)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    tools: list[dict] | None = Field(default=None, max_length=0)
    tool_choice: Literal["none", "auto"] | None = None
    parallel_tool_calls: bool | None = None
    truncation: Literal["disabled", "auto"] = "disabled"
    metadata: dict[str, str] | None = None
    text: dict | None = None
    reasoning: dict | None = None
    stream_options: dict | None = None
    background: Literal[False] = False
    include: list[str] | None = Field(default=None, max_length=0)
    safety_identifier: str | None = Field(default=None, max_length=100)
    prompt_cache_key: str | None = Field(default=None, max_length=100)

    def messages(self) -> list[dict]:
        if self.text:
            output_format = self.text.get("format", {})
            if not isinstance(output_format, dict) or output_format.get("type", "text") != "text":
                raise APIError(400, "unsupported_format", "Only text output is supported.", "text")
        if self.metadata and (
            len(self.metadata) > 16
            or any(len(k) > 64 or len(v) > 512 for k, v in self.metadata.items())
        ):
            raise APIError(400, "invalid_metadata", "Metadata exceeds protocol limits.", "metadata")
        if isinstance(self.input, str):
            result = [{"role": "user", "content": self.input}]
        else:
            result = []
            for item in self.input:
                role = item.get("role")
                if (
                    item.get("type", "message") != "message"
                    or not isinstance(role, str)
                    or role
                    not in {
                        "user",
                        "assistant",
                        "system",
                        "developer",
                    }
                ):
                    raise APIError(
                        400, "unsupported_input", "Only text message items are supported.", "input"
                    )
                content = item.get("content")
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if (
                            not isinstance(part, dict)
                            or not isinstance(part.get("type"), str)
                            or part.get("type") not in {"input_text", "output_text", "text"}
                            or not isinstance(part.get("text"), str)
                        ):
                            raise APIError(
                                400,
                                "unsupported_input",
                                "Only text content parts are supported.",
                                "input",
                            )
                        parts.append(part["text"])
                    content = "\n".join(parts)
                if not isinstance(content, str):
                    raise APIError(400, "invalid_input", "Message content must be text.", "input")
                # Accept client system/developer messages for wire compatibility, but grant no authority.
                if role in {"user", "assistant"}:
                    result.append({"role": role, "content": content})
        if not result or result[-1]["role"] != "user" or not result[-1]["content"].strip():
            raise APIError(
                400,
                "invalid_input",
                "The last conversational message must be a nonempty user message.",
                "input",
            )
        return result


def response_object(
    request: ResponseRequest, settings: Settings, response_id: str, created: int
) -> dict:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created,
        "completed_at": None,
        "status": "in_progress",
        "incomplete_details": None,
        "model": settings.public_model,
        "previous_response_id": request.previous_response_id,
        "instructions": None,
        "output": [],
        "error": None,
        "tools": [],
        "tool_choice": "none",
        "truncation": request.truncation,
        "parallel_tool_calls": False,
        "text": {"format": {"type": "text"}},
        "top_p": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "top_logprobs": 0,
        "temperature": 0.0,
        "reasoning": None,
        "usage": None,
        "max_output_tokens": request.max_output_tokens,
        "max_tool_calls": 0,
        "store": request.store,
        "background": False,
        "service_tier": "default",
        "metadata": request.metadata or {},
        "safety_identifier": None,
        "prompt_cache_key": None,
    }


def complete_response(response: dict, text: str, input_tokens: int, output_tokens: int) -> dict:
    response = copy.deepcopy(response)
    response.update(status="completed", completed_at=int(time.time()))
    response["output"] = [
        {
            "type": "message",
            "id": "msg_" + uuid.uuid4().hex,
            "status": "completed",
            "role": "assistant",
            "phase": "final_answer",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
    ]
    response["usage"] = {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": input_tokens + output_tokens,
    }
    return response


def event(name: str, sequence: int, **data) -> str:
    payload = {"type": name, "sequence_number": sequence, **data}
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def text_events(response: dict, start: int = 2):
    """Emit complete item/content lifecycles, with immutable snapshots."""
    item = response["output"][0]
    final_part = item["content"][0]
    empty_part = {**final_part, "text": ""}
    sequence = start
    yield event(
        "response.output_item.added",
        sequence,
        output_index=0,
        item={**item, "status": "in_progress", "content": []},
    )
    sequence += 1
    common = {"item_id": item["id"], "output_index": 0, "content_index": 0}
    yield event("response.content_part.added", sequence, **common, part=empty_part)
    sequence += 1
    text = final_part["text"]
    for offset in range(0, len(text), 80):
        yield event(
            "response.output_text.delta", sequence, **common, delta=text[offset : offset + 80]
        )
        sequence += 1
    yield event("response.output_text.done", sequence, **common, text=text)
    sequence += 1
    yield event("response.content_part.done", sequence, **common, part=final_part)
    sequence += 1
    yield event("response.output_item.done", sequence, output_index=0, item=item)
    sequence += 1
    yield event("response." + response["status"], sequence, response=response)
