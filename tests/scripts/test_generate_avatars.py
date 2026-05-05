"""generate_avatars.py 의 strata 매트릭스 + 멱등 동작 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from korean_social_simulation.data.sampler import _AGE_BANDS
from scripts.generate_avatars import (
    AVATAR_PROVINCES,
    AVATAR_SEXES,
    iter_avatar_keys,
)
from scripts.generate_avatars import (
    run as generate_run,
)


def test_iter_avatar_keys_covers_full_matrix() -> None:
    keys = list(iter_avatar_keys())
    assert len(keys) == len(AVATAR_SEXES) * len(_AGE_BANDS) * len(AVATAR_PROVINCES)
    sample = keys[0]
    assert sample.count("_") == 2
    assert sample.split("_")[0] in AVATAR_SEXES


def test_run_skips_existing_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "avatars"
    out_dir.mkdir()
    first_key = next(iter_avatar_keys())
    (out_dir / f"{first_key}.webp").write_bytes(b"existing")

    backend = MagicMock()
    backend.generate.return_value = b"new-image-bytes"

    summary = generate_run(out_dir=out_dir, backend=backend, force=False)

    assert summary.skipped == 1
    assert summary.generated == len(list(iter_avatar_keys())) - 1
    assert (out_dir / f"{first_key}.webp").read_bytes() == b"existing"


def test_run_force_regenerates(tmp_path: Path) -> None:
    out_dir = tmp_path / "avatars"
    out_dir.mkdir()
    first_key = next(iter_avatar_keys())
    (out_dir / f"{first_key}.webp").write_bytes(b"existing")

    backend = MagicMock()
    backend.generate.return_value = b"forced-image"

    summary = generate_run(out_dir=out_dir, backend=backend, force=True)

    assert summary.skipped == 0
    assert summary.generated == len(list(iter_avatar_keys()))
    assert (out_dir / f"{first_key}.webp").read_bytes() == b"forced-image"


@pytest.mark.parametrize("limit", [1, 5])
def test_run_respects_limit(tmp_path: Path, limit: int) -> None:
    out_dir = tmp_path / "avatars"
    out_dir.mkdir()
    backend = MagicMock()
    backend.generate.return_value = b"img"

    summary = generate_run(out_dir=out_dir, backend=backend, force=False, limit=limit)

    assert summary.generated == limit
