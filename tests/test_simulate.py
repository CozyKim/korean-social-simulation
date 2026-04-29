"""simulate_one 단위 테스트 — fake LLM."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from korean_social_simulation.reaction import build_reaction_model
from korean_social_simulation.scenario import Scenario
from korean_social_simulation.simulate import simulate_one


class FakeChat(BaseChatModel):
    """미리 정해둔 dict를 그대로 ReactionModel로 반환하는 가짜 LLM."""

    canned: dict[str, Any]

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        text = "ignored"  # structured 경로에서만 쓰임
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def with_structured_output(self, schema, **kwargs):  # type: ignore[override]
        canned = self.canned

        class _Bound:
            async def ainvoke(self, _messages):
                return schema(**canned)

        return _Bound()


async def test_simulate_one_returns_validated_reaction():
    canned = {
        "stance": "positive",
        "intensity": 4,
        "action_intent": "purchase",
        "key_drivers": ["맛이 좋아 보임"],
        "concerns": [],
        "quote": "한 번 사 먹어볼래요",
    }
    llm = FakeChat(canned=canned)
    Reaction = build_reaction_model()
    persona = {
        "uuid": "u1",
        "sex": "남",
        "age": 34,
        "province": "서울",
        "district": "강남",
        "occupation": "개발자",
        "education_level": "학사",
        "bachelors_field": "CS",
        "marital_status": "미혼",
        "military_status": "필",
        "family_type": "1인",
        "housing_type": "아파트",
        "country": "대한민국",
        "persona": "p",
    }
    scenario = Scenario(title="t", stimulus="새 라면 광고")

    result = await simulate_one(persona, scenario, llm, Reaction)

    assert result["uuid"] == "u1"
    assert result["stance"] == "positive"
    assert result["intensity"] == 4
    assert result["error"] is None
