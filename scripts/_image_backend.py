"""OpenAI gpt-image-1 호출 + 디스크 IO 추상.

이미지 생성은 외부 호출이라 테스트는 MagicMock으로 backend를 주입한다.
실 호출은 ``run()`` 의 default ``backend=OpenAIImageBackend()`` 경로에서만 사용.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Literal, Protocol

ImageSize = Literal[
    "auto",
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "256x256",
    "512x512",
    "1792x1024",
    "1024x1792",
]
ImageQuality = Literal["standard", "hd", "low", "medium", "high", "auto"]


class ImageBackend(Protocol):
    def generate(self, *, prompt: str, size: ImageSize = "1024x1024") -> bytes:
        """프롬프트 → webp(or png) bytes."""
        ...


@dataclass
class OpenAIImageBackend:
    """OpenAI ``gpt-image-1`` 호출. ``OPENAI_API_KEY`` 필수."""

    model: str = "gpt-image-1"
    quality: ImageQuality = "low"

    def generate(self, *, prompt: str, size: ImageSize = "1024x1024") -> bytes:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 가 설정되어 있지 않습니다.")

        client = OpenAI(api_key=api_key)
        result = client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            quality=self.quality,
            n=1,
        )
        if not result.data:
            raise RuntimeError("OpenAI 응답에 data 가 없습니다.")
        b64 = result.data[0].b64_json
        if not b64:
            raise RuntimeError("OpenAI 응답에 b64_json 가 없습니다.")
        return base64.b64decode(b64)


def to_webp(png_bytes: bytes, *, quality: int = 80) -> bytes:
    """PNG → WebP 변환. Pillow 필요."""
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    out = BytesIO()
    img.save(out, format="WEBP", quality=quality)
    return out.getvalue()


def resize_image(raw: bytes, target: tuple[int, int], *, quality: int = 80) -> bytes:
    """이미지 bytes 를 ``target`` 크기로 리사이즈. 입력 형식(PNG/WebP)을 보존.

    gpt-image-1 은 256/512 같은 작은 크기를 직접 지원하지 않으므로, 1024×1024 결과를
    받아 로컬에서 다운스케일할 때 사용. LANCZOS 가 다운스케일에 적합.

    Args:
        raw: 입력 이미지 bytes (PNG 또는 WebP).
        target: 출력 크기 ``(width, height)``.
        quality: WebP 인코딩 품질 (PNG 는 무손실이라 무시).

    Returns:
        리사이즈된 이미지 bytes — 입력과 동일 형식 (PNG → PNG, WebP → WebP).
    """
    from io import BytesIO

    from PIL import Image

    src = Image.open(BytesIO(raw))
    fmt = src.format or "PNG"
    resized = src.convert("RGB").resize(target, Image.Resampling.LANCZOS)
    out = BytesIO()
    if fmt.upper() == "WEBP":
        resized.save(out, format="WEBP", quality=quality)
    else:
        resized.save(out, format="PNG")
    return out.getvalue()
