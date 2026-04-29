"""CoreReaction + 동적 모델 빌더 검증."""

import pytest
from pydantic import ValidationError

from korean_social_simulation.reaction import (
    DEFAULT_ACTION_INTENT_CHOICES,
    CoreReaction,
    build_reaction_model,
)


def test_core_reaction_validates_intensity_range():
    with pytest.raises(ValidationError):
        CoreReaction(
            stance="positive",
            intensity=6,  # > 5
            action_intent="purchase",
            key_drivers=["a"],
            quote="q",
        )


def test_default_action_intent_choices_contains_expected_values():
    for value in ["purchase", "advocate", "share", "ignore", "reject"]:
        assert value in DEFAULT_ACTION_INTENT_CHOICES


def test_build_reaction_model_with_default_choices():
    Model = build_reaction_model()
    inst = Model(
        stance="positive",
        intensity=4,
        action_intent="purchase",
        key_drivers=["좋은 가격"],
        quote="살 만하네요",
    )
    assert inst.action_intent == "purchase"


def test_build_reaction_model_with_custom_choices():
    Model = build_reaction_model(action_intent_choices=["구매", "관망", "거부"])
    Model(
        stance="positive",
        intensity=4,
        action_intent="구매",
        key_drivers=["가격"],
        quote="...",
    )
    with pytest.raises(ValidationError):
        Model(
            stance="positive",
            intensity=4,
            action_intent="purchase",  # 새 enum에 없음
            key_drivers=["가격"],
            quote="...",
        )


def test_build_reaction_model_with_extra_fields():
    Model = build_reaction_model(
        extra_fields={
            "purchase_likelihood": (int, "0~100, 구매 가능성"),
            "price_sensitivity": (int, "0~100, 가격 민감도"),
        }
    )
    inst = Model(
        stance="positive",
        intensity=3,
        action_intent="purchase",
        key_drivers=["맛"],
        quote="좋네요",
        purchase_likelihood=70,
        price_sensitivity=40,
    )
    assert inst.purchase_likelihood == 70
    assert inst.price_sensitivity == 40
    # extra 필드 미제공 시 검증 실패
    with pytest.raises(ValidationError):
        Model(
            stance="positive",
            intensity=3,
            action_intent="purchase",
            key_drivers=["맛"],
            quote="좋네요",
        )
