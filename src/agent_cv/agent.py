from dataclasses import dataclass

from .model import OllamaSelector
from .policy import MESSAGES, language_of, precheck
from .profile import Profile
from .retrieval import Retriever


@dataclass
class Answer:
    text: str
    decision: str
    fact_ids: list[str]
    input_tokens: int = 0
    output_tokens: int = 0


class Agent:
    def __init__(self, profile: Profile, selector: OllamaSelector):
        self.profile = profile
        self.selector = selector
        self.retriever = Retriever(profile)

    async def answer(self, question: str, previous_user: str = "") -> Answer:
        language = language_of(question, previous_user)
        canned = MESSAGES[language]
        decision = precheck(question)
        if decision:
            return Answer(canned[decision], decision, [])
        facts = self.retriever.search(question, previous_user)
        if not facts:
            return Answer(canned["unknown"], "unknown", [])
        result = await self.selector.select(question, previous_user, facts)
        selection = result.selection
        if selection.decision != "answer":
            return Answer(
                canned[selection.decision],
                selection.decision,
                [],
                result.input_tokens,
                result.output_tokens,
            )
        # No model-generated prose, IDs, links or source labels ever reach the public answer.
        by_id = {f.id: f for f in facts}
        selected = [by_id[i] for i in dict.fromkeys(selection.fact_ids)]
        body = "\n\n".join(f.text(language) for f in selected)
        return Answer(
            body,
            "answer",
            [f.id for f in selected],
            result.input_tokens,
            result.output_tokens,
        )
