"""HuggingFace 데이터셋 로딩 — `nvidia/Nemotron-Personas-Korea`."""

from __future__ import annotations

import logging
import os
from typing import Any

from datasets import load_dataset

from korean_social_simulation._version import DATASET_REVISION

logger = logging.getLogger(__name__)


_DATASET_ID = "nvidia/Nemotron-Personas-Korea"


def load_personas(num_proc: int = 8) -> tuple[Any, str]:
    """페르소나 데이터셋을 로드하고 결정적 fingerprint와 함께 반환한다.

    Args:
        num_proc: 로딩 시 사용할 병렬 프로세스 수.

    Returns:
        (train_dataset, fingerprint) 튜플. fingerprint는 datasets 라이브러리가
        제공하는 결정적 해시로, 데이터·전처리·버전이 같으면 동일하게 유지된다.
    """
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    logger.info("Loading dataset %s @ %s", _DATASET_ID, DATASET_REVISION)
    ds = load_dataset(
        _DATASET_ID,
        revision=DATASET_REVISION,
        num_proc=num_proc,
    )
    train = ds["train"]
    return train, train._fingerprint
