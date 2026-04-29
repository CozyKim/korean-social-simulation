"""공통 pytest fixtures."""

import pytest


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    """테스트 격리용 임시 캐시 디렉터리."""
    cache = tmp_path / ".cache" / "korean_social_simulation"
    cache.mkdir(parents=True)
    monkeypatch.setenv("KSS_CACHE_DIR", str(cache))
    return cache
