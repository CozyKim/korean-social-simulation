"""반응 데이터 모델 — 코어 + 동적 확장."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

DEFAULT_ACTION_INTENT_CHOICES: list[str] = [
    "purchase",
    "advocate",
    "share",
    "discuss",
    "seek_more_info",
    "ignore",
    "avoid",
    "reject",
]


class CoreReaction(BaseModel):
    """모든 시뮬에 공통인 코어 반응 스키마."""

    stance: Literal["positive", "negative", "neutral", "mixed"]
    intensity: int = Field(ge=1, le=5, description="반응 강도 1(약함)~5(강함)")
    action_intent: str = Field(description="페르소나의 행동 의도 (enum 동적)")
    key_drivers: list[str] = Field(min_length=1, description="핵심 이유 1~3개")
    concerns: list[str] = Field(default_factory=list, description="우려/거부 포인트")
    quote: str = Field(min_length=1, description="페르소나가 할 법한 1~2 문장")


def build_reaction_model(
    action_intent_choices: list[str] | None = None,
    extra_fields: dict[str, tuple[type, str]] | None = None,
) -> type[BaseModel]:
    """런타임에 ReactionModel을 생성한다.

    Args:
        action_intent_choices: 디폴트 enum을 오버라이드 (예 한국어로 변경).
        extra_fields: 추가 필드 dict — `{"name": (type, "description"), ...}`.

    Returns:
        Pydantic BaseModel 서브클래스. LangChain `with_structured_output`에 그대로 전달 가능.
    """
    choices = action_intent_choices or DEFAULT_ACTION_INTENT_CHOICES
    intent_type = Literal[tuple(choices)]  # type: ignore[valid-type]

    fields: dict[str, tuple[type, object]] = {
        "stance": (Literal["positive", "negative", "neutral", "mixed"], ...),
        "intensity": (int, Field(ge=1, le=5)),
        "action_intent": (intent_type, ...),
        "key_drivers": (list[str], Field(min_length=1)),
        "concerns": (list[str], Field(default_factory=list)),
        "quote": (str, Field(min_length=1)),
    }

    for name, (typ, desc) in (extra_fields or {}).items():
        fields[name] = (typ, Field(..., description=desc))

    return create_model("ReactionModel", **fields)
