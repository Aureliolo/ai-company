"""Schema audit: credential-bearing fields never leak into context models."""

from typing import Any, get_args, get_origin

import pytest

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


@pytest.mark.unit
class TestCredentialSchemaAudit:
    """Ensure sensitive models have no credential-bearing fields."""

    def test_agent_context_has_no_credential_fields(self) -> None:
        for name, info in AgentContext.model_fields.items():
            if not _could_carry_credential(info.annotation):
                continue
            assert not _matches_credential_pattern(name), (
                f"AgentContext.{name} (type={info.annotation}) "
                f"matches a credential pattern"
            )

    def test_turn_record_has_no_credential_fields(self) -> None:
        for name, info in TurnRecord.model_fields.items():
            if not _could_carry_credential(info.annotation):
                continue
            assert not _matches_credential_pattern(name), (
                f"TurnRecord.{name} (type={info.annotation}) "
                f"matches a credential pattern"
            )

    def test_task_metadata_is_the_extensibility_point(
        self,
    ) -> None:
        """Task.metadata is the only dict[str, Any] on Task."""
        dict_fields = [
            n
            for n, f in Task.model_fields.items()
            if "dict" in str(f.annotation).lower()
        ]
        assert dict_fields == ["metadata"], (
            f"Expected only 'metadata' as dict field, found: {dict_fields}"
        )
