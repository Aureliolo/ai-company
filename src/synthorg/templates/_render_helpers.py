"""Internal helpers extracted from the renderer to keep file size manageable.

These are private implementation details of the two-pass rendering
pipeline and should not be imported outside the ``templates`` package.
"""

from typing import Any

from pydantic import ValidationError

from synthorg.config.errors import ConfigLocation
from synthorg.config.schema import RootConfig
from synthorg.config.utils import to_float
from synthorg.observability import get_logger
from synthorg.observability.events.template import (
    TEMPLATE_RENDER_TYPE_ERROR,
    TEMPLATE_RENDER_VALIDATION_ERROR,
    TEMPLATE_RENDER_VARIABLE_ERROR,
)
from synthorg.templates.errors import TemplateRenderError, TemplateValidationError

logger = get_logger(__name__)


def build_departments(
    raw_depts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build RootConfig-compatible department dicts.

    Args:
        raw_depts: List of department dicts from rendered YAML.

    Returns:
        List of dicts suitable for ``Department`` construction.
    """
    departments: list[dict[str, Any]] = []
    for dept in raw_depts:
        try:
            budget_pct = to_float(
                dept.get("budget_percent", 0.0),
                field_name=f"departments[{dept.get('name', '')}].budget_percent",
            )
        except ValueError as exc:
            msg = f"Invalid department budget value: {exc}"
            logger.warning(
                TEMPLATE_RENDER_TYPE_ERROR,
                department=dept.get("name", ""),
                field="budget_percent",
                error=str(exc),
            )
            raise TemplateRenderError(msg) from exc
        dept_name = dept.get("name", "")
        head_role = dept.get("head_role")
        if not head_role:
            logger.warning(
                TEMPLATE_RENDER_VARIABLE_ERROR,
                department=dept_name,
                field="head_role",
                detail="No head_role specified; using department name as placeholder",
            )
            head_role = dept_name or ""
        head_merge_id = dept.get("head_merge_id", "")
        dept_dict: dict[str, Any] = {
            "name": dept_name,
            "head": head_role,
            "budget_percent": budget_pct,
        }
        if head_merge_id and dept.get("head_role"):
            dept_dict["head_id"] = head_merge_id
        elif head_merge_id:
            logger.warning(
                TEMPLATE_RENDER_VARIABLE_ERROR,
                department=dept_name,
                field="head_merge_id",
                detail=(
                    f"head_merge_id {head_merge_id!r} is set but "
                    f"head_role is missing; head_merge_id discarded"
                ),
            )
        reporting_lines = dept.get("reporting_lines")
        if reporting_lines is not None:
            if not isinstance(reporting_lines, list):
                msg = f"Department {dept_name!r} 'reporting_lines' must be a list"
                logger.warning(
                    TEMPLATE_RENDER_TYPE_ERROR,
                    department=dept_name,
                    field="reporting_lines",
                    expected="list",
                    got=type(reporting_lines).__name__,
                )
                raise TemplateRenderError(msg)
            dept_dict["reporting_lines"] = reporting_lines
        policies = dept.get("policies")
        if policies is not None:
            if not isinstance(policies, dict):
                msg = f"Department {dept_name!r} 'policies' must be a mapping"
                logger.warning(
                    TEMPLATE_RENDER_TYPE_ERROR,
                    department=dept_name,
                    field="policies",
                    expected="mapping",
                    got=type(policies).__name__,
                )
                raise TemplateRenderError(msg)
            dept_dict["policies"] = policies
        departments.append(dept_dict)
    return departments


def validate_as_root_config(
    merged: dict[str, Any],
    source_name: str,
) -> RootConfig:
    """Validate a merged config dict as RootConfig.

    Args:
        merged: Merged config dict.
        source_name: Label for error messages.

    Returns:
        Validated, frozen :class:`RootConfig`.

    Raises:
        TemplateValidationError: If validation fails.
    """
    try:
        return RootConfig(**merged)
    except ValidationError as exc:
        field_errors: list[tuple[str, str]] = []
        locations: list[ConfigLocation] = []
        for error in exc.errors():
            key_path = ".".join(str(p) for p in error["loc"])
            error_msg = error["msg"]
            field_errors.append((key_path, error_msg))
            locations.append(
                ConfigLocation(
                    file_path=source_name,
                    key_path=key_path,
                ),
            )
        logger.exception(
            TEMPLATE_RENDER_VALIDATION_ERROR,
            source_name=source_name,
            error_count=len(exc.errors()),
        )
        msg = f"Rendered template failed RootConfig validation: {source_name}"
        raise TemplateValidationError(
            msg,
            locations=tuple(locations),
            field_errors=tuple(field_errors),
        ) from exc
