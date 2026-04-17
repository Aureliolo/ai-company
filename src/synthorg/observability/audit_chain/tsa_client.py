"""RFC 3161 Time-Stamp Authority client for the audit chain.

Issues a timestamp request for a SHA-256 (or SHA-512) hash of a
caller-supplied blob and returns the TSA-signed timestamp. Wraps
:mod:`rfc3161_client` (PyCA) for ASN.1 encode/decode and defers HTTP
transport to :mod:`httpx`.

The client verifies two invariants before returning a
:class:`TimestampToken`:

1. **Hash binding**: the response's ``MessageImprint`` matches the
   request's hash and algorithm (replay/tamper detection).
2. **Nonce echo**: the response's nonce matches the random 64-bit
   nonce the builder generated for the request.

Cert-chain + SignedData signature verification is delegated to the
caller via :meth:`TsaClient.request_timestamp`'s ``trusted_roots``
parameter -- when provided, the library's :class:`Verifier` validates
the CMS SignedData structure against those PEM-encoded roots.

Reference: RFC 3161, RFC 5816.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import rfc3161_client
from cryptography import x509
from rfc3161_client import TimestampRequestBuilder
from rfc3161_client import base as _rfc_base
from rfc3161_client import tsp as _rfc_tsp

if TYPE_CHECKING:
    from collections.abc import Iterable

from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_TIMESTAMP_GRANTED,
    SECURITY_TIMESTAMP_HASH_MISMATCH,
    SECURITY_TIMESTAMP_REJECTED,
    SECURITY_TIMESTAMP_REQUESTED,
    SECURITY_TIMESTAMP_SIGNATURE_INVALID,
    SECURITY_TIMESTAMP_TIMEOUT,
)

logger = get_logger(__name__)

_HASH_ALGORITHMS: dict[str, Any] = {
    "sha256": _rfc_base.HashAlgorithm.SHA256,
    "sha512": _rfc_base.HashAlgorithm.SHA512,
}

_DIGEST_FACTORY = {
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}

# Content-Type per RFC 3161 section 3.4.
_REQ_CONTENT_TYPE = "application/timestamp-query"
_RESP_CONTENT_TYPE = "application/timestamp-reply"


class TsaError(Exception):
    """Base class for TSA client failures.

    Every subclass signals a specific failure mode so the audit
    chain's :class:`ResilientTimestampProvider` can tag the fallback
    log with a precise reason and operators can build alerts per
    class.
    """


class TsaTimeoutError(TsaError):
    """TSA did not respond within the configured deadline."""


class TsaTransportError(TsaError):
    """Network or HTTP transport failure (4xx/5xx, DNS, TLS)."""


class TsaProtocolError(TsaError):
    """The TSA response is malformed or the PKI status is not granted."""


class TsaHashMismatchError(TsaProtocolError):
    """Response ``MessageImprint`` does not match the request hash.

    Treated as a security incident -- the TSA either stamped the
    wrong payload or an on-path attacker swapped the response.
    """


class TsaNonceMismatchError(TsaProtocolError):
    """Response nonce does not match the request nonce (replay guard)."""


class TsaSignatureError(TsaProtocolError):
    """CMS ``SignedData`` signature does not verify against trusted roots."""


@dataclass(frozen=True, slots=True)
class TimestampToken:
    """Fully parsed and verified RFC 3161 timestamp response.

    Attributes:
        timestamp: UTC datetime parsed from ``TSTInfo.genTime``.
        serial_number: TSA-assigned serial number.
        hash_algorithm: Hash algorithm name (``"sha256"`` / ``"sha512"``).
        hashed_message: The hash bytes that were stamped (matches
            ``MessageImprint.hashedMessage``).
        tsa_url: The endpoint that issued the timestamp.
        raw_response: The full DER-encoded TSA response (persisted
            with the audit chain record for offline re-verification).
    """

    timestamp: datetime
    serial_number: int
    hash_algorithm: str
    hashed_message: bytes
    tsa_url: str
    raw_response: bytes


class TsaClient:
    """RFC 3161 timestamp client with hash-binding verification.

    The client is safe to share across tasks -- each call generates
    its own nonce and httpx request. Pass a shared
    :class:`httpx.AsyncClient` for connection pooling; the client
    never closes an injected http client (the caller owns it).

    Args:
        tsa_url: HTTPS endpoint of the RFC 3161 TSA.
        timeout_sec: HTTP request timeout. Upper-bounded by the
            audit chain's 5.0s ``_SIGNING_EXECUTOR`` deadline.
        hash_algorithm: Hash algorithm for the message imprint
            (``"sha256"`` or ``"sha512"``).
        trusted_roots: Iterable of PEM-encoded root certs. When
            supplied, the library verifies the CMS SignedData
            signature; when empty, signature verification is
            skipped. Supplying roots is strongly recommended for
            compliance-relevant deployments.
        http_client: Optional shared ``httpx.AsyncClient`` (owned by
            caller). When ``None``, the client constructs a
            per-call client with the configured timeout.
    """

    def __init__(
        self,
        tsa_url: str,
        *,
        timeout_sec: float = 5.0,
        hash_algorithm: str = "sha256",
        trusted_roots: Iterable[bytes] = (),
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if hash_algorithm not in _HASH_ALGORITHMS:
            msg = (
                f"Unsupported hash algorithm {hash_algorithm!r}; "
                f"expected one of {sorted(_HASH_ALGORITHMS)}"
            )
            raise ValueError(msg)
        if timeout_sec <= 0:
            msg = "timeout_sec must be positive"
            raise ValueError(msg)
        self._tsa_url = tsa_url
        self._timeout_sec = timeout_sec
        self._hash_algorithm = hash_algorithm
        self._trusted_roots: tuple[x509.Certificate, ...] = tuple(
            _load_root_cert(pem) for pem in trusted_roots
        )
        self._http_client = http_client
        self._owns_http_client = http_client is None

    @property
    def tsa_url(self) -> str:
        """Return the configured TSA endpoint."""
        return self._tsa_url

    @property
    def hash_algorithm(self) -> str:
        """Return the configured hash algorithm name."""
        return self._hash_algorithm

    async def request_timestamp(self, data: bytes) -> TimestampToken:
        """Hash *data*, POST a TSA request, verify + return the token.

        The method is idempotent-safe (each call generates an
        independent nonce) but the TSA may allocate a unique serial
        per request; callers should treat ``TimestampToken`` as a
        unique artefact.

        Args:
            data: Arbitrary bytes to timestamp.

        Returns:
            A verified :class:`TimestampToken`.

        Raises:
            TsaTimeoutError: Deadline exceeded during transport.
            TsaTransportError: Network, DNS, TLS, 4xx, or 5xx.
            TsaProtocolError: Malformed ASN.1 or non-granted PKI status.
            TsaHashMismatchError: ``MessageImprint`` mismatch.
            TsaNonceMismatchError: Response nonce mismatch.
            TsaSignatureError: CMS signature invalid (only raised
                when ``trusted_roots`` was supplied to __init__).
        """
        digest = _DIGEST_FACTORY[self._hash_algorithm](data).digest()
        request = (
            TimestampRequestBuilder()
            .data(data)
            .hash_algorithm(_HASH_ALGORITHMS[self._hash_algorithm])
            .nonce(nonce=True)
            .cert_request(cert_request=True)
            .build()
        )
        request_nonce = int(request.nonce) if request.nonce is not None else 0
        logger.info(
            SECURITY_TIMESTAMP_REQUESTED,
            tsa_url=self._tsa_url,
            hash_algorithm=self._hash_algorithm,
            nonce=request_nonce,
        )
        raw_response = await self._post(request.as_bytes())
        response = _decode_response(raw_response)
        _check_pki_status(response, self._tsa_url)
        tst_info = response.tst_info
        _check_hash_binding(tst_info, digest, self._hash_algorithm, self._tsa_url)
        _check_nonce(tst_info, request_nonce, self._tsa_url)
        if self._trusted_roots:
            _verify_signature(
                response,
                hashed_message=digest,
                trusted_roots=self._trusted_roots,
                tsa_url=self._tsa_url,
            )
        timestamp = _gen_time_to_datetime(tst_info.gen_time)
        logger.info(
            SECURITY_TIMESTAMP_GRANTED,
            tsa_url=self._tsa_url,
            serial_number=tst_info.serial_number,
            timestamp=timestamp.isoformat(),
        )
        return TimestampToken(
            timestamp=timestamp,
            serial_number=int(tst_info.serial_number),
            hash_algorithm=self._hash_algorithm,
            hashed_message=bytes(tst_info.message_imprint.message),
            tsa_url=self._tsa_url,
            raw_response=raw_response,
        )

    async def aclose(self) -> None:
        """Close the internal httpx client (no-op if caller-injected)."""
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _post(self, body: bytes) -> bytes:
        """POST a DER-encoded request to the TSA, return DER response.

        Creates a per-call client when no shared one was injected, so
        lazy initialisation does not require an event loop at
        construction time.
        """
        client = self._http_client
        created_for_call = False
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout_sec)
            self._http_client = client
            created_for_call = True
        try:
            response = await client.post(
                self._tsa_url,
                content=body,
                headers={"Content-Type": _REQ_CONTENT_TYPE},
                timeout=self._timeout_sec,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                SECURITY_TIMESTAMP_TIMEOUT,
                tsa_url=self._tsa_url,
                timeout_sec=self._timeout_sec,
            )
            msg = f"TSA request timed out after {self._timeout_sec}s"
            raise TsaTimeoutError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"TSA transport failure: {type(exc).__name__}"
            raise TsaTransportError(msg) from exc
        finally:
            if created_for_call and not self._owns_http_client:
                await client.aclose()
        if response.status_code >= 400:  # noqa: PLR2004
            msg = f"TSA returned HTTP {response.status_code}: {response.reason_phrase}"
            raise TsaTransportError(msg)
        content_type = response.headers.get("Content-Type", "")
        if _RESP_CONTENT_TYPE not in content_type:
            msg = (
                f"TSA returned unexpected Content-Type {content_type!r}; "
                f"expected {_RESP_CONTENT_TYPE!r}"
            )
            raise TsaProtocolError(msg)
        return response.content


def _decode_response(raw: bytes) -> Any:
    try:
        return rfc3161_client.decode_timestamp_response(raw)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        msg = f"TSA response is not a valid ASN.1 TimeStampResp: {exc}"
        raise TsaProtocolError(msg) from exc


def _check_pki_status(response: Any, tsa_url: str) -> None:
    status = response.status
    if status in {
        _rfc_tsp.PKIStatus.GRANTED,
        _rfc_tsp.PKIStatus.GRANTED_WITH_MODS,
    }:
        return
    status_string = getattr(response, "status_string", None)
    logger.warning(
        SECURITY_TIMESTAMP_REJECTED,
        tsa_url=tsa_url,
        pki_status=status.name,
        status_string=status_string,
    )
    msg = f"TSA rejected request: status={status.name} {status_string!r}"
    raise TsaProtocolError(msg)


def _check_hash_binding(
    tst_info: Any,
    expected_digest: bytes,
    hash_algorithm: str,
    tsa_url: str,
) -> None:
    message_imprint = tst_info.message_imprint
    actual = bytes(message_imprint.message)
    if actual != expected_digest:
        logger.error(
            SECURITY_TIMESTAMP_HASH_MISMATCH,
            tsa_url=tsa_url,
            hash_algorithm=hash_algorithm,
            expected_length=len(expected_digest),
            actual_length=len(actual),
        )
        msg = (
            "TSA response MessageImprint does not match request hash "
            "(possible on-path tampering or TSA misbehaviour)"
        )
        raise TsaHashMismatchError(msg)


def _check_nonce(tst_info: Any, expected_nonce: int, tsa_url: str) -> None:
    actual = int(tst_info.nonce) if tst_info.nonce is not None else None
    if actual != expected_nonce:
        logger.error(
            SECURITY_TIMESTAMP_HASH_MISMATCH,
            tsa_url=tsa_url,
            reason="nonce_mismatch",
            expected_nonce=expected_nonce,
            actual_nonce=actual,
        )
        msg = "TSA response nonce does not match request nonce (replay guard)"
        raise TsaNonceMismatchError(msg)


def _verify_signature(
    response: Any,
    *,
    hashed_message: bytes,
    trusted_roots: tuple[x509.Certificate, ...],
    tsa_url: str,
) -> None:
    """Verify the CMS SignedData signature against *trusted_roots*.

    Uses :class:`rfc3161_client.VerifierBuilder` which validates the
    TSA cert chain and the SignedData signature over TSTInfo. Any
    failure raises :exc:`TsaSignatureError`.
    """
    try:
        builder = rfc3161_client.VerifierBuilder()
        for root_cert in trusted_roots:
            builder = builder.add_root_certificate(root_cert)
        verifier = builder.build()
        verifier.verify(response, hashed_message)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.exception(
            SECURITY_TIMESTAMP_SIGNATURE_INVALID,
            tsa_url=tsa_url,
            error=type(exc).__name__,
        )
        msg = f"TSA signature verification failed: {exc}"
        raise TsaSignatureError(msg) from exc


def _load_root_cert(pem_bytes: bytes) -> x509.Certificate:
    """Parse a PEM-encoded certificate into an :class:`x509.Certificate`.

    Raises:
        ValueError: If *pem_bytes* does not contain a valid PEM
            certificate.
    """
    try:
        return x509.load_pem_x509_certificate(pem_bytes)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        msg = f"Invalid trusted-root PEM: {exc}"
        raise ValueError(msg) from exc


def _gen_time_to_datetime(gen_time: Any) -> datetime:
    """Coerce a TSTInfo ``gen_time`` into a UTC-aware datetime."""
    if isinstance(gen_time, datetime):
        return gen_time if gen_time.tzinfo is not None else gen_time.replace(tzinfo=UTC)
    msg = f"Unexpected gen_time type: {type(gen_time).__name__}"
    raise TsaProtocolError(msg)
