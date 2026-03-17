"""Config bridge — extract setting values from RootConfig by dotted path.

Maps ``(namespace, key)`` pairs to dotted attribute paths in
``RootConfig`` for YAML-layer resolution in the settings service.
"""

import json

from pydantic import BaseModel

from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_CONFIG_PATH_MISS

logger = get_logger(__name__)


def _serialize_value(value: object) -> str:
    """Serialize a resolved config value to a string.

    Handles Pydantic models, collections of models, dicts with
    model values, and plain collections by producing valid JSON.
    Scalars fall back to ``str()``.

    Args:
        value: The resolved config attribute.

    Returns:
        A string representation suitable for the settings layer.
    """
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(mode="json"))

    if isinstance(value, (tuple, list)):
        if any(isinstance(item, BaseModel) for item in value):
            return json.dumps(
                [
                    item.model_dump(mode="json")
                    if isinstance(item, BaseModel)
                    else item
                    for item in value
                ]
            )
        return json.dumps(list(value))

    if isinstance(value, dict):
        if any(isinstance(v, BaseModel) for v in value.values()):
            return json.dumps(
                {
                    k: v.model_dump(mode="json") if isinstance(v, BaseModel) else v
                    for k, v in value.items()
                }
            )
        return json.dumps(value)

    return str(value)


def extract_from_config(config: object, yaml_path: str) -> str | None:
    """Resolve a dotted path against a config object.

    Traverses the object attribute chain for each segment in
    *yaml_path*.  Returns a serialized string if the final
    attribute exists and is not ``None``, otherwise ``None``.

    For Pydantic models, tuples/lists containing models, and
    dicts with model values, the result is valid JSON.  For
    scalars, the result is ``str(value)``.

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
            logger.debug(
                SETTINGS_CONFIG_PATH_MISS,
                yaml_path=yaml_path,
                failed_segment=segment,
            )
            return None
        if current is None:
            return None
    return _serialize_value(current)
