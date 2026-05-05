"""OpenAI gpt-image-1 호출 + 디스크 IO 추상.

이미지 생성은 외부 호출이라 테스트는 MagicMock으로 backend를 주입한다.
실 호출은 ``run()`` 의 default ``backend=OpenAIImageBackend()`` 경로에서만 사용.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol


class ImageBackend(Protocol):
    def generate(self, *, prompt: str, size: str = "1024x1024") -> bytes:
        """프롬프트 → webp(or png) bytes."""


@dataclass
class OpenAIImageBackend:
    """OpenAI ``gpt-image-1`` 호출. ``OPENAI_API_KEY`` 필수."""

    model: str = "gpt-image-1"
    quality: str = "low"

    def generate(self, *, prompt: str, size: str = "1024x1024") -> bytes:
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
