"""Tests for persistence error hierarchy."""

import pytest

from ai_company.persistence.errors import (
    DuplicateRecordError,
    MigrationError,
    PersistenceConnectionError,
    PersistenceError,
    QueryError,
    RecordNotFoundError,
)


@pytest.mark.unit
class TestPersistenceErrorHierarchy:
    def test_base_is_exception(self) -> None:
        assert issubclass(PersistenceError, Exception)

    def test_connection_error_inherits(self) -> None:
        assert issubclass(PersistenceConnectionError, PersistenceError)

    def test_migration_error_inherits(self) -> None:
        assert issubclass(MigrationError, PersistenceError)

    def test_record_not_found_inherits(self) -> None:
        assert issubclass(RecordNotFoundError, PersistenceError)

    def test_duplicate_record_inherits(self) -> None:
        assert issubclass(DuplicateRecordError, PersistenceError)

    def test_query_error_inherits(self) -> None:
        assert issubclass(QueryError, PersistenceError)

    @pytest.mark.parametrize(
        "cls",
        [
            PersistenceConnectionError,
            MigrationError,
            RecordNotFoundError,
            DuplicateRecordError,
            QueryError,
        ],
    )
    def test_catch_all_with_base(self, cls: type[PersistenceError]) -> None:
        """All subclasses are caught by except PersistenceError."""
        msg = "test"
        with pytest.raises(PersistenceError):
            raise cls(msg)

    def test_error_message_preserved(self) -> None:
        err = PersistenceConnectionError("db down")
        assert str(err) == "db down"

    def test_does_not_shadow_builtin(self) -> None:
        """Our error is NOT the builtin ConnectionError."""
        assert PersistenceConnectionError is not ConnectionError  # type: ignore[comparison-overlap]
