import asyncio
import json

import pytest

from agent_cv.app import create_app

from .conftest import StubSelector


@pytest.mark.parametrize("stream", [False, True])
async def test_disconnect_cancels_generation_and_releases_worker(settings, stream):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class Waiting(StubSelector):
        async def select(self, *args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    app = create_app(settings, Waiting())
    body = json.dumps({"input": "HSBC", "stream": stream}).encode()
    queue = asyncio.Queue()
    queue.put_nowait({"type": "http.request", "body": body, "more_body": False})
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/responses",
        "raw_path": b"/v1/responses",
        "query_string": b"",
        "root_path": "",
        "server": ("test", 80),
        "client": ("127.0.0.1", 1234),
        "headers": [
            (b"content-type", b"application/json"),
            (b"authorization", ("Bearer " + settings.api_key).encode()),
        ],
    }
    async with app.router.lifespan_context(app):
        task = asyncio.create_task(app(scope, queue.get, send))
        await asyncio.wait_for(started.wait(), 5)
        queue.put_nowait({"type": "http.disconnect"})
        await asyncio.wait_for(task, 5)
        assert cancelled.is_set()
        assert not app.state.worker.locked()
