"""페르소나 row → 프론트엔드 avatar 자산 lookup 키 매핑.

데이터셋의 ``sex`` 는 한국어(`남`/`여`)이고, 프론트엔드 정적 자산은 영문 prefix
(`male_*` / `female_*`) 로 명명된다. 이 모듈은 두 표기를 잇는 단일 진실원
(single source of truth) 이다.
"""

from __future__ import annotations

from typing import Any

from korean_social_simulation.data.sampler import age_band

# 데이터셋이 쓰는 한국어 sex 라벨 → 자산 prefix 매핑.
# 알 수 없는 값(빈 문자열, 'X' 등) 은 None 을 반환해 클라이언트가 fallback 처리.
_SEX_TO_CANONICAL: dict[str, str] = {
    "남": "male",
    "여": "female",
}


def avatar_key_from_row(row: dict[str, Any]) -> str | None:
    """페르소나 row 에서 ``{sex}_{age_band}_{province}`` canonical 키를 만든다.

    Args:
        row: 페르소나 dict — ``sex``, ``age``, ``province`` 키 포함.

    Returns:
        canonical 자산 키 문자열, 또는 row 가 매핑 불가능한 경우 ``None``.

    Examples:
        >>> avatar_key_from_row({"sex": "남", "age": 28, "province": "서울특별시"})
        'male_20s_서울특별시'
        >>> avatar_key_from_row({"sex": "여", "age": 35, "province": "경기도"})
        'female_30s_경기도'
        >>> avatar_key_from_row({"sex": "X", "age": 28, "province": "서울특별시"}) is None
        True
    """
    sex = row.get("sex")
    age = row.get("age")
    province = row.get("province")
    if not (isinstance(sex, str) and isinstance(age, (int, float)) and isinstance(province, str)):
        return None
    canonical_sex = _SEX_TO_CANONICAL.get(sex)
    if canonical_sex is None:
        return None
    return f"{canonical_sex}_{age_band(int(age))}_{province}"
