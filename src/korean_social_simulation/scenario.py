"""Scenario 입력 모델."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

ScenarioType = Literal["marketing", "social", "product", "policy", "other"]


class Scenario(BaseModel):
    """시뮬레이션 입력 시나리오."""

    title: str = Field(min_length=1, description="짧은 식별자, 파일명 슬러그용")
    stimulus: str = Field(min_length=1, description="페르소나가 노출되는 본문")
    context: str | None = None
    scenario_type: ScenarioType = "other"
    question: str | None = None

    def slug(self) -> str:
        """파일명·디렉터리명에 안전한 슬러그를 생성."""
        s = re.sub(r"[^\w가-힣\- ]+", "", self.title, flags=re.UNICODE)
        s = re.sub(r"\s+", "-", s.strip())
        return s[:64]
