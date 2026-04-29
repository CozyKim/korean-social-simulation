"""마크다운 리포트 렌더링."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from korean_social_simulation.report.charts import (
    action_intent_bar,
    intensity_hist,
    segment_heatmap,
    stance_donut,
)
from korean_social_simulation.scenario import Scenario


def render_report(
    *,
    out_dir: Path,
    scenario: Scenario,
    df: pd.DataFrame,
    meta: dict[str, Any],
    insights: str,
) -> Path:
    """report.md를 ``out_dir`` 에 생성하고 그 경로를 반환."""
    charts = out_dir / "charts"
    stance_donut(df, charts / "stance.png")
    intensity_hist(df, charts / "intensity.png")
    action_intent_bar(df, charts / "intent.png")
    segment_heatmap(
        df,
        segment="sex",
        out_path=charts / "seg_sex.png",
        min_cell=meta.get("min_cell_threshold", 5),
    )
    segment_heatmap(
        df,
        segment="province",
        out_path=charts / "seg_province.png",
        min_cell=meta.get("min_cell_threshold", 5),
    )

    md = _render_markdown(scenario, df, meta, insights)
    path = out_dir / "report.md"
    path.write_text(md, encoding="utf-8")
    return path


def _render_markdown(
    scenario: Scenario,
    df: pd.DataFrame,
    meta: dict[str, Any],
    insights: str,
) -> str:
    n = len(df)
    error_rate = (df["error"].notna().sum() / n) if n else 0.0
    avg_latency = int(df["latency_ms"].mean()) if n else 0
    sparse_note = ""
    threshold = meta.get("min_cell_threshold", 5)
    if threshold > 0:
        cells = df.groupby(["province", "sex"]).size()
        sparse_n = (cells < threshold).sum()
        if sparse_n:
            sparse_note = (
                f"> ⚠ **희소 strata 경고**: {sparse_n}개 셀이 임계값 "
                f"{threshold} 미만입니다. 세그먼트 결론 일반화에 주의.\n"
            )

    fingerprint = meta.get("dataset_fingerprint", "")
    fingerprint_short = fingerprint[:12] if fingerprint else ""
    return f"""# {scenario.title}

- **모델**: {meta.get("model")}
- **샘플**: {meta.get("n")} (seed={meta.get("seed")})
- **재현 정보**: dataset_fingerprint=`{fingerprint_short}`, sampler_version=`{meta.get("sampler_version")}`
- **시나리오 타입**: {scenario.scenario_type}

## 시나리오 stimulus

> {scenario.stimulus}

{sparse_note}
## 핵심 결과

![stance](charts/stance.png)

![intensity](charts/intensity.png)

![action_intent](charts/intent.png)

## 세그먼트 분석

### 성별 × stance
![seg_sex](charts/seg_sex.png)

### 지역 × stance
![seg_province](charts/seg_province.png)

## 대표 발언

{_top_quotes(df)}

## 종합 인사이트

{insights}

## 부록 — 호출 통계

- 총 호출: {n}
- 실패율: {error_rate:.1%}
- 평균 latency: {avg_latency}ms
"""


def _top_quotes(df: pd.DataFrame, per_stance: int = 3) -> str:
    lines: list[str] = []
    for stance in ["positive", "negative", "neutral", "mixed"]:
        sub = df[df["stance"] == stance].head(per_stance)
        if sub.empty:
            continue
        lines.append(f"### {stance}")
        for _, r in sub.iterrows():
            meta = f"({r.get('sex')}, {r.get('age')}, {r.get('province')})"
            lines.append(f'- {meta} "{r.get("quote", "")}"')
        lines.append("")
    return "\n".join(lines)
