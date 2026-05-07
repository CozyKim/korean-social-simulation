"""이미지 생성 backend 추상 + 디스크 IO.

두 backend 제공:
- :class:`CodexImageBackend` — codex CLI (ChatGPT 컨슈머 백엔드, OAuth) 사용. **기본**.
  spec §5.3 의 "모두 codex CLI 로 일괄 생성" 정책에 부합. ``codex login`` 만 필요.
- :class:`OpenAIImageBackend` — OpenAI public API ``gpt-image-1``. ``OPENAI_API_KEY`` 필요.
  대안.

테스트는 MagicMock 으로 backend 를 주입한다 — 실 호출은 default 경로에서만.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
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
class CodexImageBackend:
    """``codex exec`` subprocess 호출로 ChatGPT 컨슈머 백엔드의 image_gen tool 사용.

    spec §5.3 의 기본 backend. ``codex login`` 으로 OAuth 토큰을 한 번 발급해 두면
    추가 환경변수 없이 동작. 한 장당 약 30~60초 소요 (GPT-image 호출 + sips 리사이즈).

    내부 동작:
    1. 임시 디렉터리에 ``out.png`` 경로 지정.
    2. codex 에이전트에게 PNG 이미지를 ``out.png`` 로 저장하고 정확한 ``size`` 로 리사이즈
       (``sips`` 사용) 후 종료하라고 지시.
    3. ``codex exec`` 종료 후 파일 read → bytes 반환.

    Attributes:
        codex_bin: codex CLI 실행 파일 경로 (기본 ``codex`` — PATH 검색).
        timeout_s: 한 장당 최대 대기 시간. 기본 240초.
    """

    codex_bin: str = "codex"
    timeout_s: int = 360

    def generate(self, *, prompt: str, size: ImageSize = "1024x1024") -> bytes:
        if not shutil.which(self.codex_bin):
            raise RuntimeError(f"codex CLI 를 찾을 수 없습니다 (PATH 에 {self.codex_bin} 없음). https://github.com/openai/codex 참고.")

        with tempfile.TemporaryDirectory(prefix="kss-codex-img-") as tmp:
            tmp_dir = Path(tmp)
            out_path = tmp_dir / "out.png"
            instruction = (
                f"PNG 이미지를 한 장 만들어 ./out.png 경로에 저장해 주세요. "
                f"이미지 내용: {prompt} "
                f"최종 파일은 정확히 {size} 픽셀이어야 합니다. "
                f"필요하면 sips 로 리사이즈한 뒤 'DONE: out.png' 한 줄만 출력하고 종료하세요."
            )
            cmd = [
                self.codex_bin,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                instruction,
            ]
            try:
                proc = subprocess.run(  # noqa: S603
                    cmd,
                    cwd=tmp_dir,
                    capture_output=True,
                    timeout=self.timeout_s,
                    check=False,
                    text=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"codex exec 타임아웃 ({self.timeout_s}s)") from exc

            if proc.returncode != 0:
                raise RuntimeError(f"codex exec 실패 (exit {proc.returncode}). stderr tail: {proc.stderr[-500:] if proc.stderr else '(empty)'}")
            if not out_path.exists():
                raise RuntimeError(f"codex 가 out.png 를 만들지 않음. stdout tail: {proc.stdout[-500:]}")
            return out_path.read_bytes()


@dataclass
class OpenAIImageBackend:
    """OpenAI ``gpt-image-1`` 호출. ``OPENAI_API_KEY`` 필수. CodexImageBackend 의 대안."""

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
