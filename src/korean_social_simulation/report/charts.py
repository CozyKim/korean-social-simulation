"""matplotlib 기반 리포트 차트들 — 파일에 PNG로 저장."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from korean_social_simulation.data.sampler import age_band  # noqa: E402

_STANCE_ORDER = ["positive", "neutral", "mixed", "negative"]
_STANCE_COLORS = {
    "positive": "#3CB371",
    "neutral": "#A9A9A9",
    "mixed": "#FFA500",
    "negative": "#CD5C5C",
}


def stance_donut(df: pd.DataFrame, out_path: Path) -> None:
    """stance 분포를 도넛 차트로 그려 ``out_path`` 에 저장."""
    counts = df["stance"].value_counts().reindex(_STANCE_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(
        counts.values,
        labels=counts.index,
        colors=[_STANCE_COLORS[s] for s in counts.index],
        autopct="%1.1f%%",
        wedgeprops={"width": 0.4},
        startangle=90,
    )
    ax.set_title("Stance distribution")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def intensity_hist(df: pd.DataFrame, out_path: Path) -> None:
    """intensity 1~5 히스토그램을 그려 저장."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(
        df["intensity"], bins=range(1, 7), align="left", rwidth=0.8, color="#4682B4"
    )
    ax.set_xticks(range(1, 6))
    ax.set_xlabel("Intensity (1=weak, 5=strong)")
    ax.set_ylabel("count")
    ax.set_title("Reaction intensity")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def action_intent_bar(df: pd.DataFrame, out_path: Path) -> None:
    """action_intent 빈도 가로 막대그래프."""
    counts = df["action_intent"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(counts.index[::-1], counts.values[::-1], color="#6A5ACD")
    ax.set_xlabel("count")
    ax.set_title("Action intent distribution")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def segment_heatmap(
    df: pd.DataFrame,
    *,
    segment: str,
    out_path: Path,
    min_cell: int = 5,
) -> None:
    """segment(sex/age_band/province) × stance 비율 히트맵.

    각 (segment, stance) **셀**의 카운트가 ``min_cell`` 미만이면 그 셀만 회색으로
    마스킹한다 (행 전체가 아니라). 행 합계 ``n`` 은 y축 라벨에 함께 표기한다.
    """
    work = df.copy()
    if segment == "age_band":
        work["age_band"] = work["age"].map(age_band)
    counts = (
        work.groupby([segment, "stance"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=_STANCE_ORDER, fill_value=0)
    )
    totals = counts.sum(axis=1)
    ratios = counts.div(totals, axis=0).fillna(0)
    cell_counts = counts.values
    masked = np.where(cell_counts < min_cell, np.nan, ratios.values)

    fig, ax = plt.subplots(figsize=(6, max(2.5, 0.4 * len(ratios))))
    im = ax.imshow(masked, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(_STANCE_ORDER)))
    ax.set_xticklabels(_STANCE_ORDER)
    ax.set_yticks(range(len(ratios.index)))
    ax.set_yticklabels([f"{idx} (n={int(totals[idx])})" for idx in ratios.index])
    for i in range(cell_counts.shape[0]):
        for j in range(cell_counts.shape[1]):
            v = ratios.values[i, j]
            cell_n = int(cell_counts[i, j])
            color = "lightgray" if cell_n < min_cell else "black"
            ax.text(
                j, i, f"{v:.0%}", ha="center", va="center", color=color, fontsize=8
            )
    ax.set_title(f"{segment} × stance")
    fig.colorbar(im, ax=ax, fraction=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def count_sparse_strata(df: pd.DataFrame, *, threshold: int) -> int:
    """샘플러와 동일한 ``sex × age_band × province`` strata 기준 희소 셀 개수.

    리포트와 대시보드의 sparse 경고가 sampler와 일치하도록 사용한다.
    ``threshold <= 0`` 이면 0을 반환한다.
    """
    if threshold <= 0:
        return 0
    work = df.copy()
    work["_band"] = work["age"].map(age_band)
    cells = work.groupby(["sex", "_band", "province"]).size()
    return int((cells < threshold).sum())
