"""Core domain models for the SynthOrg framework.

This package uses explicit per-module imports rather than
re-exporting everything from the top level.  Import specific
symbols from their defining submodule, e.g.::

    from synthorg.core.types import NotBlankStr
    from synthorg.core.agent import AgentIdentity

This avoids a ~2 second import-time cost that the eager re-export
approach imposed on every caller that merely wanted a leaf type
(like ``NotBlankStr`` from ``synthorg.core.types``).
"""
