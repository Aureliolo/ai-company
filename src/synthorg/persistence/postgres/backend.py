"""PostgresPersistenceBackend stub (Phase 0 scaffolding).

The concrete implementation lands in Phase 2.  This stub exists so the
package can be imported, the factory can dispatch to it, and config
validation can run end-to-end during Phase 0 without requiring the
full repository port.
"""

from synthorg.persistence.config import PostgresConfig  # noqa: TC001


class PostgresPersistenceBackend:
    """Postgres implementation of the PersistenceBackend protocol.

    Raises:
        NotImplementedError: Until the lifecycle and repositories land
            in Phase 2 / Phase 3.
    """

    def __init__(self, config: PostgresConfig) -> None:
        self._config = config
        msg = "PostgresPersistenceBackend lifecycle not yet implemented"
        raise NotImplementedError(msg)
