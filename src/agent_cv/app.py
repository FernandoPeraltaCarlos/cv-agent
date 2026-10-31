import asyncio
import hashlib
import hmac
import logging
import time
import uuid
from collections import Counter, deque
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .agent import Agent
from .config import Settings
from .errors import APIError
from .model import OllamaSelector
from .profile import Profile
from .protocol import ResponseRequest, complete_response, event, response_object, text_events
from .state import ResponseStore

logger = logging.getLogger("agent_cv")
bearer = HTTPBearer(auto_error=False)


class BodyLimit:
    """Bound streamed bodies too, without trusting Content-Length or blocking forever."""

    def __init__(self, app, maximum: int):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if headers.get(b"content-type", b"").split(b";")[0].lower() != b"application/json":
            return await JSONResponse(
                APIError(415, "unsupported_media_type", "Use application/json.").body(),
                status_code=415,
            )(scope, receive, send)
        body = bytearray()
        try:
            async with asyncio.timeout(15):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > self.maximum:
                        return await JSONResponse(
                            APIError(413, "body_too_large", "Request body is too large.").body(),
                            status_code=413,
                        )(scope, receive, send)
                    if not message.get("more_body"):
                        break
        except TimeoutError:
            return await JSONResponse(
                APIError(400, "body_timeout", "Request body timed out.").body(), status_code=408
            )(scope, receive, send)
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class ResponseMetadata:
    """Pure ASGI middleware preserves disconnect/cancellation semantics."""

    def __init__(self, app, metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = ("req_" + uuid.uuid4().hex).encode()

        async def send_with_metadata(message):
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", request_id),
                        (b"x-content-type-options", b"nosniff"),
                        (b"cache-control", b"no-store"),
                    ],
                }
                if scope["path"].startswith("/v1/"):
                    self.metrics["requests"] += 1
                    self.metrics["http_seconds"] += time.monotonic() - started
            await send(message)

        await self.app(scope, receive, send_with_metadata)


