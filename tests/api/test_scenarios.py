"""Scenarios 목록 — scenarios/ 디렉터리의 YAML 파일을 노출."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_list_scenarios(settings_env: Path, client: TestClient) -> None:
    sc_root = settings_env / "scenarios"
    (sc_root / "ramen.yaml").write_text(
        """title: "라면 광고"
stimulus: "신라면 신제품"
scenario_type: marketing
""",
        encoding="utf-8",
    )
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    items = r.json()
    assert any(item["filename"] == "ramen.yaml" for item in items)


def test_get_scenario_returns_full(settings_env: Path, client: TestClient) -> None:
    sc_root = settings_env / "scenarios"
    (sc_root / "ramen.yaml").write_text(
        """title: "라면 광고"
stimulus: "신라면"
scenario_type: marketing
""",
        encoding="utf-8",
    )
    r = client.get("/api/scenarios/ramen.yaml")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "라면 광고"


def test_get_scenario_path_traversal_404(settings_env: Path, client: TestClient) -> None:
    r = client.get("/api/scenarios/..%2Fetc%2Fpasswd")
    assert r.status_code == 404
