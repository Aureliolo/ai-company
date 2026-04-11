"""HashiCorp Vault secret backend (stub).

Full implementation deferred -- this stub satisfies the
pluggable-backend protocol and raises ``NotImplementedError``
on all operations.
"""


class VaultSecretBackend:
    """Stub for HashiCorp Vault secret storage."""

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "vault"

    async def store(self, secret_id: str, value: bytes) -> None:
        """Not implemented."""
        msg = "HashiCorp Vault backend not yet implemented"
        raise NotImplementedError(msg)

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Not implemented."""
        msg = "HashiCorp Vault backend not yet implemented"
        raise NotImplementedError(msg)

    async def delete(self, secret_id: str) -> bool:
        """Not implemented."""
        msg = "HashiCorp Vault backend not yet implemented"
        raise NotImplementedError(msg)
