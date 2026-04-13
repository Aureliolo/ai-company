"""Schema audit: credential-bearing fields never leak into context models."""

from collections.abc import Mapping
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel

from synthorg.core.task import Task
from synthorg.engine._validation import _CREDENTIAL_KEY_PATTERNS
from synthorg.engine.context import AgentContext
from synthorg.engine.loop_protocol import TurnRecord

_PATTERNS = _CREDENTIAL_KEY_PATTERNS

# Types that could plausibly carry credential values.
_CREDENTIAL_CARRYING_TYPES = (str, dict, bytes, bytearray)


def _matches_credential_pattern(name: str) -> bool:
    """Check if a field name matches any credential pattern."""
    return any(p.search(name) for p in _PATTERNS)


def _could_carry_credential(annotation: Any) -> bool:
    """Return True if the annotation could hold a credential.

    Numeric fields (int, float, bool) and enum fields cannot carry
    credential strings, so ``input_tokens: int`` is safe even
    though the name contains "token".
    """
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        return any(_could_carry_credential(a) for a in args)
    if annotation is Any:
        return True
    return isinstance(annotation, type) and issubclass(
        annotation, _CREDENTIAL_CARRYING_TYPES
    )


def _check_model_recursive(
    model_cls: type[BaseModel],
    path: str,
    visited: set[type],
    violations: list[str],
) -> None:
    """Recursively check a Pydantic model for credential-bearing fields."""
    if model_cls in visited:
        return
    visited.add(model_cls)

    for name, info in model_cls.model_fields.items():
        field_path = f"{path}.{name}"
        annotation = info.annotation

        # Check the field name if the type could carry credentials.
        # BaseModel fields are included: a field named "api_key" is
        # suspicious even if wrapped in a Pydantic model.
        is_model = isinstance(annotation, type) and issubclass(
            annotation,
            BaseModel,
        )
        if (
            _could_carry_credential(annotation) or is_model
        ) and _matches_credential_pattern(name):
            violations.append(
                f"{field_path} (type={annotation}) matches a credential pattern",
            )

        # Recurse into nested BaseModel subclasses.
        origin = get_origin(annotation)
        targets: list[Any] = []
        if origin is not None:
            targets.extend(get_args(annotation))
        else:
            targets.append(annotation)

        for target in targets:
            if (
                isinstance(target, type)
                and issubclass(target, BaseModel)
                and target not in visited
            ):
                _check_model_recursive(target, field_path, visited, violations)


@pytest.mark.unit
class TestCredentialSchemaAudit:
    """Ensure sensitive models have no credential-bearing fields."""

    def test_agent_context_has_no_credential_fields(self) -> None:
        violations: list[str] = []
        _check_model_recursive(
            AgentContext,
            "AgentContext",
            set(),
            violations,
        )
        assert not violations, f"Credential-bearing fields found: {violations}"

    def test_turn_record_has_no_credential_fields(self) -> None:
        violations: list[str] = []
        _check_model_recursive(
            TurnRecord,
            "TurnRecord",
            set(),
            violations,
        )
        assert not violations, f"Credential-bearing fields found: {violations}"

    def test_task_metadata_is_the_extensibility_point(
        self,
    ) -> None:
        """Task.metadata is the only dict/Mapping field on Task."""

        def _is_mapping_type(annotation: Any) -> bool:
            origin = get_origin(annotation)
            if origin is not None:
                if isinstance(origin, type) and issubclass(origin, Mapping):
                    return True
                return any(_is_mapping_type(a) for a in get_args(annotation))
            return isinstance(annotation, type) and issubclass(
                annotation,
                Mapping,
            )

        dict_fields = [
            n for n, f in Task.model_fields.items() if _is_mapping_type(f.annotation)
        ]
        assert dict_fields == ["metadata"], (
            f"Expected only 'metadata' as mapping field, found: {dict_fields}"
        )
