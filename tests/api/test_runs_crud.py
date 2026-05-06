"""Runs 목록·상세 — public 가시성 + 권한 게이트."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def _make_run(runs_root: Path, run_id: str, *, public: bool = False) -> Path:
    scenario = Scenario(title=f"t-{run_id}", stimulus="s")
    Run.create(
        root=runs_root,
        scenario=scenario,
        reactions=pd.DataFrame([{"sex": "female", "stance": "positive"}]),
        sample=pd.DataFrame([{"sex": "female", "age": 28}]),
        meta={"model": "vllm-qwen", "n": 1},
        run_id=run_id,
    )
    meta_path = runs_root / run_id / "scenario.json"
    data = json.loads(meta_path.read_text())
    data["public"] = public
    data["status"] = "completed"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return runs_root / run_id


def test_list_runs_anonymous_only_public(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    _make_run(runs_root, "priv", public=False)
    r = client.get("/api/runs")
    assert r.status_code == 200
    ids = [item["run_id"] for item in r.json()]
    assert "pub" in ids
    assert "priv" not in ids


def test_list_runs_owner_sees_private(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    _make_run(runs_root, "priv", public=False)
    _login(client)
    r = client.get("/api/runs")
    ids = [item["run_id"] for item in r.json()]
    assert {"pub", "priv"} <= set(ids)


def test_get_private_run_anonymous_404(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "priv", public=False)
    r = client.get("/api/runs/priv")
    assert r.status_code == 404


def test_get_public_run_returns_meta(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    r = client.get("/api/runs/pub")
    assert r.status_code == 200
    assert r.json()["title"] == "t-pub"


def test_delete_run(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "rid")
    _login(client)
    r = client.delete("/api/runs/rid")
    assert r.status_code == 204
    assert not (settings_env / "runs" / "rid").exists()


def test_delete_run_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """percent-encoded `..` 같은 traversal 시도는 거부되어야 하고 runs_root 의 형제
    디렉터리는 절대 삭제되지 않아야 한다."""
    runs_root = settings_env / "runs"
    sibling = settings_env / "scenarios"
    assert sibling.exists()  # conftest 가 만들어 둠

    _login(client)

    # 다양한 traversal 변형 — 모두 4xx 로 거부되어야 한다.
    # 슬래시가 path 안에 들어간 변형(`../scenarios`, `/etc/passwd`)은 FastAPI 라우터
    # 단계에서 405/404 로 떨어지지만, 그래도 절대 외부 디렉터리는 삭제되지 말아야 한다.
    for run_id in ("..", "%2E%2E", "../scenarios", "..%2Fscenarios", "foo/../..", "/etc/passwd"):
        r = client.delete(f"/api/runs/{run_id}")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"

    # 외부 디렉터리는 손상되지 않아야 한다.
    assert sibling.exists()
    assert runs_root.exists()


# 라우터까지 도달하는 단일-세그먼트 traversal payload — codex 가 지적한 핵심 시나리오.
# 슬래시 포함 변형(``../x``, ``/etc/passwd``)은 클라이언트/스타렛 단계에서 다른 라우트로
# 정규화·매칭될 수 있어 의미가 달라지므로 별도 케이스(_test_delete_run_rejects_path_traversal_)
# 에서 외부 디렉터리 보존 여부로 확인한다.
_TRAVERSAL_RUN_IDS = (
    "..",
    "%2E%2E",
    "%2E%2E%2F",
    ".%2E",
)


def test_get_run_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """GET /api/runs/{run_id} 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.get(f"/api/runs/{run_id}")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_patch_run_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """PATCH /api/runs/{run_id} 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.patch(f"/api/runs/{run_id}", json={"public": True})
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_stream_events_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """GET /api/runs/{run_id}/events SSE 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.get(f"/api/runs/{run_id}/events")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_stream_reactions_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """GET /api/runs/{run_id}/reactions 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.get(f"/api/runs/{run_id}/reactions")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_stream_charts_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """GET /api/runs/{run_id}/charts/{name} 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.get(f"/api/runs/{run_id}/charts/x.png")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_stream_report_rejects_path_traversal(settings_env: Path, client: TestClient) -> None:
    """GET /api/runs/{run_id}/report 도 traversal 시도를 거부해야 한다."""
    _login(client)
    for run_id in _TRAVERSAL_RUN_IDS:
        r = client.get(f"/api/runs/{run_id}/report")
        assert r.status_code in {400, 404, 405}, f"{run_id!r} returned {r.status_code}"


def test_get_reactions_private_run_anonymous_404(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "priv", public=False)
    r = client.get("/api/runs/priv/reactions")
    assert r.status_code == 404


def test_get_reactions_public_streams_parquet(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "pub", public=True)
    r = client.get("/api/runs/pub/reactions")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.apache.parquet"
    assert len(r.content) > 0
