"""POST /api/runs 즉시 응답 + 백그라운드 시뮬 진행."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def test_post_runs_requires_login(client: TestClient) -> None:
    r = client.post(
        "/api/runs",
        json={
            "scenario_title": "t",
            "scenario_stimulus": "s",
            "n": 2,
            "model": "vllm-qwen",
        },
    )
    assert r.status_code == 401


def test_post_runs_returns_run_id_immediately(monkeypatch, client: TestClient) -> None:
    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={
                "scenario_title": "t",
                "scenario_stimulus": "s",
                "n": 2,
                "model": "vllm-qwen",
            },
        )
    assert r.status_code == 202
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "starting"
