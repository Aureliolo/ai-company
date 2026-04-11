"""Stable constraint tokens for user-table DB invariants.

These tokens are returned by ``ConstraintViolationError.constraint``
and are shared across all persistence backends (SQLite, Postgres)
and the API controller layer.  Keeping them in one module prevents
token drift between backends and call sites.
"""

USERS_USERNAME_UNIQUE: str = "users.username"
"""UNIQUE constraint on ``users.username``."""

IDX_SINGLE_CEO: str = "idx_single_ceo"
"""Partial unique index allowing at most one CEO."""

LAST_CEO_TRIGGER: str = "enforce_ceo_minimum"
"""Constraint trigger preventing removal of the last CEO."""

LAST_OWNER_TRIGGER: str = "enforce_owner_minimum"
"""Constraint trigger preventing removal of the last owner."""
