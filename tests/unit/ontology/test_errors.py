"""Tests for ontology error hierarchy."""

import pytest

from synthorg.ontology.errors import (
    OntologyConfigError,
    OntologyConnectionError,
    OntologyDuplicateError,
    OntologyError,
    OntologyNotFoundError,
)

pytestmark = pytest.mark.unit


class TestOntologyErrorHierarchy:
    """Verify error inheritance and message propagation."""

    def test_base_error_is_exception(self) -> None:
        assert issubclass(OntologyError, Exception)

    def test_connection_error_inherits_base(self) -> None:
        assert issubclass(OntologyConnectionError, OntologyError)

    def test_not_found_error_inherits_base(self) -> None:
        assert issubclass(OntologyNotFoundError, OntologyError)

    def test_duplicate_error_inherits_base(self) -> None:
        assert issubclass(OntologyDuplicateError, OntologyError)

    def test_config_error_inherits_base(self) -> None:
        assert issubclass(OntologyConfigError, OntologyError)

    def test_catch_base_catches_subtypes(self) -> None:
        for cls in (
            OntologyConnectionError,
            OntologyNotFoundError,
            OntologyDuplicateError,
            OntologyConfigError,
        ):
            with pytest.raises(OntologyError):
                raise cls("test")  # noqa: EM101

    def test_message_propagates(self) -> None:
        err = OntologyNotFoundError("Entity 'Foo' not found")
        assert str(err) == "Entity 'Foo' not found"
