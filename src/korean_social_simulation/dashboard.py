"""Streamlit 대시보드.

두 가지 모드를 지원한다.

- **Result viewer**: ``streamlit run dashboard.py -- <run_path>`` — 기존 run 결과를
  로드해 차트와 발언을 보여준다.
- **Run launcher**: 인자 없이 실행하면 ``scenarios/`` 의 YAML을 고르거나 새 시나리오를
  직접 작성한 뒤 모델·n·seed를 입력하고 그 자리에서 시뮬레이션을 돌려 결과 뷰로 이어진다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, get_args

import pandas as pd
import yaml
from pydantic import ValidationError

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise ImportError("streamlit이 설치되지 않았습니다. `uv sync --extra dashboard`로 설치하세요.") from exc

from korean_social_simulation.data.loader import load_personas
from korean_social_simulation.data.sampler import _apply_filters
from korean_social_simulation.llm.factory import (
    DEFAULT_CONCURRENCY,
    available_models,
)
from korean_social_simulation.report.charts import count_sparse_strata
from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario, ScenarioType
from korean_social_simulation.simulate import simulate

DEFAULT_SCENARIOS_DIR = Path("scenarios")
DEFAULT_RUNS_ROOT = Path("runs")
N_HARD_CAP = 1000
INSIGHTS_NONE_LABEL = "(생략)"
PREVIEW_QUOTE_MAX_CHARS = 140
PREVIEW_LINES = 6

_FILTER_COLUMNS: tuple[str, ...] = ("uuid", "sex", "age", "province")

_AGE_BAND_LABELS: tuple[str, ...] = (
    "~19", "20s", "30s", "40s", "50s", "60s", "70+",
)
_AGE_BAND_RANGES: dict[str, tuple[int, int]] = {
    "~19": (0, 19),
    "20s": (20, 29),
    "30s": (30, 39),
    "40s": (40, 49),
    "50s": (50, 59),
    "60s": (60, 69),
    "70+": (70, 200),
}


@st.cache_resource
def _cached_population_lite() -> tuple[pd.DataFrame, str]:
    """필터 위젯·카운트 미리보기 전용 경량 모집단 캐시.

    narrative/persona 텍스트 컬럼은 제외해 메모리 사용을 최소화한다.
    실제 시뮬레이션은 simulate() 내부에서 풀 dataset을 다시 로드하므로,
    이 캐시는 launcher UI 전용이다.

    Returns:
        ``(lite_df, dataset_fingerprint)`` — lite_df는 _FILTER_COLUMNS 만 포함.
    """
    ds, fp = load_personas()
    df = ds.select_columns(list(_FILTER_COLUMNS)).to_pandas()
    return df, fp


def main() -> None:
    """Streamlit 진입점."""
    st.set_page_config(page_title="Korean Social Simulation", layout="wide")

    run_path: Path | None = None
    if not st.session_state.get("force_launcher"):
        run_path = _resolve_run_path()
    if run_path is None:
        stored = st.session_state.get("run_path")
        if stored is not None:
            run_path = Path(stored)

    if run_path is not None:
        run = Run.load(run_path)
        _render_run_view(run)
        return

    _render_launcher()


def _render_launcher() -> None:
    """시나리오 선택 + 시뮬레이션 실행 폼."""
    # 위젯 렌더 이전에 클론 페이로드를 폼 session_state로 이관해야
    # Streamlit이 위젯 키 충돌 경고를 내지 않는다.
    _consume_pending_clone()

    st.title("Korean Social Simulation — Launcher")
    st.caption("시나리오를 골라 시뮬레이션을 실행합니다.")

    scenarios_dir = Path(st.text_input("시나리오 디렉터리", value=str(DEFAULT_SCENARIOS_DIR)))

    mode = st.radio(
        "시나리오 입력 방식",
        ["기존 YAML 선택", "직접 작성"],
        horizontal=True,
        key="scenario_input_mode",
    )

    pending_save_path: Path | None = None
    if mode == "기존 YAML 선택":
        scenario = _select_existing_scenario(scenarios_dir)
    else:
        scenario, pending_save_path = _compose_new_scenario(scenarios_dir)

    if scenario is None:
        return

    with st.expander("시나리오 미리보기", expanded=True):
        st.markdown(f"**제목:** {scenario.title}")
        st.markdown(f"**유형:** `{scenario.scenario_type}`")
        st.markdown("**자극(stimulus):**")
        st.markdown(f"> {scenario.stimulus}")
        if scenario.context:
            st.markdown("**맥락:**")
            st.markdown(f"> {scenario.context}")
        if scenario.question:
            st.markdown(f"**질문:** {scenario.question}")

    population_df, _population_fp = _cached_population_lite()
    filters = _render_filters(population_df)

    st.divider()
    st.subheader("실행 설정")

    models = available_models()
    insights_options = [INSIGHTS_NONE_LABEL, *models]
    col1, col2, col3 = st.columns(3)
    with col1:
        model = st.selectbox(
            "시뮬레이션 모델",
            models,
            index=models.index("vllm-qwen") if "vllm-qwen" in models else 0,
            help="페르소나 발언 생성에 사용 (페르소나 1개당 1 LLM 호출).",
        )
    with col2:
        insights_choice = st.selectbox(
            "리포트(인사이트) 모델",
            insights_options,
            index=0,
            help=f"종합 인사이트·리포트 생성에 사용. `{INSIGHTS_NONE_LABEL}` 선택 시 인사이트 단계를 건너뜁니다.",
        )
    with col3:
        n = st.number_input(
            "샘플 크기 n",
            min_value=1,
            max_value=N_HARD_CAP,
            value=50,
            step=10,
            help=f"비용 가드: 상한 {N_HARD_CAP}",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        seed = st.number_input("시드", min_value=0, value=42, step=1)
    with col5:
        default_conc = DEFAULT_CONCURRENCY.get(model, 8)
        concurrency = st.number_input(
            "동시성",
            min_value=1,
            max_value=64,
            value=default_conc,
            step=1,
            help="동시 LLM 호출 수. 시뮬레이션 모델별 디폴트가 자동으로 채워집니다.",
        )
    with col6:
        runs_root = Path(st.text_input("runs 루트", value=str(DEFAULT_RUNS_ROOT)))

    insights_model: str | None = None if insights_choice == INSIGHTS_NONE_LABEL else insights_choice

    if n >= 200:
        st.warning(f"n={n} — 모델 `{model}` 로 호출 비용·시간이 클 수 있습니다.")

    filtered_preview = _apply_filters(population_df, filters or {})
    n_pass = len(filtered_preview)
    n_total = len(population_df)
    can_run = True
    if n_pass == 0:
        st.error(f"❌ 필터 통과: 0명 / {n_total:,}명 — 조건을 완화하세요.")
        can_run = False
    elif n_pass < n:
        st.warning(
            f"⚠️ 필터 통과: {n_pass:,}명 / {n_total:,}명 — n={n} 보다 적습니다. "
            f"n을 줄이거나 필터를 완화하세요."
        )
        can_run = False
    else:
        st.success(f"✅ 필터 통과: {n_pass:,}명 / {n_total:,}명 — n={n} 샘플링 가능.")

    if not st.button("▶ Run simulation", type="primary", disabled=not can_run):
        return

    if pending_save_path is not None:
        try:
            _save_scenario_yaml(scenario, pending_save_path)
        except Exception as exc:  # noqa: BLE001
            st.error(f"시나리오 저장 실패 (`{pending_save_path}`): {exc}")
            return
        st.success(f"시나리오 저장: `{pending_save_path}`")

    n_total = int(n)
    progress_bar = st.progress(0.0, text=f"진행: 0/{n_total}")
    preview_box = st.empty()
    state = {"done": 0, "ok": 0, "fail": 0, "lines": []}

    def _on_progress(row: dict[str, Any]) -> None:
        state["done"] += 1
        if row.get("error"):
            state["fail"] += 1
            head = f"⚠️ error: {row['error']}"
        else:
            state["ok"] += 1
            quote = (row.get("quote") or "").strip().replace("\n", " ")
            if len(quote) > PREVIEW_QUOTE_MAX_CHARS:
                quote = quote[:PREVIEW_QUOTE_MAX_CHARS] + "…"
            stance = row.get("stance", "?")
            intensity = row.get("intensity", "?")
            head = f"[{stance}/{intensity}] {quote}"
        meta = f"{row.get('sex', '?')}, {row.get('age', '?')}, {row.get('province', '?')}"
        state["lines"].append(f"- **{meta}** — {head}")
        ratio = state["done"] / n_total
        progress_bar.progress(
            min(ratio, 1.0),
            text=f"진행: {state['done']}/{n_total}  (성공 {state['ok']} · 실패 {state['fail']})",
        )
        preview_box.markdown("\n".join(state["lines"][-PREVIEW_LINES:]))

    with st.spinner(f"`{model}` 로 n={n_total} 시뮬레이션 실행 중… (페르소나 1개당 1 LLM 호출)"):
        try:
            run = simulate(
                scenario=scenario,
                n=n_total,
                model=model,
                seed=int(seed),
                concurrency=int(concurrency),
                runs_root=runs_root,
                filters=filters,
                on_progress=_on_progress,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"시뮬레이션 실패: {type(exc).__name__}: {exc}")
            return

    progress_bar.progress(1.0, text=f"완료: {state['done']}/{n_total}")
    st.success(f"시뮬레이션 완료: `{run.path}`")

    if insights_model is not None:
        with st.spinner(f"`{insights_model}` 로 리포트 생성 중…"):
            try:
                md_path = run.report(insights_model=insights_model)
            except Exception as exc:  # noqa: BLE001
                st.error(f"리포트 생성 실패: {type(exc).__name__}: {exc}")
            else:
                st.success(f"📄 Report: `{md_path}`")

    st.session_state["run_path"] = str(run.path)
    st.session_state.pop("force_launcher", None)
    st.rerun()


def _render_run_view(run: Run) -> None:
    """기존 run 결과 뷰."""
    df = run.df.copy()

    header_col, btn_col = st.columns([5, 1])
    with header_col:
        st.title(run.scenario.title)
        st.caption(f"model={run.meta.get('model')}, n={run.meta.get('n')}, seed={run.meta.get('seed')}")
        filters_meta = run.meta.get("filters") or {}
        if filters_meta:
            st.caption(f"filters: {_format_filters_summary(filters_meta)}")
    with btn_col:
        if st.button("← Launcher"):
            st.session_state.pop("run_path", None)
            st.session_state["force_launcher"] = True
            st.rerun()

    threshold = run.meta.get("min_cell_threshold", 5)
    n_sparse = count_sparse_strata(df, threshold=threshold)
    if n_sparse:
        st.warning(f"⚠ {n_sparse}개 strata cell(`sex × age_band × province`)이 min_cell_threshold={threshold} 미만 — 세그먼트 결론 일반화에 주의.")

    with st.sidebar:
        st.header("필터")
        sex_filter = st.multiselect("성별", df["sex"].unique(), default=list(df["sex"].unique()))
        province_filter = st.multiselect("지역", df["province"].unique(), default=list(df["province"].unique()))
        df = df[df["sex"].isin(sex_filter) & df["province"].isin(province_filter)]

    tabs = st.tabs(["개요", "세그먼트", "발언", "Extra fields", "Raw"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Stance positive %", f"{(df['stance'] == 'positive').mean():.1%}")
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
                st.markdown(f"**{r['sex']}, {r['age']}, {r['province']}** — _{r['quote']}_")

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


def _select_existing_scenario(scenarios_dir: Path) -> Scenario | None:
    """``scenarios_dir`` 의 YAML 중 하나를 선택해 Scenario로 로드.

    선택된 시나리오를 그대로 실행할 수도 있고, "복제하여 수정" 버튼을 눌러
    '직접 작성' 폼으로 옮겨 편집·저장할 수도 있다.
    """
    yaml_files = _discover_scenarios(scenarios_dir)
    if not yaml_files:
        st.warning(f"`{scenarios_dir}` 에서 YAML 파일을 찾을 수 없습니다. 경로를 확인하거나 '직접 작성' 모드로 새 시나리오를 만들 수 있습니다.")
        return None

    selected = st.selectbox(
        "시나리오 YAML",
        yaml_files,
        format_func=lambda p: p.name,
    )
    scenario = _load_scenario(selected)
    if scenario is None:
        return None

    if st.button(
        "📋 복제하여 수정",
        help="이 시나리오를 '직접 작성' 폼으로 복사해 새 시나리오로 편집합니다.",
        key="clone_existing_scenario",
    ):
        st.session_state["_clone_payload"] = {
            "title": f"{scenario.title} (복제본)",
            "scenario_type": scenario.scenario_type,
            "stimulus": scenario.stimulus,
            "context": scenario.context or "",
            "question": scenario.question or "",
            "filename": f"{selected.stem}-copy.yaml",
        }
        st.rerun()

    return scenario


def _consume_pending_clone() -> None:
    """직전 rerun에서 적재된 클론 페이로드를 폼 session_state로 이관.

    ``_render_launcher`` 진입 직후, 어떤 위젯도 렌더되기 전에 호출해야 한다.
    Streamlit은 같은 run 안에서 이미 인스턴스화된 위젯 키의 session_state를
    수정하면 ``StreamlitAPIException`` 을 던지므로, 페이로드 적재 → ``st.rerun()``
    → 새 run 최상단에서 소비하는 2단계 패턴이 필요하다.
    """
    pending = st.session_state.pop("_clone_payload", None)
    if pending is None:
        return
    st.session_state["scenario_input_mode"] = "직접 작성"
    st.session_state["new_scenario_title"] = pending["title"]
    st.session_state["new_scenario_type"] = pending["scenario_type"]
    st.session_state["new_scenario_stimulus"] = pending["stimulus"]
    st.session_state["new_scenario_context"] = pending["context"]
    st.session_state["new_scenario_question"] = pending["question"]
    st.session_state["new_scenario_save_flag"] = True
    st.session_state["new_scenario_filename"] = pending["filename"]


def _render_filters(population_df: pd.DataFrame) -> dict[str, Any] | None:
    """`📊 대상 필터링` 섹션을 렌더링하고 simulate에 전달할 filter dict를 반환.

    Returns:
        모든 축이 "전부" 일 때는 ``None``, 그 외에는 사용자가 좁힌 축만 담은 dict.
        반환된 dict는 ``simulate(filters=...)`` 또는 ``_apply_filters`` 에 그대로 전달.
    """
    sex_options = sorted(population_df["sex"].unique().tolist())
    province_options = sorted(population_df["province"].unique().tolist())
    age_min_data = int(population_df["age"].min())
    age_max_data = int(population_df["age"].max())

    with st.expander("📊 대상 필터링", expanded=True):
        st.caption("페르소나 모집단을 좁혀 시뮬레이션합니다. 모두 '전부' 선택이면 필터 없음.")

        col_sx, col_pv = st.columns(2)
        with col_sx:
            sex_sel = st.multiselect(
                "성별", sex_options, default=sex_options, key="filter_sex"
            )
        with col_pv:
            province_sel = st.multiselect(
                "지역", province_options, default=province_options, key="filter_province"
            )

        age_mode = st.radio(
            "연령 입력 방식",
            ["범위", "연령대"],
            horizontal=True,
            key="filter_age_mode",
        )

        if age_mode == "범위":
            age_range = st.slider(
                "연령 범위",
                min_value=age_min_data,
                max_value=age_max_data,
                value=(age_min_data, age_max_data),
                key="filter_age_range",
            )
            age_filter_value: Any = None
            if age_range[0] > age_min_data or age_range[1] < age_max_data:
                age_filter_value = {"min": age_range[0], "max": age_range[1]}
        else:
            bands_sel = st.multiselect(
                "연령대",
                list(_AGE_BAND_LABELS),
                default=list(_AGE_BAND_LABELS),
                key="filter_age_bands",
            )
            age_filter_value = None
            if set(bands_sel) != set(_AGE_BAND_LABELS):
                if not bands_sel:
                    # 0개 선택은 빈 결과 → 빈 list로 표현
                    age_filter_value = []
                else:
                    age_set: set[int] = set()
                    for b in bands_sel:
                        lo, hi = _AGE_BAND_RANGES[b]
                        age_set.update(range(lo, hi + 1))
                    age_filter_value = sorted(age_set)

    filters: dict[str, Any] = {}
    if set(sex_sel) != set(sex_options):
        filters["sex"] = sex_sel
    if set(province_sel) != set(province_options):
        filters["province"] = province_sel
    if age_filter_value is not None:
        filters["age"] = age_filter_value

    return filters or None


def _format_filters_summary(filters: dict[str, Any]) -> str:
    """run view caption용 필터 요약 문자열.

    예: ``남자 / 서울특별시+경기도 / age 25-34`` — 컬럼별로 ' / ' 로 구분.
    """
    parts: list[str] = []
    for col, val in filters.items():
        if isinstance(val, list) and val:
            parts.append("+".join(str(v) for v in val))
        elif isinstance(val, dict) and ("min" in val or "max" in val):
            lo = val.get("min", "")
            hi = val.get("max", "")
            parts.append(f"{col} {lo}-{hi}")
        else:
            parts.append(str(val))
    return " / ".join(parts) if parts else "(없음)"


def _compose_new_scenario(scenarios_dir: Path) -> tuple[Scenario | None, Path | None]:
    """폼 입력으로 Scenario를 구성하고, 선택 시 저장 경로를 함께 반환.

    Returns:
        ``(scenario, save_path)`` — ``scenario`` 는 검증 실패/미입력 시 ``None`` 이고,
        ``save_path`` 는 사용자가 디스크 저장을 켰을 때만 non-None.
    """
    type_options = list(get_args(ScenarioType))
    default_type_idx = type_options.index("other") if "other" in type_options else 0

    title = st.text_input(
        "제목",
        key="new_scenario_title",
        placeholder="예: 신라면 신제품 광고",
        help="짧은 식별자. 파일명 슬러그로도 사용됩니다.",
    )
    scenario_type = st.selectbox(
        "유형",
        type_options,
        index=default_type_idx,
        key="new_scenario_type",
    )
    stimulus = st.text_area(
        "자극 (stimulus)",
        key="new_scenario_stimulus",
        height=160,
        placeholder="페르소나가 노출될 본문(광고 카피, 정책 문구, 기사 등)을 작성하세요.",
    )
    context = st.text_area(
        "맥락 (context, 선택)",
        key="new_scenario_context",
        height=100,
        placeholder="시장 상황·배경 등 추가 맥락이 있다면 입력하세요.",
    )
    question = st.text_input(
        "질문 (question, 선택)",
        key="new_scenario_question",
        placeholder="페르소나에게 던질 핵심 질문이 있다면 입력하세요.",
    )

    save_to_disk = st.checkbox(
        f"`{scenarios_dir}` 에 YAML로 저장",
        key="new_scenario_save_flag",
        help="체크하면 Run 버튼 클릭 시 시뮬레이션 직전에 파일로 저장합니다.",
    )

    save_path: Path | None = None
    if save_to_disk:
        if "new_scenario_filename" not in st.session_state:
            default_name = ""
            if title.strip():
                try:
                    default_name = f"{Scenario(title=title, stimulus='_').slug()}.yaml"
                except ValidationError:
                    default_name = ""
            st.session_state["new_scenario_filename"] = default_name
        filename = st.text_input(
            "파일명",
            key="new_scenario_filename",
            help=".yaml 확장자가 없으면 자동으로 붙입니다.",
        )
        filename = filename.strip()
        if filename:
            if not filename.endswith((".yaml", ".yml")):
                filename = f"{filename}.yaml"
            save_path = scenarios_dir / filename
            if save_path.exists():
                st.warning(f"⚠ `{save_path}` 이미 존재합니다. Run을 누르면 덮어씁니다.")

    if not title.strip() or not stimulus.strip():
        st.info("제목과 자극(stimulus)을 입력하면 미리보기와 실행 설정이 표시됩니다.")
        return None, None

    try:
        scenario = Scenario(
            title=title.strip(),
            stimulus=stimulus,
            context=context.strip() or None,
            scenario_type=scenario_type,
            question=question.strip() or None,
        )
    except ValidationError as exc:
        st.error(f"시나리오 검증 실패: {exc}")
        return None, None

    return scenario, save_path


def _save_scenario_yaml(scenario: Scenario, path: Path) -> None:
    """Scenario를 YAML로 직렬화해 ``path`` 에 저장. 부모 디렉터리는 자동 생성."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": scenario.title,
        "scenario_type": scenario.scenario_type,
        "stimulus": scenario.stimulus,
    }
    if scenario.context is not None:
        payload["context"] = scenario.context
    if scenario.question is not None:
        payload["question"] = scenario.question
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _discover_scenarios(directory: Path) -> list[Path]:
    """``directory`` 하위 .yaml/.yml 파일을 정렬된 리스트로 반환."""
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted([p for p in directory.iterdir() if p.suffix in {".yaml", ".yml"}])


def _load_scenario(path: Path) -> Scenario | None:
    """YAML을 읽어 Scenario를 반환. 실패 시 에러를 표시하고 None."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Scenario(**data)
    except Exception as exc:  # noqa: BLE001
        st.error(f"시나리오 로드 실패 (`{path.name}`): {exc}")
        return None


def _resolve_run_path() -> Path | None:
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1])
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    main()
