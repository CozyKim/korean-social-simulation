"""인구비례 stratified 샘플링 — 재현성 + 희소 셀 경고."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from korean_social_simulation._version import SAMPLER_VERSION

logger = logging.getLogger(__name__)

_AGE_BANDS: list[tuple[int, str]] = [
    (19, "~19"),
    (29, "20s"),
    (39, "30s"),
    (49, "40s"),
    (59, "50s"),
    (69, "60s"),
    (200, "70+"),
]


def age_band(age: int) -> str:
    """나이를 고정된 7개 연령대 라벨로 매핑."""
    for upper, label in _AGE_BANDS:
        if age <= upper:
            return label
    return "70+"


def _strata_key(df: pd.DataFrame) -> pd.Series:
    bands = df["age"].map(age_band)
    return df["sex"].astype(str) + "|" + bands + "|" + df["province"].astype(str)


def sample_personas(
    population: pd.DataFrame,
    *,
    n: int,
    seed: int,
    filters: dict[str, Any] | None = None,
    min_cell_threshold: int = 5,
) -> pd.DataFrame:
    """모집단에서 인구비례 stratified 샘플 N명을 결정적으로 추출한다.

    largest-remainder allocation으로 정확히 N개를 보장한다. 모든 stratum의
    가용 행 수를 cap하고 결손분은 큰 비례부터 채운다.

    Args:
        population: 페르소나 모집단 (`uuid`, `sex`, `age`, `province`, ... 컬럼).
        n: 샘플 크기.
        seed: 재현성 시드.
        filters: 컬럼별 필터 dict — 예 `{"province": "서울특별시"}`.
        min_cell_threshold: 셀 카운트가 이 값 미만이면 경고 로그 출력. 0이면 비활성.

    Returns:
        샘플링된 페르소나 DataFrame (인덱스 reset 됨, len == n).

    Raises:
        ValueError: 필터 후 모집단이 비어있거나 n이 가용 행 수를 초과할 때.
    """
    df = population
    if filters:
        df = _apply_filters(df, filters)
    df = df.reset_index(drop=True)

    if len(df) == 0:
        raise ValueError(f"Filtered population is empty: filters={filters}")
    if n > len(df):
        raise ValueError(f"Requested n={n} exceeds filtered population size {len(df)}")

    rng = np.random.default_rng(seed)
    strata = _strata_key(df)
    quotas = _allocate_quotas(strata, df, n)

    sampled_idx: list[int] = []
    for stratum_label, quota in quotas.items():
        if quota <= 0:
            continue
        pool_idx = df.index[strata == stratum_label].to_numpy()
        chosen = rng.choice(pool_idx, size=quota, replace=False)
        sampled_idx.extend(chosen.tolist())

    sample = df.loc[sampled_idx].reset_index(drop=True)
    assert len(sample) == n, f"sample size mismatch: {len(sample)} != {n}"
    if min_cell_threshold > 0:
        _warn_sparse_cells(sample, min_cell_threshold)
    return sample


def _allocate_quotas(strata: pd.Series, df: pd.DataFrame, n: int) -> pd.Series:
    """largest-remainder allocation: 각 stratum에 정수 quota를 분배해 합 == n.

    각 stratum의 가용 행 수(pool size)를 cap으로 두고, 결손분은 비례
    잔여(remainder)가 큰 stratum부터 +1씩 redistribute.
    """
    pool_sizes = strata.value_counts()  # stratum_label -> 가용 행 수
    if pool_sizes.sum() < n:
        raise ValueError(f"Filtered population size {pool_sizes.sum()} < n={n}")

    proportions = pool_sizes / pool_sizes.sum()
    raw = proportions * n
    floor = np.floor(raw).astype(int)
    quotas = pd.Series(
        np.minimum(floor.values, pool_sizes.values),
        index=pool_sizes.index,
    )

    remainders = (raw - floor).sort_values(ascending=False)
    deficit = n - int(quotas.sum())
    for stratum_label in remainders.index:
        if deficit <= 0:
            break
        if quotas[stratum_label] < pool_sizes[stratum_label]:
            quotas[stratum_label] += 1
            deficit -= 1

    if deficit != 0:
        # 결손분이 남았다 = 가용량이 부족 (이미 위에서 raise했어야 함)
        raise ValueError(f"Could not allocate exactly n={n} samples (deficit={deficit})")

    return quotas


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """필터 dict의 값 타입에 따라 컬럼별 조건을 적용.

    값 타입별 의미:
        - list/tuple : isin 매칭 (다중 선택)
        - dict with min/max : 범위 매칭 (수치형)
        - 그 외 (scalar) : 등호 매칭 (기존 동작 — 하위호환)

    Args:
        df: 원본 DataFrame.
        filters: 컬럼명 → 필터 값 매핑.

    Returns:
        필터를 적용한 DataFrame view (인덱스 reset 안 함).
    """
    for col, val in filters.items():
        if isinstance(val, (list, tuple)):
            df = df[df[col].isin(val)]
        elif isinstance(val, dict) and ("min" in val or "max" in val):
            if "min" in val:
                df = df[df[col] >= val["min"]]
            if "max" in val:
                df = df[df[col] <= val["max"]]
        else:
            df = df[df[col] == val]
    return df


def _warn_sparse_cells(sample: pd.DataFrame, threshold: int) -> None:
    """샘플 내 (sex, age_band, province) cell 카운트를 검사하고 경고한다."""
    bands = sample["age"].map(age_band)
    cells = sample.assign(_band=bands).groupby(["sex", "_band", "province"], dropna=False).size()
    sparse = cells[cells < threshold]
    if not sparse.empty:
        sample_strs = ", ".join(f"{idx}=({n})" for idx, n in sparse.head(5).items())
        logger.warning(
            "%d strata cell(s) below min_cell_threshold=%d (e.g., %s) — segment generalization may be unreliable",
            len(sparse),
            threshold,
            sample_strs,
        )


def _default_cache_dir() -> Path:
    """기본 캐시 디렉터리 — `KSS_CACHE_DIR` 환경변수 우선, 없으면 `~/.cache/korean_social_simulation`."""
    env = os.environ.get("KSS_CACHE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "korean_social_simulation"


def cache_key(
    *,
    seed: int,
    n: int,
    filters: dict[str, Any] | None,
    dataset_fingerprint: str,
    sampler_version: str = SAMPLER_VERSION,
) -> str:
    """결정적 캐시 키 — 다섯 축이 모두 같아야 같은 키.

    Args:
        seed: 샘플링 시드.
        n: 샘플 크기.
        filters: 컬럼별 필터 dict (None이면 빈 dict로 정규화).
        dataset_fingerprint: 모집단 데이터 fingerprint (앞 12자만 키에 사용).
        sampler_version: 샘플러 알고리즘 버전 — bump 시 캐시 일괄 무효화.

    Returns:
        `{seed}-{n}-{filters_hash}-{fingerprint12}-{version}` 형태의 결정적 키.
    """
    filters_str = json.dumps(filters or {}, sort_keys=True, ensure_ascii=False)
    filters_hash = hashlib.sha1(filters_str.encode("utf-8")).hexdigest()[:8]
    return f"{seed}-{n}-{filters_hash}-{dataset_fingerprint[:12]}-{sampler_version}"


def sample_personas_cached(
    population: pd.DataFrame,
    *,
    n: int,
    seed: int,
    dataset_fingerprint: str,
    filters: dict[str, Any] | None = None,
    min_cell_threshold: int = 5,
    cache_dir: Path | None = None,
    sampler_version: str = SAMPLER_VERSION,
) -> pd.DataFrame:
    """`sample_personas`의 캐시 wrapper — fingerprint 불일치 시 재생성.

    parquet 파일에 schema metadata로 (seed, n, filters, fingerprint, version)을
    함께 저장한다. 캐시 hit 시 메타가 현재 파라미터와 모두 일치할 때만 반환.

    Args:
        population: 페르소나 모집단 DataFrame.
        n: 샘플 크기.
        seed: 재현성 시드.
        dataset_fingerprint: 모집단 fingerprint — 변경 시 캐시 재생성.
        filters: 컬럼별 필터 dict.
        min_cell_threshold: 희소 셀 경고 임계치.
        cache_dir: 캐시 루트 디렉터리 (None이면 `_default_cache_dir()`).
        sampler_version: 샘플러 알고리즘 버전.

    Returns:
        샘플링된 페르소나 DataFrame (len == n).
    """
    cache_root = Path(cache_dir or _default_cache_dir()) / "samples"
    cache_root.mkdir(parents=True, exist_ok=True)
    key = cache_key(
        seed=seed,
        n=n,
        filters=filters,
        dataset_fingerprint=dataset_fingerprint,
        sampler_version=sampler_version,
    )
    path = cache_root / f"{key}.parquet"

    if path.exists():
        try:
            tbl = pq.read_table(path)
            meta = json.loads((tbl.schema.metadata or {}).get(b"kss_meta", b"{}"))
            if meta.get("dataset_fingerprint") == dataset_fingerprint and meta.get("sampler_version") == sampler_version and meta.get("seed") == seed and meta.get("n") == n:
                return tbl.to_pandas()
            logger.warning("Sample cache rejected (metadata mismatch): %s", path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sample cache unreadable, regenerating: %s", exc)

    sample = sample_personas(
        population,
        n=n,
        seed=seed,
        filters=filters,
        min_cell_threshold=min_cell_threshold,
    )
    table = pa.Table.from_pandas(sample, preserve_index=False)
    meta = {
        "seed": seed,
        "n": n,
        "filters": filters or {},
        "dataset_fingerprint": dataset_fingerprint,
        "sampler_version": sampler_version,
    }
    table = table.replace_schema_metadata(
        {
            b"kss_meta": json.dumps(meta, ensure_ascii=False).encode("utf-8"),
        }
    )
    pq.write_table(table, path)
    return sample
