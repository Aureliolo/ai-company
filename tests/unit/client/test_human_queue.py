"""Unit tests for HumanInputQueue protocol and in-memory impl."""

import asyncio

import pytest

from synthorg.client.human_queue import (
    HumanInputQueue,
    InMemoryHumanInputQueue,
)
from synthorg.client.models import (
    ClientFeedback,
    GenerationContext,
    ReviewContext,
    TaskRequirement,
)

pytestmark = pytest.mark.unit


def _gen_ctx() -> GenerationContext:
    return GenerationContext(
        project_id="proj-1",
        domain="backend",
        count=1,
    )


def _rev_ctx() -> ReviewContext:
    return ReviewContext(
        task_id="task-1",
        task_title="Task",
        deliverable_summary="Deliverable summary",
    )


def _requirement(title: str = "Req") -> TaskRequirement:
    return TaskRequirement(title=title, description="Desc")


def _feedback(*, accepted: bool = True) -> ClientFeedback:
    return ClientFeedback(
        task_id="task-1",
        client_id="client-1",
        accepted=accepted,
        reason=None if accepted else "rejected",
    )


class TestProtocolCompliance:
    def test_in_memory_satisfies_protocol(self) -> None:
        queue = InMemoryHumanInputQueue()
        assert isinstance(queue, HumanInputQueue)


class TestRequirementQueue:
    async def test_enqueue_and_resolve(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_requirement(
            client_id="client-1", context=_gen_ctx()
        )

        async def resolver() -> None:
            await asyncio.sleep(0)
            await queue.resolve_requirement(ticket, _requirement("A"))

        await asyncio.gather(queue.await_requirement(ticket, timeout=1.0), resolver())

    async def test_await_returns_resolved_value(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_requirement(
            client_id="client-1", context=_gen_ctx()
        )

        async def resolver() -> None:
            await queue.resolve_requirement(ticket, _requirement("Done"))

        async def waiter() -> TaskRequirement | None:
            return await queue.await_requirement(ticket, timeout=1.0)

        _, result = await asyncio.gather(resolver(), waiter())
        assert result is not None
        assert result.title == "Done"

    async def test_await_timeout_returns_none(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_requirement(
            client_id="client-1", context=_gen_ctx()
        )
        result = await queue.await_requirement(ticket, timeout=0.01)
        assert result is None

    async def test_resolve_with_none_decline(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_requirement(
            client_id="client-1", context=_gen_ctx()
        )

        async def resolver() -> None:
            await queue.resolve_requirement(ticket, None)

        async def waiter() -> TaskRequirement | None:
            return await queue.await_requirement(ticket, timeout=1.0)

        _, result = await asyncio.gather(resolver(), waiter())
        assert result is None

    async def test_resolve_unknown_ticket_raises(self) -> None:
        queue = InMemoryHumanInputQueue()
        with pytest.raises(KeyError):
            await queue.resolve_requirement("missing", _requirement())

    async def test_await_unknown_ticket_raises(self) -> None:
        queue = InMemoryHumanInputQueue()
        with pytest.raises(KeyError):
            await queue.await_requirement("missing", timeout=0.01)

    async def test_concurrent_tickets_independent(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket_a = await queue.enqueue_requirement(client_id="c1", context=_gen_ctx())
        ticket_b = await queue.enqueue_requirement(client_id="c1", context=_gen_ctx())

        async def resolve_both() -> None:
            await queue.resolve_requirement(ticket_a, _requirement("A"))
            await queue.resolve_requirement(ticket_b, _requirement("B"))

        await resolve_both()
        a = await queue.await_requirement(ticket_a, timeout=0.5)
        b = await queue.await_requirement(ticket_b, timeout=0.5)
        assert a is not None
        assert a.title == "A"
        assert b is not None
        assert b.title == "B"


class TestReviewQueue:
    async def test_enqueue_resolve_and_await(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_review(client_id="client-1", context=_rev_ctx())

        async def resolver() -> None:
            await queue.resolve_review(ticket, _feedback(accepted=True))

        async def waiter() -> ClientFeedback | None:
            return await queue.await_review(ticket, timeout=1.0)

        _, result = await asyncio.gather(resolver(), waiter())
        assert result is not None
        assert result.accepted is True

    async def test_review_timeout_returns_none(self) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_review(client_id="client-1", context=_rev_ctx())
        result = await queue.await_review(ticket, timeout=0.01)
        assert result is None


class TestListing:
    async def test_list_pending(self) -> None:
        queue = InMemoryHumanInputQueue()
        await queue.enqueue_requirement(client_id="c1", context=_gen_ctx())
        await queue.enqueue_requirement(client_id="c2", context=_gen_ctx())
        await queue.enqueue_review(client_id="c1", context=_rev_ctx())

        reqs = await queue.list_pending_requirements()
        reviews = await queue.list_pending_reviews()
        assert len(reqs) == 2
        assert len(reviews) == 1
        assert {r.client_id for r in reqs} == {"c1", "c2"}

    async def test_resolved_tickets_removed_from_pending(
        self,
    ) -> None:
        queue = InMemoryHumanInputQueue()
        ticket = await queue.enqueue_requirement(client_id="c1", context=_gen_ctx())
        await queue.resolve_requirement(ticket, _requirement())
        pending = await queue.list_pending_requirements()
        assert pending == ()
