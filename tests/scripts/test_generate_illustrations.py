"""generate_illustrations.py 명세 매핑 + 멱등 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from scripts.generate_illustrations import (
    ILLUSTRATION_SPECS,
)
from scripts.generate_illustrations import (
    run as generate_run,
)


def test_specs_cover_required_assets() -> None:
    names = {s.name for s in ILLUSTRATION_SPECS}
    assert {"hero", "og", "favicon"}.issubset(names)
    assert {
        "category-marketing",
        "category-social",
        "category-product",
        "category-policy",
        "category-other",
    }.issubset(names)


def test_run_skips_existing(tmp_path: Path) -> None:
    out_dir = tmp_path
    spec0 = ILLUSTRATION_SPECS[0]
    (out_dir / spec0.filename).write_bytes(b"existing")

    backend = MagicMock()
    backend.generate.return_value = b"new"

    summary = generate_run(out_dir=out_dir, backend=backend, force=False)

    assert summary.skipped == 1
    assert summary.generated == len(ILLUSTRATION_SPECS) - 1


def test_run_force_overwrites(tmp_path: Path) -> None:
    out_dir = tmp_path
    spec0 = ILLUSTRATION_SPECS[0]
    (out_dir / spec0.filename).write_bytes(b"existing")

    backend = MagicMock()
    backend.generate.return_value = b"new"

    summary = generate_run(out_dir=out_dir, backend=backend, force=True)
    assert summary.generated == len(ILLUSTRATION_SPECS)
