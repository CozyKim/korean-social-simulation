"""차트 생성 — 파일이 만들어지면 OK (이미지 내용은 비교 안 함)."""

import pandas as pd
import pytest

from korean_social_simulation.report.charts import (
    action_intent_bar,
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
