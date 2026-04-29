"""인구비례 stratified 샘플링 — 재현성 + 희소 셀 경고."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

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
        for col, val in filters.items():
            df = df[df[col] == val]
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
