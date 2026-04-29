"""Korean Social Simulation CLI."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario
from korean_social_simulation.simulate import simulate

app = typer.Typer(
    add_completion=False,
    help="Korean Social Simulation — 한국 페르소나 기반 사회 시뮬레이션",
)


@app.command("run")
def run_cmd(
    scenario: Path = typer.Option(..., "--scenario", help="시나리오 YAML 파일"),
    n: int = typer.Option(200, "--n", help="샘플 크기"),
    model: str = typer.Option("vllm-qwen", "--model", help="LLM 모델 ID"),
    seed: int = typer.Option(42, "--seed"),
    insights_model: str = typer.Option(
        None,
        "--insights-model",
        help="종합 인사이트용 LLM (생략 시 인사이트 단계 건너뜀)",
    ),
    runs_root: Path = typer.Option(Path("runs"), "--runs-root"),
) -> None:
    """시나리오 YAML을 받아 시뮬을 실행하고 report.md 까지 생성."""
    data = yaml.safe_load(scenario.read_text(encoding="utf-8"))
    scen = Scenario(**data)
    run = simulate(
        scenario=scen, n=n, model=model, seed=seed, runs_root=runs_root
    )
    md = run.report(insights_model=insights_model)
    typer.echo(f"✅ Run saved to: {run.path}")
    typer.echo(f"📄 Report: {md}")


@app.command("list")
def list_cmd(
    runs_root: Path = typer.Option(Path("runs"), "--runs-root"),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    """최근 run 디렉터리 목록."""
    if not runs_root.exists():
        typer.echo("(no runs)")
        return
    dirs = sorted(
        [p for p in runs_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    for d in dirs:
        typer.echo(f"  {d.name}")


@app.command("inspect")
def inspect_cmd(run_path: Path) -> None:
    """run의 메타와 통계를 출력."""
    run = Run.load(run_path)
    typer.echo(f"Title: {run.scenario.title}")
    typer.echo(
        f"Model: {run.meta.get('model')}, n={run.meta.get('n')}, "
        f"seed={run.meta.get('seed')}"
    )
    typer.echo("Stance distribution:")
    typer.echo(run.df["stance"].value_counts(normalize=True).round(3).to_string())


@app.command("dashboard")
def dashboard_cmd(run_path: Path) -> None:
    """Streamlit 대시보드 실행 (extras ``dashboard`` 필요)."""
    import subprocess
    import sys

    from korean_social_simulation import dashboard as _dash  # noqa: F401

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(Path(_dash.__file__)),
            "--",
            str(run_path),
        ],
        check=True,
    )


if __name__ == "__main__":
    app()
