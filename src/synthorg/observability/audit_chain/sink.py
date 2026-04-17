"""AuditChainSink -- logging handler that signs and chains security events."""

import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.audit_chain.chain import HashChain
from synthorg.observability.events.audit_chain import (
    AUDIT_CHAIN_CALLBACK_ERROR,
    AUDIT_CHAIN_EMIT_ERROR,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from synthorg.observability.audit_chain.config import AuditChainConfig
    from synthorg.observability.audit_chain.protocol import AuditChainSigner
    from synthorg.observability.audit_chain.timestamping import (
        TimestampProvider,
    )

    # Signature: (status, chain_depth, timestamp_unix) -> None
    # where status is one of: "signed", "fallback", "error".
    AppendCallback = Callable[[str, int, float], None]

logger = get_logger(__name__)


def _build_binding_payload(
    *,
    tail_hash: str,
    event_data: bytes,
    signature: bytes,
) -> bytes:
    """Return the bytes a TSA should timestamp for an append.

    Including the current tail hash, a digest of the event data, and
    the signature produces a per-append payload that an attacker
    cannot precompute. The resulting TSA token is cryptographically
    bound to both the prior chain state and the specific event being
    appended, so replaying the token on a different append (or a
    different chain) fails hash binding at verification.
    """
    hasher = hashlib.sha256()
    hasher.update(tail_hash.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(event_data)
    hasher.update(b"\x00")
    hasher.update(signature)
    return hasher.digest()


# Dedicated thread pool for async-to-sync bridging.  A single worker
# avoids contention and keeps chain appends sequential.
_SIGNING_EXECUTOR_PREFIX = "audit-sign"
_SIGNING_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix=_SIGNING_EXECUTOR_PREFIX,
)


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
        self._append_callback: AppendCallback | None = None

    def set_append_callback(
        self,
        callback: AppendCallback | None,
    ) -> None:
        """Register a callback invoked after every append attempt.

        Passed ``(status, chain_depth, timestamp_unix)`` where status
        is ``"signed"`` (successful TSA) / ``"fallback"`` (local
        clock) / ``"error"`` (append failed entirely). Used by
        startup wiring to push :meth:`PrometheusCollector.record_audit_append`
        without coupling the sink to AppState.

        Thread safety: invoked under the sink's lock inside
        :meth:`emit`; the callback must be fast and non-blocking.

        Raises:
            TypeError: When ``callback`` is not callable (and not
                ``None``). Failing fast at registration mirrors
                :meth:`OtlpHandler.set_export_callback` and catches
                wiring bugs before they surface mid-emit.
        """
        # Callers satisfy this at type-check time; the runtime guard
        # catches misuse from untyped wiring (tests, config loaders,
        # dynamic callers). mypy flags the check as unreachable under
        # the declared signature, which is exactly the point -- the
        # ignore preserves the defensive assertion.
        if callback is not None and not callable(callback):  # type: ignore[unreachable, unused-ignore]
            msg = "append callback must be callable or None"
            raise TypeError(msg)  # type: ignore[unreachable, unused-ignore]
        self._append_callback = callback

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

        Re-entry from the sink's own signing thread is suppressed:
        the signer, TSA client, and any helper they call log events
        of their own (including ``security.timestamp.*``) that would
        otherwise loop back into this handler through the logging
        hierarchy and eventually deadlock on the single-worker
        ``_SIGNING_EXECUTOR``. Records originating from a thread
        named ``audit-sign`` are dropped here and handled by the
        sibling handlers on the same logger.

        Args:
            record: Log record from the logging framework.
        """
        if threading.current_thread().name.startswith(_SIGNING_EXECUTOR_PREFIX):
            return

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

            # Bind the TSA token to this specific append by stamping
            # the concatenation of the current tail hash, the event
            # hash, and the signature. Reading tail_hash here (not
            # under the append lock) is safe: _SIGNING_EXECUTOR is a
            # single worker, so appends are already serialised, and
            # other emit() calls are blocked on future.result above.
            binding_payload = _build_binding_payload(
                tail_hash=self._chain.tail_hash,
                event_data=data,
                signature=signed.signature,
            )
            ts_future = _SIGNING_EXECUTOR.submit(
                asyncio.run,
                self._timestamp_provider.get_timestamp(binding_payload),
            )
            ts_result = ts_future.result(timeout=5.0)

            with self._lock:
                self._chain.append(
                    event_data=data,
                    signature=signed.signature,
                    timestamp=ts_result.timestamp,
                )
                depth = len(self._chain.entries)
            # The provider tells us its origin directly; we only
            # record "signed" when a TSA actually signed the
            # timestamp -- fallbacks from TSA failure and plain
            # local-clock providers both report non-signed status
            # so audit-chain append metrics accurately reflect how
            # many events received a cryptographic timestamp.
            status = "signed" if ts_result.source == "signed" else "fallback"
            self._invoke_append_callback(
                status,
                depth,
                ts_result.timestamp.timestamp(),
            )

        except MemoryError, RecursionError:
            raise
        except Exception:
            # Use a non-audited event prefix (``audit_chain.*``) so
            # this error log can't loop back through ``emit()`` and
            # recurse on the single-worker signing executor.
            logger.error(
                AUDIT_CHAIN_EMIT_ERROR,
                exc_info=True,
            )
            self._invoke_append_callback("error", 0, 0.0)

    def _invoke_append_callback(
        self,
        status: str,
        chain_depth: int,
        timestamp_unix: float,
    ) -> None:
        """Call the registered append callback, swallowing errors.

        A callback failure must never break the audit chain; we log
        to the module logger instead of re-raising.
        """
        callback = self._append_callback
        if callback is None:
            return
        try:
            callback(status, chain_depth, timestamp_unix)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                AUDIT_CHAIN_CALLBACK_ERROR,
                exc_info=True,
            )
