"""AWS Secrets Manager secret backend (stub).

Full implementation deferred -- this stub satisfies the
pluggable-backend protocol and raises ``NotImplementedError``
on all operations.
"""


class AwsSecretsManagerBackend:
    """Stub for AWS Secrets Manager secret storage."""

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "aws_secrets_manager"

    async def store(self, secret_id: str, value: bytes) -> None:
        """Not implemented."""
        msg = "AWS Secrets Manager backend not yet implemented"
        raise NotImplementedError(msg)

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Not implemented."""
        msg = "AWS Secrets Manager backend not yet implemented"
        raise NotImplementedError(msg)

    async def delete(self, secret_id: str) -> bool:
        """Not implemented."""
        msg = "AWS Secrets Manager backend not yet implemented"
        raise NotImplementedError(msg)
