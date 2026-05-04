"""JobManager 단위 테스트 — fan-out, replay, last-event-id."""

from __future__ import annotations

import asyncio


async def test_register_and_publish_fans_out_to_subscribers() -> None:
    from korean_social_simulation.api.job_manager import JobManager

    jm = JobManager()
    jm.register("rid")
    q1 = jm.subscribe("rid")
    q2 = jm.subscribe("rid")

    await jm.publish("rid", {"type": "persona_done", "index": 0})

    e1 = await asyncio.wait_for(q1.get(), timeout=1)
    e2 = await asyncio.wait_for(q2.get(), timeout=1)
    assert e1["index"] == 0 == e2["index"]
    assert e1["event_id"] == 1 == e2["event_id"]


async def test_subscribe_with_last_event_id_backfills() -> None:
    from korean_social_simulation.api.job_manager import JobManager

    jm = JobManager()
    jm.register("rid")
    await jm.publish("rid", {"type": "persona_done", "index": 0})
    await jm.publish("rid", {"type": "persona_done", "index": 1})
    await jm.publish("rid", {"type": "persona_done", "index": 2})

    q = jm.subscribe("rid", last_event_id=1)
    e1 = await asyncio.wait_for(q.get(), timeout=1)
    e2 = await asyncio.wait_for(q.get(), timeout=1)
    assert e1["event_id"] == 2
    assert e2["event_id"] == 3


async def test_complete_publishes_done_marker_and_status() -> None:
    from korean_social_simulation.api.job_manager import JobManager, JobStatus

    jm = JobManager()
    jm.register("rid")
    q = jm.subscribe("rid")
    await jm.complete("rid")
    e = await asyncio.wait_for(q.get(), timeout=1)
    assert e["type"] == "completed"
    assert jm.get("rid").status == JobStatus.COMPLETED


async def test_fail_publishes_error_marker() -> None:
    from korean_social_simulation.api.job_manager import JobManager, JobStatus

    jm = JobManager()
    jm.register("rid")
    q = jm.subscribe("rid")
    await jm.fail("rid", error="boom")
    e = await asyncio.wait_for(q.get(), timeout=1)
    assert e["type"] == "error"
    assert "boom" in e["error"]
    assert jm.get("rid").status == JobStatus.FAILED


async def test_unsubscribe_drops_queue() -> None:
    from korean_social_simulation.api.job_manager import JobManager

    jm = JobManager()
    jm.register("rid")
    q = jm.subscribe("rid")
    jm.unsubscribe("rid", q)
    await jm.publish("rid", {"type": "persona_done"})
    assert q.empty()
