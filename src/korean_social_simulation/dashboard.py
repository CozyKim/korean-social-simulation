"""Streamlit 대시보드 — ``python -m streamlit run dashboard.py -- <run_path>``."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "streamlit이 설치되지 않았습니다. `uv sync --extra dashboard`로 설치하세요."
    ) from exc

from korean_social_simulation.report.charts import count_sparse_strata
from korean_social_simulation.run import Run


def main() -> None:
    """Streamlit 진입점."""
    st.set_page_config(page_title="Korean Social Simulation", layout="wide")

    run_path = _resolve_run_path()
    if run_path is None:
        st.error("run 경로를 인자로 전달하세요: `streamlit run dashboard.py -- <path>`")
        return

    run = Run.load(run_path)
    df = run.df.copy()

    st.title(run.scenario.title)
    st.caption(
        f"model={run.meta.get('model')}, n={run.meta.get('n')}, "
        f"seed={run.meta.get('seed')}"
    )

    threshold = run.meta.get("min_cell_threshold", 5)
    n_sparse = count_sparse_strata(df, threshold=threshold)
    if n_sparse:
        st.warning(
            f"⚠ {n_sparse}개 strata cell(`sex × age_band × province`)이 "
            f"min_cell_threshold={threshold} 미만 — 세그먼트 결론 일반화에 주의."
        )

    with st.sidebar:
        st.header("필터")
        sex_filter = st.multiselect(
            "성별", df["sex"].unique(), default=list(df["sex"].unique())
        )
        province_filter = st.multiselect(
            "지역", df["province"].unique(), default=list(df["province"].unique())
        )
        df = df[df["sex"].isin(sex_filter) & df["province"].isin(province_filter)]

    tabs = st.tabs(["개요", "세그먼트", "발언", "Extra fields", "Raw"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Stance positive %", f"{(df['stance'] == 'positive').mean():.1%}"
        )
        c2.metric("Avg intensity", f"{df['intensity'].mean():.2f}")
        c3.metric("실패율", f"{df['error'].notna().mean():.1%}")
        st.bar_chart(df["stance"].value_counts())
        st.bar_chart(df["action_intent"].value_counts())

    with tabs[1]:
        for seg in ["sex", "province"]:
            st.subheader(f"{seg} × stance")
            ct = pd.crosstab(df[seg], df["stance"], normalize="index")
            st.dataframe(ct.style.format("{:.1%}"))

    with tabs[2]:
        for stance in ["positive", "negative", "neutral", "mixed"]:
            sub = df[df["stance"] == stance].head(10)
            if sub.empty:
                continue
            st.subheader(f"{stance} ({len(sub)})")
            for _, r in sub.iterrows():
                st.markdown(
                    f"**{r['sex']}, {r['age']}, {r['province']}** — _{r['quote']}_"
                )

    with tabs[3]:
        meta_extras = run.meta.get("extra_field_names") or []
        if not meta_extras:
            st.info("extra fields가 정의되지 않은 run입니다.")
        else:
            for name in meta_extras:
                if name in df.columns:
                    st.subheader(name)
                    if pd.api.types.is_numeric_dtype(df[name]):
                        st.bar_chart(df[name])
                    else:
                        st.bar_chart(df[name].value_counts())

    with tabs[4]:
        st.dataframe(df)


def _resolve_run_path() -> Path | None:
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1])
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    main()
