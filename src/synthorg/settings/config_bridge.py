"""Config bridge — extract setting values from RootConfig by dotted path.

Maps ``(namespace, key)`` pairs to dotted attribute paths in
``RootConfig`` for YAML-layer resolution in the settings service.
"""

from synthorg.observability import get_logger

logger = get_logger(__name__)


def extract_from_config(config: object, yaml_path: str) -> str | None:
    """Resolve a dotted path against a config object.

    Traverses the object attribute chain for each segment in
    *yaml_path*.  Returns ``str(value)`` if the final attribute
    exists and is not ``None``, otherwise ``None``.

    Args:
        config: Root config object (typically ``RootConfig``).
        yaml_path: Dot-separated attribute path
            (e.g. ``"budget.total_monthly"``).

    Returns:
        The resolved value as a string, or ``None`` if the path
        cannot be resolved.
    """
    current: object = config
    for segment in yaml_path.split("."):
        try:
            current = getattr(current, segment)
        except AttributeError:
            return None
        if current is None:
            return None
    return str(current)
