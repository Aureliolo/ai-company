"""Coverage guard: every controller decorator site uses the registry.

HYG-2 migrated all ``per_op_rate_limit(...)`` sites in the controller
package to ``per_op_rate_limit_from_policy(...)``.  This test AST-walks
the package and fails loud if a bare ``per_op_rate_limit(`` call ever
re-appears, or if a new policy key is referenced that has not been
registered in :data:`RATE_LIMIT_POLICIES`.
"""

import ast
from pathlib import Path

import pytest

from synthorg.api.rate_limits.policies import RATE_LIMIT_POLICIES

pytestmark = pytest.mark.unit

_CONTROLLERS_DIR = (
    Path(__file__).resolve().parents[4] / "src" / "synthorg" / "api" / "controllers"
)


def _controller_files() -> list[Path]:
    """Every ``*.py`` directly inside ``src/synthorg/api/controllers``."""
    return sorted(p for p in _CONTROLLERS_DIR.glob("*.py") if p.name != "__init__.py")


def test_controllers_directory_discovered() -> None:
    # Sanity: the path math above must land on a non-empty dir;
    # otherwise the coverage assertions below would be vacuously true.
    files = _controller_files()
    assert files, f"no controller files discovered at {_CONTROLLERS_DIR}"


def test_no_residual_bare_per_op_rate_limit_calls() -> None:
    """No controller may call the primitive decorator directly."""
    offenders: list[str] = []
    for path in _controller_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "per_op_rate_limit"
        )
    assert not offenders, (
        "Controllers must use per_op_rate_limit_from_policy instead "
        "of the bare per_op_rate_limit primitive. Offending sites: "
        f"{offenders!r}"
    )


def test_every_policy_lookup_resolves() -> None:
    """Every string passed to the helper must exist in the registry."""
    unknown: list[tuple[str, str, int]] = []
    for path in _controller_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "per_op_rate_limit_from_policy":
                continue
            if not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                # A non-literal first arg is unusual but not wrong --
                # the runtime KeyError remains the safety net.
                continue
            if first.value not in RATE_LIMIT_POLICIES:
                unknown.append((path.name, first.value, node.lineno))
    assert not unknown, (
        "Controllers reference policy keys missing from "
        "RATE_LIMIT_POLICIES: "
        + ", ".join(f"{name}:{line} -> {op!r}" for name, op, line in unknown)
    )
