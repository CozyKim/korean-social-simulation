"""data.sampler 단위 테스트 — pandas 픽스처로 HF 의존성 제거."""

import logging

import pandas as pd
import pytest

from korean_social_simulation.data.sampler import (
    age_band,
    sample_personas,
)


@pytest.fixture
def fake_population():
    """1,000명짜리 합성 인구 — 비례 검증용."""
    rows = []
    for i in range(1000):
        rows.append(
            {
                "uuid": f"u{i:04d}",
                "sex": "남" if i % 2 == 0 else "여",
                "age": 20 + (i % 60),
                "province": ["서울특별시", "경기도", "부산광역시"][i % 3],
                "district": "테스트구",
                "occupation": "학생",
                "education_level": "학사",
                "family_type": "1인가구",
                "housing_type": "아파트",
                "persona": f"테스트 페르소나 {i}",
            }
        )
    return pd.DataFrame(rows)


def test_age_band_buckets():
    assert age_band(19) == "~19"
    assert age_band(20) == "20s"
    assert age_band(29) == "20s"
    assert age_band(30) == "30s"
    assert age_band(70) == "70+"


def test_sample_is_deterministic_for_same_seed(fake_population):
    """같은 (seed, n, filters)는 항상 같은 행을 뽑는다."""
    s1 = sample_personas(fake_population, n=100, seed=42)
    s2 = sample_personas(fake_population, n=100, seed=42)
    assert list(s1["uuid"]) == list(s2["uuid"])


def test_different_seeds_produce_different_samples(fake_population):
    s1 = sample_personas(fake_population, n=100, seed=1)
    s2 = sample_personas(fake_population, n=100, seed=2)
    assert list(s1["uuid"]) != list(s2["uuid"])


def test_filters_restrict_population(fake_population):
    s = sample_personas(fake_population, n=100, seed=42, filters={"province": "서울특별시"})
    assert (s["province"] == "서울특별시").all()


def test_proportional_sampling_preserves_sex_ratio(fake_population):
    """남:여 비율 50:50이 샘플에서도 유지되어야 한다 (±5% 오차)."""
    s = sample_personas(fake_population, n=200, seed=42)
    male_ratio = (s["sex"] == "남").mean()
    assert 0.45 <= male_ratio <= 0.55


def test_min_cell_warning_logged(fake_population, caplog):
    """min_cell_threshold 미만 셀이 있으면 경고 로그가 출력된다."""
    with caplog.at_level(logging.WARNING):
        sample_personas(fake_population, n=50, seed=42, min_cell_threshold=10)
    assert any("strata cell" in r.message for r in caplog.records)


def test_min_cell_threshold_zero_disables_warning(fake_population, caplog):
    with caplog.at_level(logging.WARNING):
        sample_personas(fake_population, n=200, seed=42, min_cell_threshold=0)
    assert not any("strata cell" in r.message for r in caplog.records)


def test_sample_size_is_exact_for_various_n(fake_population):
    """largest-remainder allocation은 정확히 N을 보장한다 (희소 strata에서도)."""
    for n in [50, 100, 200, 500, 999]:
        s = sample_personas(fake_population, n=n, seed=42)
        assert len(s) == n, f"expected {n} rows, got {len(s)}"


def test_sample_n_exceeds_population_raises(fake_population):
    """n > 가용 모집단이면 명확한 ValueError."""
    with pytest.raises(ValueError, match="exceeds"):
        sample_personas(fake_population, n=10_000, seed=42)
