"""data.sampler 단위 테스트 — pandas 픽스처로 HF 의존성 제거."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from korean_social_simulation.data.sampler import (
    _canonicalize_filters,
    age_band,
    cache_key,
    sample_personas,
    sample_personas_cached,
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


def test_cache_key_changes_with_each_dimension():
    base = dict(seed=1, n=100, filters=None, dataset_fingerprint="abc", sampler_version="1")
    assert cache_key(**base) == cache_key(**base)  # 결정적
    assert cache_key(**{**base, "seed": 2}) != cache_key(**base)
    assert cache_key(**{**base, "n": 200}) != cache_key(**base)
    assert cache_key(**{**base, "filters": {"province": "서울특별시"}}) != cache_key(**base)
    assert cache_key(**{**base, "dataset_fingerprint": "xyz"}) != cache_key(**base)
    assert cache_key(**{**base, "sampler_version": "2"}) != cache_key(**base)


def test_cache_hit_returns_same_sample(fake_population, tmp_cache_dir):
    s1 = sample_personas_cached(
        fake_population,
        n=100,
        seed=42,
        dataset_fingerprint="fp1",
        cache_dir=tmp_cache_dir,
    )
    s2 = sample_personas_cached(
        fake_population,
        n=100,
        seed=42,
        dataset_fingerprint="fp1",
        cache_dir=tmp_cache_dir,
    )
    assert list(s1["uuid"]) == list(s2["uuid"])


def test_cache_miss_on_fingerprint_change(fake_population, tmp_cache_dir, caplog):
    sample_personas_cached(
        fake_population,
        n=100,
        seed=42,
        dataset_fingerprint="fp1",
        cache_dir=tmp_cache_dir,
    )
    # 같은 키지만 다른 fingerprint를 메타에 강제 주입했다고 가정 — 새 fingerprint로 다시 호출
    sample_personas_cached(
        fake_population,
        n=100,
        seed=42,
        dataset_fingerprint="fp2",
        cache_dir=tmp_cache_dir,
    )
    # 캐시 파일이 두 개 존재해야 함 (fp1, fp2 각각)
    files = list(Path(tmp_cache_dir / "samples").glob("*.parquet"))
    assert len(files) == 2


def test_filter_accepts_list_isin(fake_population):
    """list 값은 isin 매칭 — 다중 선택."""
    sample = sample_personas(
        fake_population,
        n=200,
        seed=42,
        filters={"province": ["서울특별시", "경기도"]},
    )
    assert set(sample["province"].unique()) <= {"서울특별시", "경기도"}
    assert "부산광역시" not in sample["province"].unique()


def test_filter_accepts_tuple_same_as_list(fake_population):
    """tuple도 list와 동일하게 isin으로 처리."""
    sample = sample_personas(
        fake_population,
        n=100,
        seed=42,
        filters={"province": ("서울특별시", "경기도")},
    )
    assert set(sample["province"].unique()) <= {"서울특별시", "경기도"}


def test_filter_accepts_range_dict_min_max(fake_population):
    """dict {min, max} 는 범위 매칭."""
    sample = sample_personas(
        fake_population,
        n=100,
        seed=42,
        filters={"age": {"min": 30, "max": 39}},
    )
    assert sample["age"].min() >= 30
    assert sample["age"].max() <= 39


def test_filter_accepts_range_dict_min_only(fake_population):
    sample = sample_personas(
        fake_population,
        n=100,
        seed=42,
        filters={"age": {"min": 50}},
    )
    assert sample["age"].min() >= 50


def test_filter_accepts_range_dict_max_only(fake_population):
    sample = sample_personas(
        fake_population,
        n=100,
        seed=42,
        filters={"age": {"max": 39}},
    )
    assert sample["age"].max() <= 39


def test_filter_combines_list_and_range(fake_population):
    """다축 조합 — list + dict 동시 적용."""
    sample = sample_personas(
        fake_population,
        n=80,
        seed=42,
        filters={"sex": ["남"], "age": {"min": 20, "max": 29}},
    )
    assert set(sample["sex"].unique()) == {"남"}
    assert sample["age"].between(20, 29).all()


def test_canonicalize_sorts_list_values():
    raw = {"province": ["서울특별시", "경기도", "부산광역시"]}
    canonical = _canonicalize_filters(raw)
    assert canonical == {"province": ["경기도", "부산광역시", "서울특별시"]}


def test_canonicalize_tuple_becomes_sorted_list():
    raw = {"sex": ("여", "남")}
    canonical = _canonicalize_filters(raw)
    assert canonical == {"sex": ["남", "여"]}


def test_canonicalize_dict_value_sorts_keys():
    raw = {"age": {"max": 39, "min": 20}}
    canonical = _canonicalize_filters(raw)
    # dict 키 순서는 json.dumps(sort_keys=True) 가 처리하지만,
    # 명시적으로도 보장되어야 추후 직접 비교 시 안정.
    assert list(canonical["age"].keys()) == ["max", "min"]


def test_canonicalize_scalar_pass_through():
    raw = {"sex": "남"}
    canonical = _canonicalize_filters(raw)
    assert canonical == {"sex": "남"}


def test_canonicalize_none_returns_empty():
    assert _canonicalize_filters(None) == {}
    assert _canonicalize_filters({}) == {}


def test_canonicalize_unorderable_list_does_not_raise():
    """None / 혼합 타입이 list에 섞여도 정렬은 결정적이고 예외 없이 처리."""
    # None과 string 혼합: native sort는 TypeError를 던지지만 JSON-key sort는 OK.
    raw = {"province": ["서울특별시", None, "경기도"]}
    canonical = _canonicalize_filters(raw)
    # 정렬은 결정적이어야 하므로 같은 입력은 같은 출력.
    again = _canonicalize_filters({"province": [None, "경기도", "서울특별시"]})
    assert canonical == again
    # 원소 집합은 보존.
    assert set(map(str, canonical["province"])) == {"서울특별시", "None", "경기도"}


def test_cache_key_normalizes_list_order():
    """순서만 다른 list는 같은 cache key를 만든다."""
    k1 = cache_key(
        seed=42,
        n=100,
        filters={"province": ["서울특별시", "경기도"]},
        dataset_fingerprint="abc123def456",
    )
    k2 = cache_key(
        seed=42,
        n=100,
        filters={"province": ["경기도", "서울특별시"]},
        dataset_fingerprint="abc123def456",
    )
    assert k1 == k2


def test_cache_key_distinct_filters_distinct_keys():
    """다른 의미의 filters는 다른 키."""
    k1 = cache_key(
        seed=42,
        n=100,
        filters={"province": ["서울특별시"]},
        dataset_fingerprint="abc123def456",
    )
    k2 = cache_key(
        seed=42,
        n=100,
        filters={"province": ["경기도"]},
        dataset_fingerprint="abc123def456",
    )
    assert k1 != k2


def test_cache_hit_rejects_mismatched_filters_metadata(fake_population, tmp_cache_dir, caplog):
    """parquet 파일은 그대로지만 메타의 filters가 다르면 캐시 무효."""
    import json as _json

    import pyarrow.parquet as pq

    # 1) 정상 캐시 생성
    sample_personas_cached(
        fake_population,
        n=50,
        seed=42,
        dataset_fingerprint="fp_test_1234",
        filters={"province": ["서울특별시"]},
        cache_dir=tmp_cache_dir,
    )

    # 2) 같은 cache key 호출인데 filters 본문만 다른 경우를 재현하기 위해
    #    디스크의 메타를 손상시킨다 (해시 충돌 시뮬레이션).
    cache_files = list((tmp_cache_dir / "samples").glob("*.parquet"))
    assert len(cache_files) == 1
    path = cache_files[0]
    tbl = pq.read_table(path)
    bad_meta = _json.loads(tbl.schema.metadata[b"kss_meta"])
    bad_meta["filters"] = {"province": ["부산광역시"]}  # 변조
    new_meta = {b"kss_meta": _json.dumps(bad_meta, ensure_ascii=False).encode()}
    pq.write_table(tbl.replace_schema_metadata(new_meta), path)

    # 3) 같은 인자로 다시 호출하면 메타 mismatch 감지 → 재생성.
    caplog.set_level(logging.WARNING)
    result = sample_personas_cached(
        fake_population,
        n=50,
        seed=42,
        dataset_fingerprint="fp_test_1234",
        filters={"province": ["서울특별시"]},
        cache_dir=tmp_cache_dir,
    )
    # 결과는 실제 필터 적용 후 결과여야 함 (서울만)
    assert set(result["province"].unique()) == {"서울특별시"}
    assert any("metadata mismatch" in rec.message for rec in caplog.records)


def test_cache_hit_filters_canonical_form_persists(fake_population, tmp_cache_dir):
    """디스크에 저장되는 filters는 항상 canonical 형태(list 정렬됨)."""
    import json as _json

    import pyarrow.parquet as pq

    sample_personas_cached(
        fake_population,
        n=30,
        seed=7,
        dataset_fingerprint="fp_can_test",
        filters={"province": ["서울특별시", "경기도", "부산광역시"]},
        cache_dir=tmp_cache_dir,
    )
    path = next((tmp_cache_dir / "samples").glob("*.parquet"))
    meta = _json.loads(pq.read_table(path).schema.metadata[b"kss_meta"])
    # 정렬 키는 JSON 직렬화 (`json.dumps(x, ensure_ascii=False)`) — 한글 문자열의
    # 사전식 순서대로 정렬됨. ㄱ < ㅂ < ㅅ.
    assert meta["filters"] == {"province": ["경기도", "부산광역시", "서울특별시"]}


def test_cache_hit_same_filters_different_order_reuses_cache(fake_population, tmp_cache_dir):
    """순서만 다른 list 입력은 같은 cache 파일을 재사용."""
    sample_personas_cached(
        fake_population,
        n=40,
        seed=11,
        dataset_fingerprint="fp_reuse_test",
        filters={"province": ["서울특별시", "경기도"]},
        cache_dir=tmp_cache_dir,
    )
    files_before = list((tmp_cache_dir / "samples").glob("*.parquet"))

    # 순서만 뒤집어서 호출
    sample_personas_cached(
        fake_population,
        n=40,
        seed=11,
        dataset_fingerprint="fp_reuse_test",
        filters={"province": ["경기도", "서울특별시"]},
        cache_dir=tmp_cache_dir,
    )
    files_after = list((tmp_cache_dir / "samples").glob("*.parquet"))
    assert len(files_after) == 1, "동일 의미 호출이 새 캐시 파일을 만들지 말아야 함"
    assert files_before[0] == files_after[0]
