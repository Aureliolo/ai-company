"""Errors specific to distributed bus backends.

Generic ``MessageBus`` errors live in ``synthorg.communication.errors``
and are raised by both the in-memory and distributed backends. This
module holds errors that only make sense for distributed transports
(connection failures, stream setup failures, etc.).
"""

from synthorg.communication.errors import CommunicationError


class BusConnectionError(CommunicationError):
    """Raised when a distributed bus backend cannot connect to its transport.

    Signals a non-retryable failure at the transport layer, e.g. the
    NATS URL is unreachable or credentials are rejected. Callers that
    catch this should surface it as a fatal startup error.
    """


class BusStreamError(CommunicationError):
    """Raised when a distributed bus backend cannot set up or query a stream.

    Covers JetStream stream creation failures, durable consumer creation
    failures, and KV bucket setup failures. Context typically includes
    ``stream`` or ``bucket`` keys identifying the failing primitive.
    """
