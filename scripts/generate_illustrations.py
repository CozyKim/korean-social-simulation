"""랜딩 hero / OG / favicon / 카테고리 아이콘 일괄 생성 (멱등).

Usage:
    uv run --extra image python -m scripts.generate_illustrations
    uv run --extra image python -m scripts.generate_illustrations --force

``python scripts/generate_illustrations.py`` 처럼 직접 실행하면 ``sys.path[0]`` 가
``scripts/`` 가 되어 ``scripts._image_backend`` import 가 실패한다. 항상 ``-m`` 으로 호출.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from scripts._image_backend import ImageBackend, ImageSize, OpenAIImageBackend, to_webp

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "illustrations"

_STYLE_HEADER = "단색 배경, 미니멀 일러스트, 한국적 모티프, 따뜻한 색감, 프리미엄 플랫 디자인, 텍스트 없음. "


@dataclass(frozen=True)
class IllustrationSpec:
    """일러스트 1장의 출력 스펙.

    Attributes:
        name: 논리 이름 (예: ``hero``, ``category-marketing``).
        filename: 저장 파일명 (확장자 포함; ``.webp`` 또는 ``.png``).
        size: ``gpt-image-1`` 가 받는 크기 Literal.
        prompt: 한국어 생성 프롬프트.
    """

    name: str
    filename: str
    size: ImageSize
    prompt: str


ILLUSTRATION_SPECS: tuple[IllustrationSpec, ...] = (
    IllustrationSpec(
        "hero",
        "hero.webp",
        "1536x1024",
        _STYLE_HEADER + "한국인 군중이 거대한 LED 패널을 보고 있는 추상 일러스트, 패널에서 다양한 말풍선이 흘러나옴.",
    ),
    IllustrationSpec(
        "og",
        "og.webp",
        "1536x1024",
        _STYLE_HEADER + "Korean Social Simulation 소셜 카드, 한국 지도 위에 페르소나 아바타 그리드 오버레이.",
    ),
    IllustrationSpec(
        "favicon",
        "favicon.png",
        "256x256",
        _STYLE_HEADER + "흰 배경에 빨간 말풍선 안에 한글 자음 ㅎ, 정사각형 아이콘.",
    ),
    IllustrationSpec(
        "category-marketing",
        "category-marketing.webp",
        "512x512",
        _STYLE_HEADER + "메가폰과 한국 광고지가 어우러진 작은 아이콘.",
    ),
    IllustrationSpec(
        "category-social",
        "category-social.webp",
        "512x512",
        _STYLE_HEADER + "한국 시민 군중과 말풍선 네트워크 아이콘.",
    ),
    IllustrationSpec(
        "category-product",
        "category-product.webp",
        "512x512",
        _STYLE_HEADER + "쇼핑백과 한국 상품 박스가 어우러진 아이콘.",
    ),
    IllustrationSpec(
        "category-policy",
        "category-policy.webp",
        "512x512",
        _STYLE_HEADER + "한국 국회의사당 실루엣과 투표용지 아이콘.",
    ),
    IllustrationSpec(
        "category-other",
        "category-other.webp",
        "512x512",
        _STYLE_HEADER + "물음표와 다양한 말풍선이 어우러진 추상 아이콘.",
    ),
)


@dataclass
class GenerateSummary:
    """생성·스킵 카운트 요약."""

    generated: int
    skipped: int


def run(
    *,
    out_dir: Path,
    backend: ImageBackend,
    force: bool = False,
) -> GenerateSummary:
    """``ILLUSTRATION_SPECS`` 를 순회하며 디스크에 일러스트를 생성.

    Args:
        out_dir: 출력 디렉터리. 없으면 생성.
        backend: ``ImageBackend`` 구현체 (테스트는 MagicMock 주입).
        force: ``True`` 면 기존 파일도 덮어씀.

    Returns:
        생성·스킵 카운트.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    skipped = 0
    for spec in ILLUSTRATION_SPECS:
        target = out_dir / spec.filename
        if target.exists() and not force:
            skipped += 1
            continue
        raw = backend.generate(prompt=spec.prompt, size=spec.size)
        if spec.filename.endswith(".webp") and raw.startswith(b"\x89PNG"):
            raw = to_webp(raw)
        target.write_bytes(raw)
        generated += 1
    return GenerateSummary(generated=generated, skipped=skipped)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    summary = run(out_dir=args.out, backend=OpenAIImageBackend(), force=args.force)
    print(f"illustrations: generated={summary.generated} skipped={summary.skipped}")


if __name__ == "__main__":
    main()
