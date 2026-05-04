"""In-memory sliding window rate limiter — 단일 인스턴스 가정."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    """(scope, key) 별로 마지막 N초 안의 호출 수를 센다.

    재시작 시 카운터는 초기화된다 (단일 인스턴스 운영의 trade-off).
    Thread-safe — 단일 worker 내 여러 코루틴/스레드에서 안전하게 호출 가능.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, scope: str, key: str, *, max_per_window: int, window_s: float) -> bool:
        """1회 사용 등록. 한도 초과면 False (거부), 통과면 True.

        Args:
            scope: 'auth_login', 'try_run' 등 정책 식별자.
            key: 보통 IP 주소.
            max_per_window: 윈도 안의 허용 호출 수.
            window_s: 윈도 길이 (초).
        """
        now = time.monotonic()
        threshold = now - window_s
        with self._lock:
            bucket = self._buckets[(scope, key)]
            while bucket and bucket[0] < threshold:
                bucket.popleft()
            if len(bucket) >= max_per_window:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """테스트용 — 모든 카운터 초기화."""
        with self._lock:
            self._buckets.clear()


_global = SlidingWindowLimiter()


def get_limiter() -> SlidingWindowLimiter:
    return _global
