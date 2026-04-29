"""LLM 종합 인사이트 — fake LLM."""

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from korean_social_simulation.report.insights import generate_insights


class FakeChatText(BaseChatModel):
    canned: str

    @property
    def _llm_type(self) -> str:
        return "fake-text"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.canned))]
        )

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)


async def test_generate_insights_returns_string():
    df = pd.DataFrame(
        [
            {
                "stance": "positive",
                "intensity": 4,
                "quote": "좋아요",
                "sex": "남",
                "age": 30,
            }
        ]
    )
    llm = FakeChatText(canned="전체적으로 긍정 우세.")
    text = await generate_insights(df, llm=llm, max_quotes=20)
    assert "긍정" in text
