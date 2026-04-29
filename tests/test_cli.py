"""CLI 검증 — CliRunner + 설치된 entry point 두 경로 모두."""

import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from korean_social_simulation.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "list" in result.stdout
    assert "dashboard" in result.stdout


def test_run_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--scenario" in result.stdout
    assert "--n" in result.stdout
    assert "--model" in result.stdout


def test_installed_kss_entry_point_runs_outside_repo(tmp_path):
    """설치된 ``kss --help`` 가 레포 루트 밖에서도 동작하는지 검증.

    CLI가 wheel/sdist에 포함되지 않으면 (예: 패키지 외부 ``cli/`` 디렉터리에
    둔 경우) 설치 후 즉시 실패한다. 이 테스트는 그 회귀를 잡는다.
    """
    kss_bin = shutil.which("kss")
    if not kss_bin:
        pytest.skip("kss not on PATH (uv sync로 설치 후 재실행)")

    result = subprocess.run(
        [kss_bin, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"kss --help failed: {result.stderr}"
    assert "run" in result.stdout
