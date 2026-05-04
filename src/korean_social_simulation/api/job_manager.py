"""In-memory JobManager — POST /api/runs 즉시 응답 + SSE fan-out.

단일 인스턴스 가정. 백엔드 재시작 시 모든 jobs 사라짐 (interrupted partial 디렉터리만
디스크에 남음).
"""

from __future__ import annotations

import asyncio
import enum
from collections import deque
from dataclasses import dataclass, field
from typing import Any

_EVENTS_MAX = 1000  # backfill용 deque 한도


class JobStatus(enum.Enum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobState:
    run_id: str
    status: JobStatus = JobStatus.STARTING
    progress: int = 0
    total: int = 0
    next_event_id: int = 1
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=_EVENTS_MAX))
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)


class JobManager:
    """단일 인스턴스 in-memory job registry."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def register(self, run_id: str, *, total: int = 0) -> JobState:
        if run_id in self._jobs:
            raise ValueError(f"run_id already registered: {run_id}")
        state = JobState(run_id=run_id, total=total)
        self._jobs[run_id] = state
        return state

    def get(self, run_id: str) -> JobState | None:
        return self._jobs.get(run_id)

    def is_active(self, run_id: str) -> bool:
        s = self._jobs.get(run_id)
        return s is not None and s.status in {JobStatus.STARTING, JobStatus.RUNNING}

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """페르소나 결과 등 단일 이벤트를 모든 subscribers에 fan-out."""
        state = self._jobs.get(run_id)
        if state is None:
            return
        if state.status == JobStatus.STARTING:
            state.status = JobStatus.RUNNING
        eid = state.next_event_id
        state.next_event_id += 1
        enriched = {**event, "event_id": eid}
        state.events.append(enriched)
        if event.get("type") == "persona_done":
            state.progress += 1
        for q in list(state.subscribers):
            await q.put(enriched)

    async def complete(self, run_id: str, payload: dict[str, Any] | None = None) -> None:
        state = self._jobs.get(run_id)
        if state is None:
            return
        state.status = JobStatus.COMPLETED
        eid = state.next_event_id
        state.next_event_id += 1
        evt = {"type": "completed", "event_id": eid, **(payload or {})}
        state.events.append(evt)
        for q in list(state.subscribers):
            await q.put(evt)

    async def fail(self, run_id: str, *, error: str) -> None:
        state = self._jobs.get(run_id)
        if state is None:
            return
        state.status = JobStatus.FAILED
        eid = state.next_event_id
        state.next_event_id += 1
        evt = {"type": "error", "event_id": eid, "error": error}
        state.events.append(evt)
        for q in list(state.subscribers):
            await q.put(evt)

    def subscribe(
        self,
        run_id: str,
        *,
        last_event_id: int | None = None,
    ) -> asyncio.Queue[dict[str, Any]]:
        """새 큐를 만들어 subscribers에 등록.

        ``last_event_id`` 가 있으면 그 이후 이벤트를 backfill로 큐에 넣어 둔다.
        """
        state = self._jobs.get(run_id)
        if state is None:
            raise KeyError(run_id)
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        if last_event_id is not None:
            for evt in state.events:
                if evt["event_id"] > last_event_id:
                    q.put_nowait(evt)
        state.subscribers.add(q)
        return q

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        state = self._jobs.get(run_id)
        if state is None:
            return
        state.subscribers.discard(queue)

    def active_count(self) -> int:
        return sum(1 for s in self._jobs.values() if self.is_active(s.run_id))
