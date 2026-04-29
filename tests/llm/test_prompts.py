"""프롬프트 블록 포맷팅 검증."""

from korean_social_simulation.llm.prompts import (
    SIMULATION_INSTRUCTIONS,
    format_persona_block,
    format_scenario_block,
)
from korean_social_simulation.scenario import Scenario


def test_simulation_instructions_mentions_korean_and_json():
    assert "한국" in SIMULATION_INSTRUCTIONS
    assert "JSON" in SIMULATION_INSTRUCTIONS


def test_format_scenario_block_includes_all_fields():
    s = Scenario(
        title="t",
        stimulus="자극",
        context="배경",
        scenario_type="marketing",
        question="질문?",
    )
    block = format_scenario_block(s)
    assert "자극" in block
    assert "배경" in block
    assert "marketing" in block
    assert "질문?" in block


def test_format_scenario_block_omits_optional_when_missing():
    s = Scenario(title="t", stimulus="자극")
    block = format_scenario_block(s)
    assert "자극" in block
    assert "배경" not in block.lower()


def test_format_persona_block_uses_all_columns():
    persona = {
        "uuid": "u1",
        "sex": "남",
        "age": 34,
        "province": "서울특별시",
        "district": "강남구",
        "occupation": "엔지니어",
        "education_level": "학사",
        "bachelors_field": "컴퓨터공학",
        "marital_status": "기혼",
        "military_status": "필",
        "family_type": "부부+자녀",
        "housing_type": "아파트",
        "country": "대한민국",
        "persona": "통합 페르소나 텍스트",
        "professional_persona": "직업 페르소나",
        "sports_persona": "스포츠 페르소나",
        "arts_persona": "예술 페르소나",
        "travel_persona": "여행 페르소나",
        "culinary_persona": "요리 페르소나",
        "family_persona": "가족 페르소나",
        "cultural_background": "문화",
        "skills_and_expertise": "스킬",
        "skills_and_expertise_list": "[]",
        "hobbies_and_interests": "취미",
        "hobbies_and_interests_list": "[]",
        "career_goals_and_ambitions": "목표",
    }
    block = format_persona_block(persona)
    assert "남" in block and "34" in block and "강남구" in block
    assert "통합 페르소나" in block
    assert "직업 페르소나" in block
    assert "취미" in block
