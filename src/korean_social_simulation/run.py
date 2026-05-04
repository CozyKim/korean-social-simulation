"""Run — 한 번의 시뮬레이션 산출물을 표현하는 데이터클래스."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
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
        allow_existing: bool = False,
    ) -> Run:
        """산출물 디렉터리를 새로 만들고 scenario/reactions/sample을 직렬화한다.

        같은 ``run_id`` 가 이미 존재하면 ``FileExistsError`` 를 던진다 — 기존 run을
        조용히 덮어쓰지 않도록 보호한다. 자동 생성되는 ID는 microseconds + uuid
        suffix를 포함해 같은 초의 충돌을 방지한다.

        Args:
            root: 모든 run을 모아두는 루트 (예: ``runs/``).
            scenario: 입력 시나리오.
            reactions: 반응 결과 DataFrame.
            sample: 사용된 샘플 DataFrame (페르소나 메타).
            meta: 재현성·LLM 정보 (model, n, seed, dataset_fingerprint 등).
            run_id: 명시적 ID. 없으면 자동 생성.
            allow_existing: ``True`` 이면 같은 ``run_id`` 의 디렉터리가 이미 있어도
                덮어쓰지 않고 그대로 사용해 메타·결과를 재기록한다 (멱등). FastAPI
                job manager가 시뮬 시작 시점에 미리 디렉터리를 만들어 두고 종료 시
                같은 ID로 다시 호출할 수 있도록 한다.

        Returns:
            새로 생성된 Run.

        Raises:
            FileExistsError: ``run_id`` 디렉터리가 이미 존재하고 ``allow_existing``
                이 ``False`` 일 때.
        """
        run_id = run_id or _new_run_id(scenario.slug())
        path = Path(root) / run_id
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir(exist_ok=allow_existing)
        except FileExistsError as exc:
            raise FileExistsError(f"Run directory already exists: {path}. 기존 run 보호를 위해 덮어쓰지 않습니다. 다른 run_id로 다시 시도하세요.") from exc
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
            if not allow_existing:
                shutil.rmtree(path, ignore_errors=True)
            raise
        return cls(path=path, scenario=scenario, df=reactions, meta=meta)

    @classmethod
    def create_pending(
        cls,
        *,
        root: Path,
        scenario: Scenario,
        meta: dict[str, Any],
        run_id: str,
    ) -> Path:
        """시뮬 시작 시점에 디렉터리만 미리 만들고 partial.jsonl 빈 파일 둔다.

        FastAPI job manager가 ``POST /api/runs`` 직후에 호출. 시뮬 진행 중에는
        ``reactions.partial.jsonl`` 에 페르소나별 응답을 1줄씩 append하고,
        시뮬 종료 시 ``Run.finalize_pending`` 으로 parquet으로 변환한다.

        Args:
            root: 모든 run을 모아두는 루트.
            scenario: 입력 시나리오.
            meta: 재현성·LLM 정보.
            run_id: 명시적 ID. job manager가 미리 발급한 uuid.

        Returns:
            생성된 디렉터리 경로.

        Raises:
            FileExistsError: 같은 run_id 디렉터리가 이미 있을 때.
        """
        path = Path(root) / run_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir(exist_ok=False)
        (path / "charts").mkdir(exist_ok=True)
        (path / "scenario.json").write_text(
            json.dumps(
                {
                    "scenario": scenario.model_dump(),
                    "meta": meta,
                    "run_id": run_id,
                    "status": "running",
                    "public": False,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (path / "reactions.partial.jsonl").write_text("", encoding="utf-8")
        return path

    @staticmethod
    def append_partial(path: Path, row: dict[str, Any]) -> None:
        """partial.jsonl에 reaction 1건을 append. 동시 호출은 단일 워커 가정."""
        partial = Path(path) / "reactions.partial.jsonl"
        with partial.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @classmethod
    def finalize_pending(
        cls,
        path: Path,
        *,
        sample: pd.DataFrame,
    ) -> Run:
        """partial.jsonl을 reactions.parquet으로 변환하고 status=completed로 표시.

        Args:
            path: ``create_pending`` 으로 만든 run 디렉터리.
            sample: 사용된 페르소나 메타 — sample.parquet으로 저장.

        Returns:
            완성된 Run.

        Raises:
            FileNotFoundError: partial.jsonl이 없을 때 (이미 finalize되었거나
                create_pending이 호출되지 않은 경우).
        """
        path = Path(path)
        partial = path / "reactions.partial.jsonl"
        if not partial.exists():
            raise FileNotFoundError(f"No partial file at {partial}")

        rows = [json.loads(line) for line in partial.read_text(encoding="utf-8").splitlines() if line.strip()]
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        df.to_parquet(path / "reactions.parquet", index=False)
        sample.to_parquet(path / "sample.parquet", index=False)
        partial.unlink()

        meta_path = path / "scenario.json"
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data["status"] = "completed"
        data["completed_at"] = datetime.now(UTC).isoformat()
        meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        scenario = Scenario(**data["scenario"])
        return cls(path=path, scenario=scenario, df=df, meta=data["meta"])

    @classmethod
    def mark_failed(cls, path: Path, error: str) -> None:
        """status=failed + error 메시지를 scenario.json에 기록 (partial은 그대로 둠)."""
        path = Path(path)
        meta_path = path / "scenario.json"
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data["status"] = "failed"
        data["error"] = error
        data["failed_at"] = datetime.now(UTC).isoformat()
        meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> Run:
        """기존 run 디렉터리에서 Run을 복원한다."""
        path = Path(path)
        data = json.loads((path / "scenario.json").read_text(encoding="utf-8"))
        scenario = Scenario(**data["scenario"])
        df = pd.read_parquet(path / "reactions.parquet")
        return cls(path=path, scenario=scenario, df=df, meta=data["meta"])

    async def areport(
        self,
        *,
        insights_model: str | None = None,
    ) -> Path:
        """리포트 생성 (async). ``report.md`` 경로를 반환한다.

        ``insights_model`` 이 ``None`` 이면 LLM 종합 인사이트는 생략한다.
        """
        from korean_social_simulation.llm.factory import get_llm
        from korean_social_simulation.report.insights import generate_insights
        from korean_social_simulation.report.markdown import render_report

        if insights_model is not None:
            llm = get_llm(insights_model)
            insights = await generate_insights(self.df, llm=llm)
        else:
            insights = "_(insights_model이 지정되지 않아 LLM 종합 인사이트는 생략됨)_"

        return render_report(
            out_dir=self.path,
            scenario=self.scenario,
            df=self.df,
            meta=self.meta,
            insights=insights,
        )

    def report(
        self,
        *,
        insights_model: str | None = None,
    ) -> Path:
        """동기 wrapper — 실행 중인 이벤트 루프가 있으면 명확히 안내하며 실패한다.

        async 컨텍스트에서는 :meth:`areport` 를 ``await`` 한다.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Run.report()는 동기 컨텍스트에서만 호출할 수 있습니다. 노트북·async 환경에서는 `await run.areport(...)` 를 사용하세요.")
        return asyncio.run(self.areport(insights_model=insights_model))


def _new_run_id(slug: str) -> str:
    """타임스탬프(microseconds) + uuid suffix로 run_id 충돌을 방지한다."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}-{suffix}-{slug}"
