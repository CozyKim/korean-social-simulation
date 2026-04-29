"""LLM이 N건 반응을 요약해 자연어 인사이트를 작성한다."""

from __future__ import annotations

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

_SYSTEM = """\
당신은 한국 사회 시뮬레이션 결과를 종합 분석하는 리서처입니다.
주어진 반응 통계와 대표 인용을 바탕으로:
1. 전체 반응 패턴 (어떤 방향성·강도로)
2. 두드러진 세그먼트 차이가 있다면 그 의미
3. 시나리오 설계자에게 줄 1~2개의 실행 가능한 제언
을 한국어로 600~1000자 분량의 단락 글로 작성하세요. 표·번호 매김보단 자연스러운 단락을 선호합니다.
"""


async def generate_insights(
    df: pd.DataFrame,
    *,
    llm: BaseChatModel,
    max_quotes: int = 20,
) -> str:
    """반응 DataFrame을 받아 자연어 인사이트 문자열을 반환."""
    summary = _summarize_for_llm(df, max_quotes=max_quotes)
    msg = await llm.ainvoke(
        [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=summary),
        ]
    )
    return msg.content if isinstance(msg.content, str) else str(msg.content)


def _summarize_for_llm(df: pd.DataFrame, *, max_quotes: int) -> str:
    parts: list[str] = []
    parts.append(f"총 {len(df)}명의 반응:")
    parts.append("[stance 분포]")
    parts.append(df["stance"].value_counts(normalize=True).round(3).to_string())
    parts.append("[평균 intensity] " + f"{df['intensity'].mean():.2f}")
    if "action_intent" in df:
        parts.append("[action_intent top 5]")
        parts.append(df["action_intent"].value_counts().head(5).to_string())
    parts.append("[대표 인용]")
    quotes = df.dropna(subset=["quote"]).head(max_quotes)
    for _, row in quotes.iterrows():
        parts.append(
            f"- ({row.get('sex')},{row.get('age')},{row.get('stance')}) "
            f"{row['quote']}"
        )
    return "\n".join(parts)
