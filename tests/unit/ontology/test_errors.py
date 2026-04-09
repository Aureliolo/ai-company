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

    @pytest.mark.parametrize(
        "subclass",
        [
            OntologyConnectionError,
            OntologyNotFoundError,
            OntologyDuplicateError,
            OntologyConfigError,
        ],
    )
    def test_subclass_inherits_base(
        self,
        subclass: type[OntologyError],
    ) -> None:
        assert issubclass(subclass, OntologyError)

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
