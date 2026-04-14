"""AuditChainSink -- logging handler that signs and chains security events."""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.audit_chain.chain import HashChain

if TYPE_CHECKING:
    from synthorg.observability.audit_chain.config import AuditChainConfig
    from synthorg.observability.audit_chain.protocol import AuditChainSigner
    from synthorg.observability.audit_chain.timestamping import (
        TimestampProvider,
    )

logger = get_logger(__name__)

# Dedicated thread pool for async-to-sync bridging.  A single worker
# avoids contention and keeps chain appends sequential.
_SIGNING_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audit-sign")


class AuditChainSink(logging.Handler):
    """Logging handler that signs security events and appends to a hash chain.

    Processes events whose message starts with ``"security."`` or
    ``"tool.registry.integrity."``.  Thread-safe via a lock around
    chain mutation.

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
        """Read-only snapshot of the chain's entries.

        Returns a new ``HashChain`` populated with a copy of the
        current entries so callers cannot mutate the live chain.
        """
        with self._lock:
            return self._chain.snapshot()

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record, signing security events.

        Non-security events are silently ignored.

        Args:
            record: Log record from the logging framework.
        """
        _AUDITED_PREFIXES = ("security.", "tool.registry.integrity.")  # noqa: N806
        msg = record.getMessage()
        if not any(msg.startswith(p) for p in _AUDITED_PREFIXES):
            return

        try:
            payload: dict[str, object] = {
                "event": msg,
                "level": record.levelname,
                "timestamp": record.created,
                "module": record.module,
            }
            # Merge structured extras from the log record.
            for key in (
                "tool_name",
                "expected_hash",
                "actual_hash",
                "correlation_id",
                "principal",
                "resource",
                "action_type",
                "error",
            ):
                val = getattr(record, key, None)
                if val is not None:
                    payload[key] = val
            data = json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=True,
                default=str,
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

            # Use the injected timestamp provider when available.
            ts_future = _SIGNING_EXECUTOR.submit(
                asyncio.run,
                self._timestamp_provider.get_timestamp(),
            )
            timestamp = ts_future.result(timeout=5.0)

            with self._lock:
                self._chain.append(
                    event_data=data,
                    signature=signed.signature,
                    timestamp=timestamp,
                )

        except MemoryError, RecursionError:
            raise
        except Exception:
            # Use a non-security event to avoid re-entering this
            # handler (all "security." events would loop back).
            logger.error(
                "audit_chain.emit_error",
                exc_info=True,
            )
