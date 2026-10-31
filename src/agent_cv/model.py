import json
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import Settings
from .errors import APIError
from .profile import Fact


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(answer|unknown|out_of_scope)$")
    fact_ids: list[str] = Field(max_length=3)


class EvidenceIDs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_ids: list[str] = Field(max_length=3)


@dataclass
class ModelResult:
    selection: Selection
    input_tokens: int = 0
    output_tokens: int = 0


class OllamaSelector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.ollama_url, timeout=settings.model_timeout_seconds, trust_env=False
        )

    async def close(self):
        await self.client.aclose()

    async def ready(self) -> bool:
        try:
            r = await self.client.get("/api/tags", timeout=3)
            r.raise_for_status()
            return any(
                m.get("name") == self.settings.ollama_model for m in r.json().get("models", [])
            )
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return False

    async def select(self, question: str, previous_user: str, facts: list[Fact]) -> ModelResult:
        schema = EvidenceIDs.model_json_schema()
        schema["properties"]["fact_ids"]["items"] = {
            "type": "string",
            "enum": [f.id for f in facts],
        }
        evidence = [{"id": f.id, "texto": f.text_es} for f in facts]
        payload = {
            "model": self.settings.ollama_model,
            "think": False,
            "stream": False,
            "keep_alive": "5m",
            "format": schema,
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": self.settings.model_context,
                "num_predict": 120,
                "num_thread": self.settings.model_threads,
                "num_batch": 128,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Selecciona el hecho del CV que responde directamente la pregunta. "
                        "Responde JSON con fact_ids: uno a tres IDs. "
                        "Una coincidencia de palabras no es evidencia. "
                        "Si no se documenta la habilidad, certificación, título, empresa o cantidad preguntada, usa []. "
                        "Si pregunta una cifra, elige solo el hecho con esa métrica. "
                        "Formación no implica empleo y estudios en curso no son títulos terminados. "
                        'Ejemplo de formato: {"fact_ids":["id-del-hecho"]}.'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "pregunta": question,
                            "hechos": evidence,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        try:
            r = await self.client.post("/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            if data.get("done_reason") == "length":
                raise APIError(
                    502, "invalid_model_output", "The model did not complete evidence selection."
                )
            ids = EvidenceIDs.model_validate_json(data["message"]["content"]).fact_ids
            selection = Selection(decision="answer" if ids else "unknown", fact_ids=ids)
            allowed = {f.id for f in facts}
            if not set(selection.fact_ids) <= allowed or (
                selection.decision == "answer" and not selection.fact_ids
            ):
                raise APIError(
                    502, "invalid_model_output", "The model returned invalid evidence references."
                )
            return ModelResult(
                selection, data.get("prompt_eval_count", 0), data.get("eval_count", 0)
            )
        except httpx.TimeoutException as exc:
            raise APIError(
                504, "model_timeout", "The local model exceeded its time budget."
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise APIError(
                502,
                "model_unavailable",
                "The local model is unavailable or returned an invalid response.",
            ) from exc
