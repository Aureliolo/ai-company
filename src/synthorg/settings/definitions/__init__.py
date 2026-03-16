"""Setting definitions for all namespaces.

Importing this package triggers registration of all setting
definitions into the global :func:`~synthorg.settings.registry.get_registry`.
"""

from synthorg.settings.definitions import (
    backup,
    budget,
    company,
    coordination,
    memory,
    observability,
    providers,
    security,
)
