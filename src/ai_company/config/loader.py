"""YAML configuration loader with layered merging and validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ai_company.config.defaults import default_config_dict
from ai_company.config.errors import (
    ConfigFileNotFoundError,
    ConfigLocation,
    ConfigParseError,
    ConfigValidationError,
)
from ai_company.config.schema import RootConfig

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict.

    Nested dicts are merged recursively.  Lists, scalars, and all other
    types in *override* replace the corresponding value in *base*
    entirely.  Neither input dict is mutated.

    Args:
        base: Base configuration dict.
        override: Override values to layer on top.

    Returns:
        A new merged dict.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _parse_yaml_file(file_path: Path) -> dict[str, Any]:
    """Parse a YAML file and return its top-level mapping.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Parsed dict (empty dict for ``null`` / empty files).

    Raises:
        ConfigFileNotFoundError: If *file_path* does not exist.
        ConfigParseError: If the file contains invalid YAML or its
            top-level value is not a mapping.
    """
    if not file_path.exists():
        msg = f"Configuration file not found: {file_path}"
        raise ConfigFileNotFoundError(
            msg,
            locations=(ConfigLocation(file_path=str(file_path)),),
        )
    text = file_path.read_text(encoding="utf-8")
    return _parse_yaml_string(text, str(file_path))


def _parse_yaml_string(
    text: str,
    source_name: str,
) -> dict[str, Any]:
    """Parse a YAML string and return its top-level mapping.

    Args:
        text: Raw YAML content.
        source_name: Label used in error messages (file path or
            ``"<string>"``).

    Returns:
        Parsed dict (empty dict for ``null`` / empty strings).

    Raises:
        ConfigParseError: If the text is invalid YAML or its top-level
            value is not a mapping.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line: int | None = None
        col: int | None = None
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            line = exc.problem_mark.line + 1
            col = exc.problem_mark.column + 1
        msg = f"YAML syntax error in {source_name}: {exc}"
        raise ConfigParseError(
            msg,
            locations=(
                ConfigLocation(
                    file_path=source_name,
                    line=line,
                    column=col,
                ),
            ),
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"Expected YAML mapping at top level, got {type(data).__name__}"
        raise ConfigParseError(
            msg,
            locations=(ConfigLocation(file_path=source_name),),
        )
    return data


def _walk_node(
    node: yaml.Node,
    prefix: str,
    result: dict[str, tuple[int, int]],
) -> None:
    """Recursively traverse a composed YAML node tree.

    Populates *result* with ``dot.path`` -> ``(line, column)`` entries
    for every scalar, mapping key, and sequence element.
    """
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode):
                key: str = key_node.value
                path = f"{prefix}.{key}" if prefix else key
                mark = value_node.start_mark
                if mark is not None:
                    result[path] = (mark.line + 1, mark.column + 1)
                _walk_node(value_node, path, result)
    elif isinstance(node, yaml.SequenceNode):
        for idx, item_node in enumerate(node.value):
            path = f"{prefix}.{idx}"
            mark = item_node.start_mark
            if mark is not None:
                result[path] = (mark.line + 1, mark.column + 1)
            _walk_node(item_node, path, result)


def _build_line_map(yaml_text: str) -> dict[str, tuple[int, int]]:
    """Build a mapping from dot-path keys to ``(line, column)`` pairs.

    Uses :func:`yaml.compose` to walk the raw YAML AST without
    constructing Python objects, extracting positional information for
    each key path.

    Args:
        yaml_text: Raw YAML content.

    Returns:
        Dict mapping ``"dot.path"`` strings to ``(line, column)`` tuples
        (both 1-based).  Returns an empty dict if the YAML cannot be
        composed.
    """
    try:
        root = yaml.compose(yaml_text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return {}
    if root is None or not isinstance(root, yaml.MappingNode):
        return {}
    result: dict[str, tuple[int, int]] = {}
    _walk_node(root, "", result)
    return result


def _validate_config_dict(
    data: dict[str, Any],
    *,
    source_file: str | None = None,
    line_map: dict[str, tuple[int, int]] | None = None,
) -> RootConfig:
    """Validate a raw config dict against :class:`RootConfig`.

    Args:
        data: Merged configuration dict.
        source_file: File path label for error messages.
        line_map: Dot-path to (line, col) mapping for error enrichment.

    Returns:
        Validated, frozen :class:`RootConfig`.

    Raises:
        ConfigValidationError: If Pydantic validation fails.
    """
    try:
        return RootConfig(**data)
    except ValidationError as exc:
        if line_map is None:
            line_map = {}
        locations: list[ConfigLocation] = []
        field_errors: list[tuple[str, str]] = []
        for error in exc.errors():
            key_path = ".".join(str(p) for p in error["loc"])
            error_msg = error["msg"]
            field_errors.append((key_path, error_msg))
            line_col = line_map.get(key_path)
            locations.append(
                ConfigLocation(
                    file_path=source_file,
                    key_path=key_path,
                    line=line_col[0] if line_col else None,
                    column=line_col[1] if line_col else None,
                ),
            )
        msg = "Configuration validation failed"
        raise ConfigValidationError(
            msg,
            locations=tuple(locations),
            field_errors=tuple(field_errors),
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    config_path: Path | str,
    *,
    override_paths: tuple[Path | str, ...] = (),
) -> RootConfig:
    """Load and validate company configuration from YAML file(s).

    Loading order (each layer deep-merges onto the previous):

    1. Built-in defaults (from :func:`default_config_dict`).
    2. Primary config file at *config_path*.
    3. Override files in order.

    Args:
        config_path: Path to the primary config file.
        override_paths: Additional config files layered on top.

    Returns:
        Validated, frozen :class:`RootConfig`.

    Raises:
        ConfigFileNotFoundError: If any config file does not exist.
        ConfigParseError: If any file contains invalid YAML.
        ConfigValidationError: If the merged config fails validation.
    """
    config_path = Path(config_path)

    # 1. Start with built-in defaults
    merged = default_config_dict()

    # 2. Load and merge primary config
    primary = _parse_yaml_file(config_path)
    merged = _deep_merge(merged, primary)

    # 3. Apply override layers
    for override_path in override_paths:
        override = _parse_yaml_file(Path(override_path))
        merged = _deep_merge(merged, override)

    # 4. Build line map from primary file for error reporting
    yaml_text = config_path.read_text(encoding="utf-8")
    line_map = _build_line_map(yaml_text)

    # 5. Validate
    return _validate_config_dict(
        merged,
        source_file=str(config_path),
        line_map=line_map,
    )


def load_config_from_string(
    yaml_string: str,
    *,
    source_name: str = "<string>",
) -> RootConfig:
    """Load and validate config from a YAML string.

    Merges with built-in defaults before validation.  Useful for API
    endpoints and testing.

    Args:
        yaml_string: Raw YAML content.
        source_name: Label used in error messages.

    Returns:
        Validated, frozen :class:`RootConfig`.

    Raises:
        ConfigParseError: If the YAML is invalid.
        ConfigValidationError: If the merged config fails validation.
    """
    data = _parse_yaml_string(yaml_string, source_name)
    merged = _deep_merge(default_config_dict(), data)
    line_map = _build_line_map(yaml_string)
    return _validate_config_dict(
        merged,
        source_file=source_name,
        line_map=line_map,
    )
