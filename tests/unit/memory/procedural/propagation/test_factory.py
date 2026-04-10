"""Tests for propagation strategy factory."""

import pytest

from synthorg.memory.procedural.propagation.config import PropagationConfig
from synthorg.memory.procedural.propagation.department_scoped import (
    DepartmentScopedPropagation,
)
from synthorg.memory.procedural.propagation.factory import (
    build_propagation_strategy,
)
from synthorg.memory.procedural.propagation.no_propagation import (
    NoPropagation,
)
from synthorg.memory.procedural.propagation.role_scoped import (
    RoleScopedPropagation,
)


@pytest.mark.unit
class TestBuildPropagationStrategy:
    """build_propagation_strategy dispatches on config type."""

    def test_none_type(self) -> None:
        config = PropagationConfig(type="none")
        strategy = build_propagation_strategy(config)
        assert isinstance(strategy, NoPropagation)

    def test_role_scoped_type(self) -> None:
        config = PropagationConfig(type="role_scoped")
        strategy = build_propagation_strategy(config)
        assert isinstance(strategy, RoleScopedPropagation)

    def test_department_scoped_type(self) -> None:
        config = PropagationConfig(type="department_scoped")
        strategy = build_propagation_strategy(config)
        assert isinstance(strategy, DepartmentScopedPropagation)

    def test_default_is_none(self) -> None:
        config = PropagationConfig()
        strategy = build_propagation_strategy(config)
        assert isinstance(strategy, NoPropagation)

    def test_max_targets_forwarded(self) -> None:
        config = PropagationConfig(
            type="role_scoped",
            max_propagation_targets=5,
        )
        strategy = build_propagation_strategy(config)
        assert isinstance(strategy, RoleScopedPropagation)
        assert strategy.max_targets == 5
