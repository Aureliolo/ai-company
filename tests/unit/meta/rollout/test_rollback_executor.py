"""Tests for the dispatcher-based RollbackExecutor."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import (
    ConfigChange,
    ImprovementProposal,
    ProposalAltitude,
    ProposalRationale,
    RollbackOperation,
    RollbackPlan,
)
from synthorg.meta.rollout.inverse_dispatch import (
    RollbackHandler,
    UnknownRollbackOperationError,
)
from synthorg.meta.rollout.rollback import RollbackExecutor

pytestmark = pytest.mark.unit


class _CountingHandler:
    def __init__(self, *, returns: int = 1, fail: bool = False) -> None:
        self._returns = returns
        self._fail = fail
        self.calls: list[RollbackOperation] = []

    async def revert(self, operation: RollbackOperation) -> int:
        self.calls.append(operation)
        if self._fail:
            msg = "boom"
            raise RuntimeError(msg)
        return self._returns


def _operation(op_type: str = "revert_config") -> RollbackOperation:
    return RollbackOperation(
        operation_type=NotBlankStr(op_type),
        target=NotBlankStr("a.b"),
        previous_value=1,
        description=NotBlankStr("revert a.b"),
    )


def _proposal(*operations: RollbackOperation) -> ImprovementProposal:
    ops = operations or (_operation(),)
    return ImprovementProposal(
        altitude=ProposalAltitude.CONFIG_TUNING,
        title=NotBlankStr("test"),
        description=NotBlankStr("test"),
        rationale=ProposalRationale(
            signal_summary=NotBlankStr("x"),
            pattern_detected=NotBlankStr("x"),
            expected_impact=NotBlankStr("x"),
            confidence_reasoning=NotBlankStr("x"),
        ),
        config_changes=(
            ConfigChange(
                path=NotBlankStr("a.b"),
                old_value=1,
                new_value=2,
                description=NotBlankStr("d"),
            ),
        ),
        rollback_plan=RollbackPlan(
            operations=ops,
            validation_check=NotBlankStr("a.b equals 1"),
        ),
        confidence=0.8,
    )


class TestRollbackExecutor:
    async def test_dispatches_each_operation_to_its_handler(self) -> None:
        config_handler = _CountingHandler(returns=1)
        prompt_handler = _CountingHandler(returns=2)
        executor = RollbackExecutor(
            handlers={
                NotBlankStr("revert_config"): config_handler,
                NotBlankStr("restore_prompt"): prompt_handler,
            },
        )
        result = await executor.execute(
            _proposal(
                _operation("revert_config"),
                _operation("restore_prompt"),
            ),
        )
        assert result.success
        assert result.changes_applied == 3
        assert len(config_handler.calls) == 1
        assert len(prompt_handler.calls) == 1

    async def test_unknown_operation_type_raises(self) -> None:
        executor = RollbackExecutor(handlers={})
        with pytest.raises(UnknownRollbackOperationError):
            await executor.execute(_proposal(_operation("mystery")))

    async def test_handler_failure_stops_and_reports_failure(self) -> None:
        good = _CountingHandler(returns=5)
        bad = _CountingHandler(fail=True)
        executor = RollbackExecutor(
            handlers={
                NotBlankStr("revert_config"): good,
                NotBlankStr("restore_prompt"): bad,
            },
        )
        result = await executor.execute(
            _proposal(
                _operation("revert_config"),
                _operation("restore_prompt"),
                _operation("revert_config"),
            ),
        )
        assert not result.success
        assert result.changes_applied == 5
        assert len(good.calls) == 1  # second one never reached
        assert result.error_message is not None
        assert "boom" in result.error_message

    async def test_handler_is_runtime_checkable_protocol(self) -> None:
        assert isinstance(_CountingHandler(), RollbackHandler)

    async def test_empty_handlers_mapping_treated_as_none(self) -> None:
        executor = RollbackExecutor()
        with pytest.raises(UnknownRollbackOperationError):
            await executor.execute(_proposal(_operation("revert_config")))

    @pytest.mark.parametrize(
        "catastrophic",
        [MemoryError("oom"), RecursionError("stack")],
    )
    async def test_catastrophic_errors_are_reraised_never_swallowed(
        self,
        catastrophic: BaseException,
    ) -> None:
        """MemoryError/RecursionError must propagate past the executor.

        The executor's generic ``except Exception`` must not catch
        catastrophic system errors. Otherwise rollback would paper
        over out-of-memory / unbounded recursion instead of letting
        the process fail fast.
        """

        class _CatastrophicHandler:
            async def revert(self, operation: RollbackOperation) -> int:
                _ = operation
                raise catastrophic

        executor = RollbackExecutor(
            handlers={NotBlankStr("revert_config"): _CatastrophicHandler()},
        )
        with pytest.raises(type(catastrophic)):
            await executor.execute(_proposal(_operation("revert_config")))
