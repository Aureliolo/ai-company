"""Unit tests for FeedbackStore, RequestStore, and SimulationStore."""

import asyncio

import pytest

from synthorg.client.models import (
    ClientFeedback,
    ClientRequest,
    SimulationConfig,
    SimulationMetrics,
    TaskRequirement,
)
from synthorg.client.store import (
    FeedbackStore,
    RequestStore,
    SimulationRecord,
    SimulationStore,
)


def _requirement() -> TaskRequirement:
    return TaskRequirement(title="Test", description="Test desc")


def _request(client_id: str = "c-1") -> ClientRequest:
    return ClientRequest(client_id=client_id, requirement=_requirement())


def _feedback(
    client_id: str = "c-1",
    task_id: str = "t-1",
    *,
    accepted: bool = True,
) -> ClientFeedback:
    if accepted:
        return ClientFeedback(
            client_id=client_id,
            task_id=task_id,
            accepted=True,
        )
    return ClientFeedback(
        client_id=client_id,
        task_id=task_id,
        accepted=False,
        reason="not good enough",
    )


def _sim_config() -> SimulationConfig:
    return SimulationConfig(project_id="proj-1")


@pytest.mark.unit
class TestRequestStore:
    async def test_save_and_get(self) -> None:
        store = RequestStore()
        req = _request()
        await store.save(req)
        got = await store.get(req.request_id)
        assert got.request_id == req.request_id

    async def test_get_missing_raises_keyerror(self) -> None:
        store = RequestStore()
        with pytest.raises(KeyError, match="not found"):
            await store.get("missing")

    async def test_list_all(self) -> None:
        store = RequestStore()
        r1 = _request("a")
        r2 = _request("b")
        await store.save(r1)
        await store.save(r2)
        all_reqs = await store.list_all()
        assert len(all_reqs) == 2

    async def test_delete(self) -> None:
        store = RequestStore()
        req = _request()
        await store.save(req)
        await store.delete(req.request_id)
        with pytest.raises(KeyError):
            await store.get(req.request_id)

    async def test_delete_missing_is_noop(self) -> None:
        store = RequestStore()
        await store.delete("missing")

    async def test_concurrent_saves(self) -> None:
        store = RequestStore()
        reqs = [_request(f"c{i}") for i in range(10)]
        await asyncio.gather(*(store.save(r) for r in reqs))
        assert len(await store.list_all()) == 10


@pytest.mark.unit
class TestFeedbackStore:
    async def test_record_and_list(self) -> None:
        store = FeedbackStore()
        fb = _feedback()
        await store.record(fb)
        entries = await store.list_for_client("c-1")
        assert len(entries) == 1
        assert entries[0].task_id == "t-1"

    async def test_list_empty_client(self) -> None:
        store = FeedbackStore()
        assert await store.list_for_client("unknown") == ()

    async def test_clear(self) -> None:
        store = FeedbackStore()
        await store.record(_feedback())
        await store.clear("c-1")
        assert await store.list_for_client("c-1") == ()

    async def test_concurrent_records(self) -> None:
        store = FeedbackStore()
        fbs = [_feedback(task_id=f"t-{i}") for i in range(5)]
        await asyncio.gather(*(store.record(fb) for fb in fbs))
        assert len(await store.list_for_client("c-1")) == 5


@pytest.mark.unit
class TestSimulationStore:
    async def test_save_and_get(self) -> None:
        store = SimulationStore()
        record = SimulationRecord(
            simulation_id="sim-1",
            config=_sim_config(),
        )
        await store.save(record)
        got = await store.get("sim-1")
        assert got.simulation_id == "sim-1"
        assert got.status == "pending"

    async def test_get_missing_raises_keyerror(self) -> None:
        store = SimulationStore()
        with pytest.raises(KeyError, match="not found"):
            await store.get("missing")

    async def test_update_status_returns_new_record(self) -> None:
        store = SimulationStore()
        record = SimulationRecord(
            simulation_id="sim-2",
            config=_sim_config(),
        )
        await store.save(record)
        updated = await store.update_status(
            "sim-2",
            status="running",
        )
        assert updated.status == "running"
        assert updated.started_at is not None

    async def test_update_completed_sets_timestamp(self) -> None:
        store = SimulationStore()
        record = SimulationRecord(
            simulation_id="sim-3",
            config=_sim_config(),
            status="running",
        )
        await store.save(record)
        updated = await store.update_status(
            "sim-3",
            status="completed",
            metrics=SimulationMetrics(total_tasks_created=5),
            progress=1.0,
        )
        assert updated.completed_at is not None
        assert updated.metrics.total_tasks_created == 5
        assert updated.progress == 1.0

    async def test_update_preserves_identity(self) -> None:
        store = SimulationStore()
        record = SimulationRecord(
            simulation_id="sim-4",
            config=_sim_config(),
        )
        await store.save(record)
        updated = await store.update_status("sim-4", status="failed", error="oops")
        assert updated.simulation_id == "sim-4"
        assert updated.error == "oops"

    async def test_list_all(self) -> None:
        store = SimulationStore()
        for i in range(3):
            await store.save(
                SimulationRecord(
                    simulation_id=f"sim-{i}",
                    config=_sim_config(),
                ),
            )
        assert len(await store.list_all()) == 3
