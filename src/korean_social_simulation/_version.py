"""중앙 버전 상수 — 샘플 캐시 invalidation에 사용."""

# nvidia/Nemotron-Personas-Korea 의 검증된 revision (커밋 SHA 또는 태그).
# HF 측에서 데이터가 갱신되어도 우리 시뮬은 결정적으로 같은 행을 본다.
# 실제 SHA는 구현 시 `huggingface_hub.HfApi().dataset_info(...).sha` 로 확인 후 기재.
DATASET_REVISION: str = "main"  # TODO(Task 2): 실제 SHA로 교체

# 샘플링 알고리즘 또는 strata 스키마 변경 시 bump.
# bump 하면 기존 샘플 캐시는 자동으로 무효화된다.
SAMPLER_VERSION: str = "1"
