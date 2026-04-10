"""Immutability helpers for frozen Pydantic models.

Re-exports from :mod:`synthorg.core.immutable` for backward
compatibility.  The canonical location is ``core.immutable`` to
avoid circular imports when ``communication`` needs these utilities
(``engine.__init__`` eagerly imports the full engine module tree).
"""

from synthorg.core.immutable import deep_copy_mapping, freeze_recursive

__all__ = ["deep_copy_mapping", "freeze_recursive"]
