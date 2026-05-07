"""238장 한국 페르소나 strata 아바타 생성 (멱등).

기본 backend: codex CLI (ChatGPT 컨슈머 백엔드, OAuth). ``codex login`` 만 필요.
spec §5.3 의 "모두 codex CLI 로 일괄 생성" 정책.

Usage:
    uv run --extra image python -m scripts.generate_avatars
    uv run --extra image python -m scripts.generate_avatars --force
    uv run --extra image python -m scripts.generate_avatars --limit 5  # smoke

``python scripts/generate_avatars.py`` 처럼 직접 실행하면 ``sys.path[0]`` 가
``scripts/`` 가 되어 ``scripts._image_backend`` import 가 실패한다. 항상 ``-m`` 으로 호출.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from korean_social_simulation.data.sampler import _AGE_BANDS
from scripts._image_backend import CodexImageBackend, ImageBackend, to_webp

AVATAR_SEXES: tuple[str, ...] = ("female", "male")

AVATAR_PROVINCES: tuple[str, ...] = (
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
)

# ``_AGE_BANDS`` 는 ``[(upper_bound, label), ...]`` 형태이므로 라벨만 추출해 사용.
_AGE_BAND_LABELS: tuple[str, ...] = tuple(label for _, label in _AGE_BANDS)

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "avatars"

_AGE_BAND_DESC = {
    "~19": "10대 후반",
    "20s": "20대",
    "30s": "30대",
    "40s": "40대",
    "50s": "50대",
    "60s": "60대",
    "70+": "70대 이상",
}

_SEX_DESC = {"female": "여성", "male": "남성"}


def iter_avatar_keys() -> Iterator[str]:
    """{sex}_{age_band}_{province} 형식 strata 키를 결정적 순서로 yield."""
    for sex in AVATAR_SEXES:
        for age_band in _AGE_BAND_LABELS:
            for province in AVATAR_PROVINCES:
                yield f"{sex}_{age_band}_{province}"


def _prompt_for(key: str) -> str:
    sex, age_band, province = key.split("_", 2)
    return f"한국인 {_SEX_DESC[sex]}, {_AGE_BAND_DESC[age_band]}, {province} 거주, 사실적 클로즈업 초상화, 중립 표정, 단색 배경, 스튜디오 조명, 자연스러운 의복, 정면 응시"


@dataclass
class GenerateSummary:
    generated: int
    skipped: int


def run(
    *,
    out_dir: Path,
    backend: ImageBackend,
    force: bool = False,
    limit: int | None = None,
) -> GenerateSummary:
    """strata × 아바타 매트릭스를 디스크에 생성. ``limit`` 지정 시 앞에서 N개만.

    한 strata 의 backend.generate 가 fail (timeout, API error 등) 해도 stderr 에 로그하고
    다음 strata 로 진행 — 단일 fail 이 전체 batch 를 막지 않도록.
    """
    import sys

    out_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    skipped = 0
    failed = 0
    consecutive_fails = 0
    MAX_CONSECUTIVE_FAILS = 5
    for key in iter_avatar_keys():
        # ``limit`` 은 "시도 카운트" 로 해석 — generated+failed 합산 시 limit 도달이면 종료.
        # (rate limit / 토큰 소진 시 모든 strata 가 fail 인 상태에서 무한 반복 회피.)
        if limit is not None and (generated + failed) >= limit:
            break
        if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            print(
                f"[abort] {consecutive_fails} 연속 fail — codex usage limit / rate limit 의심. 중단.",
                file=sys.stderr,
            )
            break
        target = out_dir / f"{key}.webp"
        if target.exists() and not force:
            skipped += 1
            continue
        try:
            raw = backend.generate(prompt=_prompt_for(key), size="1024x1024")
        except Exception as exc:  # noqa: BLE001 — single-strata fail isolation
            failed += 1
            consecutive_fails += 1
            print(f"[skip] {key}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if raw.startswith(b"\x89PNG"):
            raw = to_webp(raw)
        target.write_bytes(raw)
        generated += 1
        consecutive_fails = 0
    if failed:
        print(f"[summary] generated={generated} skipped={skipped} failed={failed}", file=sys.stderr)
    return GenerateSummary(generated=generated, skipped=skipped)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    backend = CodexImageBackend()
    summary = run(out_dir=args.out, backend=backend, force=args.force, limit=args.limit)
    print(f"avatars: generated={summary.generated} skipped={summary.skipped}")


if __name__ == "__main__":
    main()
