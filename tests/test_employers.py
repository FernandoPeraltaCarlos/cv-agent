from pathlib import Path

import pytest

from agent_cv.profile import Profile
from agent_cv.retrieval import Retriever


@pytest.mark.parametrize(
    "question",
    [
        "ok, donde ha trabajado?",
        "no sabes donde ha trabajado?",
        "cuales son las empresas donde ha trabajado?",
        "¿Dónde ha trabajado Fernando?",
        "¿En qué compañías ha trabajado?",
        "Dime las organizaciones de su historial laboral",
        "¿Puedes decirme dónde ha trabajado?",
        "Bueno, ¿puedes darme la lista de empresas donde ha trabajado?",
        "¿Me puedes contar en qué empresas estuvo?",
        "¿Cuáles son las empresas documentadas?",
        "Where has Fernando worked?",
        "Can you list the companies he has worked for?",
        "Don't you know where he worked?",
        "Which companies are in his professional background?",
        "Tell me his employment history",
    ],
)
def test_employer_list_retrieves_the_complete_history_despite_conversational_wrappers(question):
    retriever = Retriever(Profile.load(Path("data/profile.json")))
    # A global list must also work after a conversation about one specific employer.
    for previous in ("", "¿Qué hizo en HSBC?"):
        assert [fact.id for fact in retriever.search(question, previous)] == ["career-overview"]


@pytest.mark.parametrize(
    "question",
    [
        "¿Ha trabajado en Banorte?",
        "¿En qué empresas ha trabajado con Rust?",
        "Which companies did he work for using Rust?",
        "¿En qué empresas no ha trabajado?",
        "Which companies has he never worked for?",
        "¿En qué empresas trabaja actualmente?",
        "¿Cuántos años ha trabajado en HSBC?",
    ],
)
def test_employer_qualifiers_do_not_receive_the_generic_company_list(question):
    retriever = Retriever(Profile.load(Path("data/profile.json")))
    assert "career-overview" not in {fact.id for fact in retriever.search(question)}


def test_unsupported_technology_is_not_replaced_by_an_unrelated_employer():
    retriever = Retriever(Profile.load(Path("data/profile.json")))
    assert not retriever.search("Which companies did he work for using Rust?")
    assert not retriever.search("¿En qué empresas ha trabajado con Rust?")
    facts = retriever.search("Which companies did he work for using PHP?")
    assert facts and all("php" in (fact.text_es + fact.text_en).lower() for fact in facts)


def test_correction_sequence_answers_from_profile_instead_of_previous_assistant_rejection(client):
    previous = None
    for question in [
        "ok, donde ha trabajado?",
        "no sabes donde ha trabajado?",
        "cuales son las empresas donde ha trabajado?",
    ]:
        payload = {"input": question}
        if previous:
            payload["previous_response_id"] = previous
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 200
        data = response.json()
        text = data["output"][0]["content"][0]["text"]
        for employer in ["HSBC", "Applabmx", "Industria Social", "COFAA", "ArkusNexus"]:
            assert employer in text
        assert "Fuentes:" not in text and "información documentada suficiente" not in text
        previous = data["id"]
