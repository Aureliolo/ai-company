"""Built-in default values for company configuration."""

from typing import Any


def default_config_dict() -> dict[str, Any]:
    """Return base-layer configuration defaults as a raw dict.

    These defaults are merged beneath any user-provided YAML before
    Pydantic validation.  They ensure that every field has a sensible
    starting value even if omitted from the config file.

    Returns:
        Base-layer configuration dictionary.
    """
    return {
        "company_name": "AI Company",
        "company_type": "custom",
        "departments": [],
        "agents": [],
        "custom_roles": [],
        "config": {},
        "budget": {},
        "communication": {},
        "providers": {},
        "routing": {},
    }
