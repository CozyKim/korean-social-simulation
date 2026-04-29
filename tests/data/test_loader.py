"""data.loader 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from korean_social_simulation._version import DATASET_REVISION
from korean_social_simulation.data.loader import load_personas


def test_load_personas_pins_revision_and_returns_dataset():
    """load_personas는 항상 DATASET_REVISION으로 datasets.load_dataset을 호출한다."""
    fake_dataset = MagicMock()
    fake_dataset._fingerprint = "deadbeef0000"

    with patch("korean_social_simulation.data.loader.load_dataset") as mock_load:
        mock_load.return_value = {"train": fake_dataset}
        ds, fingerprint = load_personas()

    mock_load.assert_called_once()
    _, kwargs = mock_load.call_args
    assert kwargs["revision"] == DATASET_REVISION
    assert kwargs["num_proc"] == 8
    assert ds is fake_dataset
    assert fingerprint == "deadbeef0000"


@pytest.mark.live
def test_load_personas_live_smoke():
    """실제 HF 데이터셋이 로드되는지 검증 (느림)."""
    ds, fingerprint = load_personas()
    assert len(ds) == 1_000_000
    assert "uuid" in ds.features
    assert "persona" in ds.features
    assert isinstance(fingerprint, str) and len(fingerprint) > 0
