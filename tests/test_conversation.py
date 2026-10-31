from fastapi.testclient import TestClient

from agent_cv.app import create_app

from .conftest import StubSelector


def test_subject_survives_multiple_followups_and_topic_changes(settings):
    class Tracking(StubSelector):
        observed = []

        async def select(self, question, previous_user, facts):
            self.observed.append(facts)
            return await super().select(question, previous_user, facts)

    selector = Tracking()
    with TestClient(create_app(settings, selector)) as client:
        client.headers["Authorization"] = "Bearer " + settings.api_key
        previous = None
        for question in [
            "¿Qué hizo en HSBC?",
            "¿Y qué tecnologías usó allí?",
            "¿Y cuántos tickets gestionó?",
        ]:
            payload = {"input": question}
            if previous:
                payload["previous_response_id"] = previous
            response = client.post("/v1/responses", json=payload)
            assert response.status_code == 200
            previous = response.json()["id"]
        assert all("HSBC" in fact.tags for fact in selector.observed[-1])

        switched = client.post(
            "/v1/responses", json={"input": "¿Qué hizo en COFAA?", "previous_response_id": previous}
        )
        assert switched.status_code == 200
        assert all("COFAA" in fact.tags for fact in selector.observed[-1])

        general = client.post(
            "/v1/responses",
            json={
                "input": "En general, ¿qué tecnologías usa?",
                "previous_response_id": switched.json()["id"],
            },
        )
        assert general.status_code == 200
        assert any("COFAA" not in fact.tags for fact in selector.observed[-1])
