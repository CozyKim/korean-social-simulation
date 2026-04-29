"""Run — 한 번의 시뮬레이션 산출물을 표현하는 데이터클래스."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from korean_social_simulation.scenario import Scenario


@dataclass(frozen=True)
class Run:
    """한 번의 시뮬레이션 결과 디렉터리에 대한 핸들."""

    path: Path
    scenario: Scenario
    df: pd.DataFrame
    meta: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        root: Path,
        scenario: Scenario,
        reactions: pd.DataFrame,
        sample: pd.DataFrame,
        meta: dict[str, Any],
        run_id: str | None = None,
    ) -> Run:
        """산출물 디렉터리를 새로 만들고 scenario/reactions/sample을 직렬화한다.

        Args:
            root: 모든 run을 모아두는 루트 (예: ``runs/``).
            scenario: 입력 시나리오.
            reactions: 반응 결과 DataFrame.
            sample: 사용된 샘플 DataFrame (페르소나 메타).
            meta: 재현성·LLM 정보 (model, n, seed, dataset_fingerprint 등).
            run_id: 명시적 ID. 없으면 ``YYYYMMDD-HHMMSS-{slug}`` 자동 생성.

        Returns:
            새로 생성된 Run.
        """
        run_id = run_id or _new_run_id(scenario.slug())
        path = Path(root) / run_id
        path.mkdir(parents=True, exist_ok=True)
        try:
            (path / "charts").mkdir(exist_ok=True)
            (path / "scenario.json").write_text(
                json.dumps(
                    {
                        "scenario": scenario.model_dump(),
                        "meta": meta,
                        "run_id": run_id,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            reactions.to_parquet(path / "reactions.parquet", index=False)
            sample.to_parquet(path / "sample.parquet", index=False)
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            raise
        return cls(path=path, scenario=scenario, df=reactions, meta=meta)

    @classmethod
    def load(cls, path: Path) -> Run:
        """기존 run 디렉터리에서 Run을 복원한다."""
        path = Path(path)
        data = json.loads((path / "scenario.json").read_text(encoding="utf-8"))
        scenario = Scenario(**data["scenario"])
        df = pd.read_parquet(path / "reactions.parquet")
        return cls(path=path, scenario=scenario, df=df, meta=data["meta"])

    def report(
        self,
        *,
        insights_model: str | None = None,
    ) -> Path:
        """리포트를 생성하고 ``report.md`` 경로를 반환한다.

        ``insights_model`` 이 ``None`` 이면 LLM 종합 인사이트는 생략하고
        통계/차트만 포함한 리포트를 만든다.
        """
        import asyncio

        from korean_social_simulation.llm.factory import get_llm
        from korean_social_simulation.report.insights import generate_insights
        from korean_social_simulation.report.markdown import render_report

        if insights_model is not None:
            llm = get_llm(insights_model)
            insights = asyncio.run(generate_insights(self.df, llm=llm))
        else:
            insights = "_(insights_model이 지정되지 않아 LLM 종합 인사이트는 생략됨)_"

        return render_report(
            out_dir=self.path,
            scenario=self.scenario,
            df=self.df,
            meta=self.meta,
            insights=insights,
        )


def _new_run_id(slug: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slug}"
