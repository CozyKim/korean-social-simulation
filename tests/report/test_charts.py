"""차트 생성 — 파일이 만들어지면 OK (이미지 내용은 비교 안 함)."""

import pandas as pd
import pytest

from korean_social_simulation.report.charts import (
    action_intent_bar,
    count_sparse_strata,
    intensity_hist,
    segment_heatmap,
    stance_donut,
)


@pytest.fixture
def df():
    return pd.DataFrame(
        [
            {
                "sex": "남",
                "age": 30,
                "province": "서울특별시",
                "stance": "positive",
                "intensity": 4,
                "action_intent": "purchase",
            },
            {
                "sex": "여",
                "age": 25,
                "province": "경기도",
                "stance": "negative",
                "intensity": 2,
                "action_intent": "reject",
            },
            {
                "sex": "남",
                "age": 50,
                "province": "서울특별시",
                "stance": "neutral",
                "intensity": 3,
                "action_intent": "ignore",
            },
        ]
    )


def test_stance_donut_creates_png(df, tmp_path):
    out = tmp_path / "stance.png"
    stance_donut(df, out)
    assert out.exists() and out.stat().st_size > 0


def test_intensity_hist_creates_png(df, tmp_path):
    out = tmp_path / "intensity.png"
    intensity_hist(df, out)
    assert out.exists()


def test_action_intent_bar_creates_png(df, tmp_path):
    out = tmp_path / "intent.png"
    action_intent_bar(df, out)
    assert out.exists()


def test_segment_heatmap_creates_png(df, tmp_path):
    out = tmp_path / "heat.png"
    segment_heatmap(df, segment="sex", out_path=out, min_cell=2)
    assert out.exists()


def test_count_sparse_strata_uses_full_strata():
    """sparse 카운트는 ``sex × age_band × province`` 기준이어야 한다.

    동일 province·sex 안에서 age_band가 다른 셀이 하나만 있으면, 단순
    ``province × sex`` 기준으로는 안 잡히던 strata가 잡혀야 한다.
    """
    df = pd.DataFrame(
        [
            {"sex": "남", "age": 25, "province": "서울특별시"},
            {"sex": "남", "age": 60, "province": "서울특별시"},
        ]
    )
    # 두 행의 sex·province는 같지만 age_band(20s vs 60s)가 다르므로
    # 두 strata 셀 모두 1명. threshold=2이면 두 셀 모두 sparse.
    assert count_sparse_strata(df, threshold=2) == 2
    assert count_sparse_strata(df, threshold=1) == 0
    assert count_sparse_strata(df, threshold=0) == 0


def test_segment_heatmap_masks_cells_not_rows(tmp_path):
    """행 합계가 충분해도 특정 stance 셀이 sparse면 그 셀만 회색 처리.

    여기선 단순히 함수가 에러 없이 PNG를 만들면 OK — 셀 단위 마스크 분기가
    실행되었음만 보장한다 (시각 검증은 수동).
    """
    df = pd.DataFrame(
        [
            *[
                {
                    "sex": "남",
                    "stance": "positive",
                    "intensity": 4,
                    "action_intent": "purchase",
                    "age": 30,
                    "province": "서울특별시",
                }
            ]
            * 20,
            {
                "sex": "남",
                "stance": "negative",
                "intensity": 1,
                "action_intent": "reject",
                "age": 30,
                "province": "서울특별시",
            },
        ]
    )
    out = tmp_path / "cell.png"
    segment_heatmap(df, segment="sex", out_path=out, min_cell=5)
    assert out.exists()
