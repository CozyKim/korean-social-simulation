"""generate_illustrations.py 명세 매핑 + 멱등 테스트."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from scripts.generate_illustrations import (
    ILLUSTRATION_SPECS,
)
from scripts.generate_illustrations import (
    run as generate_run,
)


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """주어진 크기의 단색 PNG bytes 생성 — 백엔드 mock 의 리턴값으로 사용."""
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


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


def test_specs_use_only_supported_api_sizes() -> None:
    """gpt-image-1 은 ``auto`` / ``1024x1024`` / ``1536x1024`` / ``1024x1536`` 만 지원.

    ``256x256``, ``512x512`` 같은 legacy DALL-E 크기를 사용하면 API 가 400 을 반환한다.
    favicon (256), category 5종 (512) 은 API 결과를 디스크에 쓰기 전 ``final_size`` 로
    리사이즈해야 한다.
    """
    supported_api_sizes = {"auto", "1024x1024", "1536x1024", "1024x1536"}
    for spec in ILLUSTRATION_SPECS:
        assert spec.size in supported_api_sizes, f"{spec.name}: {spec.size} not supported by gpt-image-1"


def test_favicon_and_category_specs_have_final_size() -> None:
    """favicon (256×256) + category 5종 (512×512) 은 ``final_size`` 가 지정돼 있어야 한다."""
    by_name = {s.name: s for s in ILLUSTRATION_SPECS}
    assert by_name["favicon"].final_size == (256, 256)
    for cat in ("marketing", "social", "product", "policy", "other"):
        assert by_name[f"category-{cat}"].final_size == (512, 512)
    # hero/og 는 API 크기 그대로 (1536×1024 그대로 저장)
    assert by_name["hero"].final_size is None
    assert by_name["og"].final_size is None


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


def test_run_calls_backend_with_supported_api_size_and_resizes_to_final(tmp_path: Path) -> None:
    """백엔드는 1024×1024 PNG 를 리턴 — favicon/category 는 디스크에 final_size 로 저장돼야 한다."""
    out_dir = tmp_path
    backend = MagicMock()
    backend.generate.return_value = _png_bytes((1024, 1024))

    generate_run(out_dir=out_dir, backend=backend, force=False)

    # 모든 backend.generate 호출의 size 인자는 gpt-image-1 지원 크기여야 함
    supported_api_sizes = {"auto", "1024x1024", "1536x1024", "1024x1536"}
    for call in backend.generate.call_args_list:
        size = call.kwargs.get("size")
        assert size in supported_api_sizes, f"unsupported size passed to backend: {size}"

    # favicon 디스크 파일은 256×256
    favicon = Image.open(out_dir / "favicon.png")
    assert favicon.size == (256, 256)

    # category-marketing 디스크 파일은 512×512 (WebP)
    for cat in ("marketing", "social", "product", "policy", "other"):
        img = Image.open(out_dir / f"category-{cat}.webp")
        assert img.size == (512, 512), f"category-{cat}: {img.size}"

    # hero/og 는 1024×1024 mock 입력 → final_size 미지정이므로 그대로 1024×1024
    hero = Image.open(out_dir / "hero.webp")
    assert hero.size == (1024, 1024)


def test_resize_image_preserves_format() -> None:
    """resize_image 헬퍼: PNG → PNG, WebP → WebP 형식 보존 + 정확한 출력 크기."""
    from scripts._image_backend import resize_image

    # PNG 입력
    src_png = _png_bytes((1024, 1024))
    out_png = resize_image(src_png, (256, 256))
    assert out_png.startswith(b"\x89PNG"), "PNG signature lost"
    img = Image.open(BytesIO(out_png))
    assert img.size == (256, 256)
    assert img.format == "PNG"

    # WebP 입력
    buf = BytesIO()
    Image.new("RGB", (1024, 1024), (0, 255, 0)).save(buf, format="WEBP")
    out_webp = resize_image(buf.getvalue(), (512, 512))
    img2 = Image.open(BytesIO(out_webp))
    assert img2.size == (512, 512)
    assert img2.format == "WEBP"
