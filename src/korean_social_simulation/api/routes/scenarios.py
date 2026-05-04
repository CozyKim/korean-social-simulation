"""Scenarios — scenarios/ 디렉터리의 YAML 파일."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from korean_social_simulation.api.deps import SettingsDep

router = APIRouter(prefix="/api", tags=["scenarios"])


def _safe_join(root: Path, name: str) -> Path | None:
    """경로 traversal 방지 — root 밖이면 None.

    Args:
        root: 허용할 기준 디렉터리 (절대 경로로 resolve됨).
        name: 클라이언트가 요청한 파일명 (URL 디코딩 후 문자열).

    Returns:
        파일이 root 내에 있고 실제 존재하면 Path, 아니면 None.
    """
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


@router.get("/scenarios")
def list_scenarios(settings: SettingsDep) -> list[dict]:
    """scenarios_root 내 YAML 파일 목록 반환.

    Args:
        settings: 앱 설정 (scenarios_root 포함).

    Returns:
        각 파일의 filename, title, scenario_type 딕셔너리 목록.
    """
    root = settings.scenarios_root
    if not root.exists():
        return []
    out: list[dict] = []
    for p in sorted(root.iterdir()):
        if p.suffix in {".yaml", ".yml"}:
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            out.append(
                {
                    "filename": p.name,
                    "title": data.get("title", p.stem),
                    "scenario_type": data.get("scenario_type", "other"),
                }
            )
    return out


@router.get("/scenarios/{name}")
def get_scenario(name: str, settings: SettingsDep) -> dict:
    """단일 시나리오 YAML 전체 반환.

    Args:
        name: 요청한 파일명 (예: ``ramen.yaml``).
        settings: 앱 설정 (scenarios_root 포함).

    Returns:
        YAML 파싱 결과 딕셔너리.

    Raises:
        HTTPException: 파일이 root 밖이거나, 없거나, yaml/yml 확장자가 아닐 때 404.
    """
    p = _safe_join(settings.scenarios_root, name)
    if p is None or p.suffix not in {".yaml", ".yml"}:
        raise HTTPException(status_code=404)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data
