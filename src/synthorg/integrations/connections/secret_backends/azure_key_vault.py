"""Azure Key Vault secret backend (stub).

Full implementation deferred -- this stub satisfies the
pluggable-backend protocol and raises ``NotImplementedError``
on all operations.
"""


class AzureKeyVaultBackend:
    """Stub for Azure Key Vault secret storage."""

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "azure_key_vault"

    async def store(self, secret_id: str, value: bytes) -> None:
        """Not implemented."""
        msg = "Azure Key Vault backend not yet implemented"
        raise NotImplementedError(msg)

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Not implemented."""
        msg = "Azure Key Vault backend not yet implemented"
        raise NotImplementedError(msg)

    async def delete(self, secret_id: str) -> bool:
        """Not implemented."""
        msg = "Azure Key Vault backend not yet implemented"
        raise NotImplementedError(msg)
