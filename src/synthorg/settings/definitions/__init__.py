"""Setting definitions for all namespaces.

Importing this package triggers registration of all setting
definitions into the global :func:`~synthorg.settings.registry.get_registry`.
"""

from synthorg.settings.definitions import (
    api,
    backup,
    budget,
    company,
    coordination,
    engine,
    integrations,
    memory,
    observability,
    providers,
    security,
)

__all__ = [
    "api",
    "backup",
    "budget",
    "company",
    "coordination",
    "engine",
    "integrations",
    "memory",
    "observability",
    "providers",
    "security",
]
