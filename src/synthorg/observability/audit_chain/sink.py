"""AuditChainSink -- logging handler that signs and chains security events."""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.observability.audit_chain.chain import HashChain

if TYPE_CHECKING:
    from synthorg.observability.audit_chain.config import AuditChainConfig
    from synthorg.observability.audit_chain.protocol import AuditChainSigner
    from synthorg.observability.audit_chain.timestamping import (
        TimestampProvider,
    )

_logger = logging.getLogger(__name__)

# Dedicated thread pool for async-to-sync bridging.  A single worker
# avoids contention and keeps chain appends sequential.
_SIGNING_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audit-sign")


class AuditChainSink(logging.Handler):
    """Logging handler that signs security events and appends to a hash chain.

    Only processes events whose message starts with ``"security."``.
    Thread-safe via a lock around chain mutation.

    Uses a dedicated thread pool to bridge async signing into the
    synchronous ``emit()`` method, avoiding the ``run_until_complete``
    deadlock that occurs when called from within an existing event loop.

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

            # Bridge async signing into sync emit via a dedicated
            # thread pool.  This avoids the run_until_complete
            # deadlock that occurs when emit() is called from within
            # an existing event loop (the normal case in async apps).
            import asyncio  # noqa: PLC0415

            future = _SIGNING_EXECUTOR.submit(
                asyncio.run,
                self._signer.sign(data),
            )
            signed = future.result(timeout=5.0)

            timestamp = datetime.now(UTC)

            with self._lock:
                self._chain.append(
                    event_data=data,
                    signature=signed.signature,
                    timestamp=timestamp,
                )

        except MemoryError, RecursionError:
            raise
        except Exception:
            _logger.error(
                "security.audit_chain.emit_error",
                exc_info=True,
            )
