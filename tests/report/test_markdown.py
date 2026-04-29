"""report.md 렌더링."""

import pandas as pd

from korean_social_simulation.report.markdown import render_report
from korean_social_simulation.scenario import Scenario


def test_render_report_creates_md_and_charts(tmp_path):
    scenario = Scenario(title="신라면", stimulus="...")
    df = pd.DataFrame(
        [
            {
                "uuid": f"u{i}",
                "sex": "남" if i % 2 else "여",
                "age": 30 + i,
                "province": "서울특별시",
                "stance": "positive" if i < 5 else "negative",
                "intensity": 3,
                "action_intent": "purchase",
                "key_drivers": ["맛"],
                "concerns": [],
                "quote": f"q{i}",
                "latency_ms": 100,
                "error": None,
                "model": "fake",
            }
            for i in range(10)
        ]
    )
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    (out_dir / "charts").mkdir()

    md_path = render_report(
        out_dir=out_dir,
        scenario=scenario,
        df=df,
        meta={
            "model": "fake",
            "n": 10,
            "seed": 1,
            "dataset_fingerprint": "fp",
            "sampler_version": "1",
            "min_cell_threshold": 5,
        },
        insights="자동 인사이트 텍스트",
    )
    assert md_path.exists()
    md = md_path.read_text(encoding="utf-8")
    assert "신라면" in md
    assert "자동 인사이트 텍스트" in md
    assert "charts/stance.png" in md
