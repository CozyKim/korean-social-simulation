"""LLM 프롬프트 블록과 시스템 지침."""

from __future__ import annotations

from collections.abc import Mapping

from korean_social_simulation.scenario import Scenario

SIMULATION_INSTRUCTIONS = """\
당신은 한국 사회의 다양한 인구통계와 가치관을 가진 가상 페르소나의 입장에서 시나리오에 반응하는 AI입니다.

규칙:
1. 응답은 반드시 정의된 JSON 스키마에 맞춰 작성합니다.
2. 페르소나의 인구통계(성별, 연령, 지역, 직업, 가족 구성)와 페르소나 텍스트의 가치관·취향을 모두 반영합니다.
3. 평균적·중립적인 답변을 피하고 그 페르소나만의 입장을 분명히 드러냅니다.
4. `quote` 필드는 그 사람이 친구나 동료에게 실제로 할 법한 한국어 문장으로 작성합니다 (1~2문장).
5. `key_drivers`와 `concerns`는 한국어로 짧고 구체적으로 (각 6~20자).
6. 모르는 내용을 지어내지 말고, 페르소나가 알 만한 범위 안에서 반응합니다.
"""


def format_scenario_block(s: Scenario) -> str:
    """시나리오를 LLM 입력용 한국어 블록으로 변환.

    Args:
        s: 직렬화할 시나리오.

    Returns:
        제목·배경·자극·평가 포인트가 정리된 멀티라인 문자열.
    """
    parts: list[str] = [f"[시나리오] {s.title} (type={s.scenario_type})"]
    if s.context:
        parts.append(f"[배경]\n{s.context}")
    parts.append(f"[페르소나가 노출되는 내용]\n{s.stimulus}")
    if s.question:
        parts.append(f"[평가 포인트] {s.question}")
    return "\n\n".join(parts)


_PERSONA_TEXT_FIELDS: list[tuple[str, str]] = [
    ("persona", "[종합 페르소나]"),
    ("professional_persona", "[직업 페르소나]"),
    ("sports_persona", "[스포츠 페르소나]"),
    ("arts_persona", "[예술 페르소나]"),
    ("travel_persona", "[여행 페르소나]"),
    ("culinary_persona", "[요리 페르소나]"),
    ("family_persona", "[가족 페르소나]"),
]


def format_persona_block(persona: Mapping[str, object]) -> str:
    """1인 페르소나의 26개 컬럼을 LLM 입력용 한국어 블록으로 변환.

    Args:
        persona: 페르소나 데이터(컬럼명 → 값) 매핑.

    Returns:
        인구통계, 페르소나 텍스트, 추가 정보가 정리된 멀티라인 문자열.
    """
    demo_fields = [
        ("성별", persona.get("sex")),
        ("나이", persona.get("age")),
        ("지역", f"{persona.get('province')} {persona.get('district')}"),
        ("직업", persona.get("occupation")),
        ("학력", f"{persona.get('education_level')} ({persona.get('bachelors_field')})"),
        ("결혼", persona.get("marital_status")),
        ("군복무", persona.get("military_status")),
        ("가족", persona.get("family_type")),
        ("주거", persona.get("housing_type")),
        ("국적", persona.get("country")),
    ]
    demo_line = ", ".join(f"{k}: {v}" for k, v in demo_fields if v is not None)

    parts: list[str] = [f"[인구통계]\n{demo_line}"]
    for key, label in _PERSONA_TEXT_FIELDS:
        value = persona.get(key)
        if value:
            parts.append(f"{label}\n{value}")

    extras = [
        ("문화적 배경", persona.get("cultural_background")),
        ("스킬·전문성", persona.get("skills_and_expertise")),
        ("취미·관심사", persona.get("hobbies_and_interests")),
        ("진로 목표", persona.get("career_goals_and_ambitions")),
    ]
    extras_lines = [f"- {k}: {v}" for k, v in extras if v]
    if extras_lines:
        parts.append("[추가 정보]\n" + "\n".join(extras_lines))

    return "\n\n".join(parts)
