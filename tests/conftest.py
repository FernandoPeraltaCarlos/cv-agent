from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_cv.app import create_app
from agent_cv.config import Settings
from agent_cv.model import ModelResult, Selection


class StubSelector:
    """Only used for transport tests; never for model quality evaluation."""

    calls = 0

    async def ready(self):
        return True

    async def close(self):
        pass

    async def select(self, question, previous_user, facts):
        self.calls += 1
        return ModelResult(Selection(decision="answer", fact_ids=[facts[0].id]), 40, 10)


@pytest.fixture
def settings(tmp_path):
    secret = tmp_path / "key"
    secret.write_text("test-" + "a" * 40)
    return Settings(
        _env_file=None,
        api_key_file=secret,
        profile_path=Path("data/profile.json"),
        state_path=tmp_path / "state.sqlite3",
        allow_draft_profile=True,
        requests_per_minute=200,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, StubSelector())) as client:
        client.headers["Authorization"] = "Bearer " + settings.api_key
        yield client