def create_app(settings: Settings | None = None, selector=None) -> FastAPI:
    settings = settings or Settings()
    metrics = Counter()
    rate = deque()
    worker = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _ = settings.api_key  # Fail startup if a proper secret is missing. Never log its value.
        profile = Profile.load(settings.profile_path)
        app.state.profile = profile
        app.state.selector = selector or OllamaSelector(settings)
        app.state.agent = Agent(profile, app.state.selector)
        app.state.store = ResponseStore(
            settings.state_path, settings.response_ttl_seconds, settings.max_stored_responses
        )
        app.state.metrics = metrics
        app.state.worker = worker
        try:
            yield
        finally:
            await app.state.selector.close()

    app = FastAPI(
        title="Fernando Peralta CV Agent",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(BodyLimit, maximum=settings.max_body_bytes)
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(ResponseMetadata, metrics=metrics)

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        metrics["errors"] += 1
        headers = {"Retry-After": "5"} if exc.status == 429 else {}
        if exc.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(exc.body(), status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # Pydantic's usual error body can echo the caller's input and credentials.
        return JSONResponse(
            APIError(
                400,
                "invalid_request",
                "Invalid or unsupported request fields; see the documented text API contract.",
            ).body(),
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        metrics["errors"] += 1
        logger.error("unexpected_error type=%s", type(exc).__name__)
        return JSONResponse(
            APIError(500, "server_error", "An internal error occurred.").body(), status_code=500
        )

    async def authenticated(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        if credentials is None or not hmac.compare_digest(
            credentials.credentials.encode(), settings.api_key.encode()
        ):
            raise APIError(401, "invalid_api_key", "A valid Bearer API key is required.")
        return hashlib.sha256(credentials.credentials.encode()).hexdigest()

    def check_profile():
        if not app.state.profile.approved and not settings.allow_draft_profile:
            raise APIError(
                503, "profile_not_approved", "The professional profile is awaiting owner review."
            )

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readiness(owner: str = Depends(authenticated)):
        check_profile()
        if not await app.state.selector.ready():
            raise APIError(
                503, "model_not_ready", "The configured local model is not loaded or available."
            )
        return {
            "status": "ready",
            "profile_version": app.state.profile.version,
            "profile_approved": app.state.profile.approved,
            "model": settings.ollama_model,
        }

    @app.get("/metrics")
    async def prometheus(owner: str = Depends(authenticated)):
        lines = [f"agent_cv_{key}_total {value}" for key, value in sorted(metrics.items())]
        lines.append(f"agent_cv_busy {int(worker.locked())}")
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @app.get("/v1/models")
    async def models(owner: str = Depends(authenticated)):
        return {
            "object": "list",
            "data": [
                {
                    "id": settings.public_model,
                    "object": "model",
                    "created": 0,
                    "owned_by": "fernando-peralta",
                }
            ],
        }

    @app.get("/v1/models/{model_id}")
    async def model(model_id: str, owner: str = Depends(authenticated)):
        if model_id != settings.public_model:
            raise APIError(404, "model_not_found", "Model not found.")
        return {
            "id": settings.public_model,
            "object": "model",
            "created": 0,
            "owned_by": "fernando-peralta",
        }

    @app.get("/v1/responses/{response_id}")
    async def get_response(response_id: str, owner: str = Depends(authenticated)):
        _, response = await asyncio.to_thread(app.state.store.get, owner, response_id)
        return response

    @app.delete("/v1/responses/{response_id}")
    async def delete_response(response_id: str, owner: str = Depends(authenticated)):
        await asyncio.to_thread(app.state.store.delete, owner, response_id)
        return {"id": response_id, "object": "response", "deleted": True}

    @app.post("/v1/responses")
    async def responses(
        payload: ResponseRequest, request: Request, owner: str = Depends(authenticated)
    ):
        check_profile()
        now = time.monotonic()
        while rate and rate[0] <= now - 60:
            rate.popleft()
        if len(rate) >= settings.requests_per_minute:
            raise APIError(429, "rate_limit_exceeded", "Request rate limit exceeded.")
        rate.append(now)
        messages = payload.messages()
        question = messages[-1]["content"]
        if len(question) > settings.max_question_chars:
            raise APIError(
                400,
                "question_too_long",
                "The latest question exceeds the supported length.",
                "input",
            )
        if payload.previous_response_id:
            history, _ = await asyncio.to_thread(
                app.state.store.get, owner, payload.previous_response_id
            )
            messages = history + messages
        if sum(len(m["content"]) for m in messages) > settings.max_context_chars:
            if payload.truncation == "disabled":
                raise APIError(
                    400,
                    "context_length_exceeded",
                    "Conversation exceeds the context budget; start a new conversation or use truncation=auto.",
                    "input",
                )
            while (
                len(messages) > 1
                and sum(len(m["content"]) for m in messages) > settings.max_context_chars
            ):
                messages.pop(0)
        previous_user = app.state.agent.retriever.conversation_context(messages[:-1])
        if worker.locked():
            raise APIError(429, "model_busy", "The local model is busy; retry shortly.")
        await worker.acquire()
        initial = response_object(payload, settings, "resp_" + uuid.uuid4().hex, int(time.time()))

        async def generate():
            started = time.monotonic()
            try:
                async with asyncio.timeout(settings.model_timeout_seconds + 2):
                    answer = await app.state.agent.answer(question, previous_user)
                result = complete_response(
                    initial, answer.text, answer.input_tokens, answer.output_tokens
                )
                # A byte ceiling is deliberately conservative: a byte-level tokenizer cannot
                # produce more tokens than UTF-8 bytes. Never claim exact public token counts.
                if (
                    payload.max_output_tokens is not None
                    and len(answer.text.encode()) > payload.max_output_tokens
                ):
                    text = answer.text.encode()[: payload.max_output_tokens].decode(
                        "utf-8", errors="ignore"
                    )
                    result["output"][0]["content"][0]["text"] = text
                    result["output"][0]["status"] = "incomplete"
                    result.update(
                        status="incomplete",
                        incomplete_details={"reason": "max_output_tokens"},
                        completed_at=None,
                    )
                if payload.store:
                    completed_history = messages + [
                        {"role": "assistant", "content": result["output"][0]["content"][0]["text"]}
                    ]
                    await asyncio.to_thread(app.state.store.save, owner, result, completed_history)
                metrics[f"decision_{answer.decision}"] += 1
                metrics["model_input_tokens"] += answer.input_tokens
                metrics["model_output_tokens"] += answer.output_tokens
                return result
            except TimeoutError as exc:
                raise APIError(504, "model_timeout", "The model exceeded its time budget.") from exc
            finally:
                metrics["generation_seconds"] += time.monotonic() - started

        async def stream():
            task = None
            try:
                yield event("response.created", 0, response=initial)
                yield event("response.in_progress", 1, response=initial)
                task = asyncio.create_task(generate())
                while not task.done():
                    done, _ = await asyncio.wait({task}, timeout=2)
                    if not done:
                        yield ": keep-alive\n\n"
                result = await task
                for chunk in text_events(result):
                    yield chunk
                yield "data: [DONE]\n\n"
            except APIError as exc:
                metrics["errors"] += 1
                failed = {
                    **initial,
                    "status": "failed",
                    "error": {"code": exc.code, "message": exc.message},
                }
                yield event("response.failed", 2, response=failed)
            except Exception:
                metrics["errors"] += 1
                failed = {
                    **initial,
                    "status": "failed",
                    "error": {"code": "server_error", "message": "Generation failed."},
                }
                yield event("response.failed", 2, response=failed)
            finally:
                if task and not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                worker.release()

        if payload.stream:
            return StreamingResponse(
                stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
            )
        task = asyncio.create_task(generate())
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=0.5)
                if not done and await request.is_disconnected():
                    raise APIError(400, "client_disconnected", "The client disconnected.")
            return await task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            worker.release()

    return app


def factory():
    return create_app()
