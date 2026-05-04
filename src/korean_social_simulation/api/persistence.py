"""runs/<id>/ 디스크 IO 헬퍼."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path


def list_run_dirs(runs_root: Path) -> Iterator[Path]:
    if not runs_root.exists():
        return
    for child in sorted(runs_root.iterdir()):
        if (child / "scenario.json").exists():
            yield child


def load_run_meta(run_path: Path) -> dict | None:
    meta_path = run_path / "scenario.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_run_meta(run_path: Path, data: dict) -> None:
    (run_path / "scenario.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def to_summary(meta: dict) -> dict:
    return {
        "run_id": meta.get("run_id"),
        "title": meta["scenario"]["title"],
        "model": meta["meta"].get("model"),
        "n": meta["meta"].get("n"),
        "status": meta.get("status", "completed"),
        "public": meta.get("public", False),
        "created_at": meta.get("created_at", ""),
    }
