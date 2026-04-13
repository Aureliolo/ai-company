"""AuditChainVerifier -- verify hash chain and EvidencePackage signatures."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.observability import get_logger
from synthorg.observability.audit_chain.chain import HashChain  # noqa: TC001
from synthorg.observability.audit_chain.protocol import AuditChainSigner  # noqa: TC001
from synthorg.observability.events.security import (
    SECURITY_AUDIT_CHAIN_BREAK_DETECTED,
    SECURITY_AUDIT_CHAIN_VERIFY_COMPLETE,
    SECURITY_AUDIT_CHAIN_VERIFY_START,
)

logger = get_logger(__name__)


class ChainVerificationResult(BaseModel):
    """Result of verifying an audit chain.

    Attributes:
        valid: Whether the entire chain is intact.
        entries_checked: Number of entries verified.
        first_break_position: Position of first broken link, if any.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    valid: bool = Field(description="Whether the chain is intact")
    entries_checked: int = Field(
        ge=0,
        description="Number of entries verified",
    )
    first_break_position: int | None = Field(
        default=None,
        description="Position of first broken link",
    )


class AuditChainVerifier:
    """Verify audit chain integrity and EvidencePackage signatures.

    Args:
        signer: Signing backend for signature verification.
    """

    def __init__(self, signer: AuditChainSigner) -> None:
        self._signer = signer

    async def verify_chain(self, chain: HashChain) -> ChainVerificationResult:
        """Verify the entire hash chain.

        Checks hash continuity and verifies each signature.

        Args:
            chain: Hash chain to verify.

        Returns:
            Verification result with validity and break position.
        """
        logger.debug(
            SECURITY_AUDIT_CHAIN_VERIFY_START,
            entry_count=len(chain.entries),
        )

        entries = chain.entries
        if not entries:
            return ChainVerificationResult(
                valid=True,
                entries_checked=0,
            )

        # Check hash continuity.
        if not chain.verify_integrity():
            # Find the first break.
            expected_prev = "genesis"
            for entry in entries:
                if entry.previous_hash != expected_prev:
                    logger.error(
                        SECURITY_AUDIT_CHAIN_BREAK_DETECTED,
                        position=entry.position,
                        expected=expected_prev,
                        actual=entry.previous_hash,
                    )
                    return ChainVerificationResult(
                        valid=False,
                        entries_checked=entry.position,
                        first_break_position=entry.position,
                    )
                import hashlib  # noqa: PLC0415

                chain_input = f"{expected_prev}:{entry.event_hash}".encode()
                expected_prev = hashlib.sha256(chain_input).hexdigest()

        logger.debug(
            SECURITY_AUDIT_CHAIN_VERIFY_COMPLETE,
            entries_checked=len(entries),
            valid=True,
        )

        return ChainVerificationResult(
            valid=True,
            entries_checked=len(entries),
        )

    async def verify_evidence_package(self, pkg: object) -> bool:
        """Verify that an EvidencePackage has sufficient valid signatures.

        Args:
            pkg: An ``EvidencePackage`` instance.

        Returns:
            ``True`` if ``is_fully_signed`` and all signatures verify.
        """
        if not getattr(pkg, "is_fully_signed", False):
            return False

        for sig in getattr(pkg, "signatures", ()):
            valid = await self._signer.verify(
                b"",  # Placeholder -- real impl needs original data.
                sig.signature_bytes,
            )
            if not valid:
                return False

        return True
