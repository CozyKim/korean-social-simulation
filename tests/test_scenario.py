"""Scenario 모델 검증."""

import pytest
from pydantic import ValidationError

from korean_social_simulation.scenario import Scenario


def test_scenario_minimum_only_stimulus_required():
    s = Scenario(title="Test", stimulus="새로운 신라면 광고")
    assert s.title == "Test"
    assert s.scenario_type == "other"
    assert s.context is None
    assert s.question is None


def test_scenario_full():
    s = Scenario(
        title="신라면 신제품",
        stimulus="...",
        context="신제품 출시 직전",
        scenario_type="marketing",
        question="구매 의향은?",
    )
    assert s.scenario_type == "marketing"


def test_scenario_invalid_type_rejected():
    with pytest.raises(ValidationError):
        Scenario(title="x", stimulus="x", scenario_type="invalid")


def test_scenario_slug():
    s = Scenario(title="신라면 신제품 광고!!!", stimulus="...")
    assert s.slug() == "신라면-신제품-광고"
