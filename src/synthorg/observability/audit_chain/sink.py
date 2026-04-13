"""AuditChainSink -- logging handler that signs and chains security events."""

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING

from synthorg.observability.audit_chain.chain import HashChain

if TYPE_CHECKING:
    from synthorg.observability.audit_chain.config import AuditChainConfig
    from synthorg.observability.audit_chain.protocol import AuditChainSigner
    from synthorg.observability.audit_chain.timestamping import (
        TimestampProvider,
    )

_logger = logging.getLogger(__name__)


class AuditChainSink(logging.Handler):
    """Logging handler that signs security events and appends to a hash chain.

    Only processes events whose message starts with ``"security."``.
    Thread-safe via a lock around chain mutation.

    Args:
        signer: Signing backend (ML-DSA-65 or equivalent).
        timestamp_provider: Trusted timestamp source.
        chain: Hash chain instance for append-only storage.
        config: Audit chain configuration.
    """

    def __init__(
        self,
        *,
        signer: AuditChainSigner,
        timestamp_provider: TimestampProvider,
        chain: HashChain | None = None,
        config: AuditChainConfig | None = None,
    ) -> None:
        super().__init__()
        self._signer = signer
        self._timestamp_provider = timestamp_provider
        self._chain = chain or HashChain()
        self._config = config
        self._lock = threading.Lock()

    @property
    def chain(self) -> HashChain:
        """Read-only access to the underlying hash chain."""
        return self._chain

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record, signing security events.

        Non-security events are silently ignored.

        Args:
            record: Log record from the logging framework.
        """
        msg = record.getMessage()
        if not msg.startswith("security."):
            return

        try:
            # Serialize record to canonical JSON.
            data = json.dumps(
                {
                    "event": msg,
                    "level": record.levelname,
                    "timestamp": record.created,
                    "module": record.module,
                },
                sort_keys=True,
                ensure_ascii=True,
            ).encode("utf-8")

            # Sign and chain are async -- bridge from sync emit.
            loop = self._get_or_create_loop()
            signed = loop.run_until_complete(self._signer.sign(data))
            timestamp = loop.run_until_complete(
                self._timestamp_provider.get_timestamp(),
            )

            with self._lock:
                self._chain.append(
                    event_data=data,
                    signature=signed.signature,
                    timestamp=timestamp,
                )

        except MemoryError, RecursionError:
            raise
        except Exception:
            # Best-effort: never crash the logging pipeline.
            _logger.debug(
                "audit_chain.emit_error",
                exc_info=True,
            )

    @staticmethod
    def _get_or_create_loop() -> asyncio.AbstractEventLoop:
        """Get the current event loop or create a new one."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop
