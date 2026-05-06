"""run_id → 안전한 디스크 경로 해석 유틸.

모든 ``/api/runs/{run_id}`` 계열 라우트는 외부 입력을 디렉터리 이름으로 그대로
받기 때문에, ``..`` 등 traversal 문자가 들어오면 ``runs_root`` 밖의 파일을 읽거나
삭제할 위험이 있다. 라우트 별로 검증을 중복 작성하지 않도록 단일 진실원으로
:func:`resolve_run_path` / :data:`RUN_ID_RE` 를 노출한다.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

# Run.create 가 만드는 ID 형식(``YYYYMMDD-HHMMSS-...-slug``) 과 ``uuid.uuid4().hex``
# 둘 다 수용한다. 슬래시·점만으로 이루어진 ``.`` / ``..`` 는 fullmatch 후 별도 거부.
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def resolve_run_path(runs_root: Path, run_id: str) -> Path:
    """``runs_root`` 내부의 정상 run 디렉터리 경로를 안전하게 반환한다.

    Args:
        runs_root: runs 루트 디렉터리 (절대경로 권장).
        run_id: 사용자 입력 run 식별자.

    Returns:
        ``runs_root / run_id`` 의 resolve 결과 — 반드시 ``runs_root`` 하위.

    Raises:
        HTTPException(404): ``run_id`` 가 화이트리스트에 맞지 않거나, 경로가
            ``runs_root`` 외부를 가리키는 경우. 존재 여부를 외부에 노출하지 않도록
            404 로 통일한다 (단 ``DELETE`` 라우트는 기존 호환을 위해 400 도 허용 —
            이 함수는 항상 404 를 던지고, 호출자가 필요하면 400 으로 재포장).
    """
    if not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise HTTPException(status_code=404, detail="run not found")
    runs_root_resolved = runs_root.resolve()
    candidate = (runs_root / run_id).resolve()
    try:
        candidate.relative_to(runs_root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    return candidate
