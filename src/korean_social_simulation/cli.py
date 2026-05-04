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
    run = simulate(scenario=scen, n=n, model=model, seed=seed, runs_root=runs_root)
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
    typer.echo(f"Model: {run.meta.get('model')}, n={run.meta.get('n')}, seed={run.meta.get('seed')}")
    typer.echo("Stance distribution:")
    typer.echo(run.df["stance"].value_counts(normalize=True).round(3).to_string())


@app.command("dashboard")
def dashboard_cmd(
    run_path: Path = typer.Argument(
        None,
        help="기존 run 디렉터리. 생략하면 launcher 모드로 진입.",
    ),
) -> None:
    """Streamlit 대시보드 실행 (extras ``dashboard`` 필요).

    인자 없이 실행하면 시나리오를 골라 그 자리에서 시뮬레이션을 시작할 수 있는
    launcher 모드로 진입한다.
    """
    import subprocess
    import sys

    from korean_social_simulation import dashboard as _dash  # noqa: F401

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(_dash.__file__)),
    ]
    if run_path is not None:
        cmd += ["--", str(run_path)]
    subprocess.run(cmd, check=True)


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="bind 주소"),
    port: int = typer.Option(8000, "--port", help="bind 포트"),
) -> None:
    """FastAPI 백엔드를 uvicorn으로 띄운다.

    환경변수 ``KSS_OWNER_TOKEN``, ``KSS_COOKIE_SECRET`` 가 필요하다.
    extras ``api`` 가 설치되어 있어야 한다 (``uv sync --extra api``).
    """
    try:
        import uvicorn
    except ImportError as exc:
        typer.echo("uvicorn이 설치되지 않았습니다. `uv sync --extra api`로 설치하세요.", err=True)
        raise typer.Exit(code=1) from exc

    uvicorn.run(
        "korean_social_simulation.api.main:app",
        host=host,
        port=port,
        workers=1,
        log_level="info",
    )


if __name__ == "__main__":
    app()
