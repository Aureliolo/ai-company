"""Docker daemon enrichment for telemetry startup events.

Queries the Docker daemon's ``/info`` endpoint and ``/containers``
list (via the same ``aiodocker`` client the sandbox layer uses) so
operators can distinguish deployments by host OS / Docker version /
storage driver / GPU-capability / fine-tune state without joining
on a separate system. The socket lives at ``/var/run/docker.sock``,
which the ``compose.override.yml`` sandbox overlay bind-mounts into
the backend container. In the no-sandbox configuration the socket
is absent and every fetch path degrades to a single
``docker_info_available=False`` marker so the deployment still
shows up in telemetry without looking broken.

GPU inventory (model names, VRAM, driver version) is intentionally
**not** probed from the backend. The backend base image
(``python:3.14.3-slim``) has no NVIDIA tooling, and the
``compose.yml`` topology scopes GPU access to the ``fine-tune``
service only. ``nvidia-smi`` is injected by the NVIDIA Container
Toolkit at launch time -- only into containers that request GPUs.
Running the probe from the backend would emit ``no_nvidia_smi`` on
every deployment. The achievable backend-side GPU signal is the
host-capability flag ``docker_gpu_runtime_available`` derived from
``/info.Runtimes``; richer GPU inventory belongs to the Go CLI,
which runs on the host and can invoke ``nvidia-smi`` natively.

Only a hand-picked subset of ``/info`` keys is exported. The raw
response includes host machine names, container IDs, labels, and
swarm cluster membership details that would leak private data
through the telemetry channel. Keep this module's allowlist and
the :mod:`synthorg.telemetry.privacy` scrubber's allowlist in
sync -- both are the scrub surface.
"""

import os
from typing import TYPE_CHECKING, Final

from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import TELEMETRY_REPORT_FAILED

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)

_DOCKER_SOCKET_PATH: Final[str] = "/var/run/docker.sock"

_MAX_STRING_LENGTH: Final[int] = 64
"""Matches the PrivacyScrubber cap; keeps long OS strings in range."""

_REASON_SOCKET_NOT_MOUNTED: Final[str] = "socket_not_mounted"
_REASON_AIODOCKER_NOT_INSTALLED: Final[str] = "aiodocker_not_installed"
_REASON_DAEMON_UNREACHABLE: Final[str] = "daemon_unreachable"

_NVIDIA_RUNTIME_NAME: Final[str] = "nvidia"
"""Runtime key the NVIDIA Container Toolkit registers with Docker."""


def _truncate(value: object) -> str:
    """Coerce to str and truncate to the scrubber's cap."""
    text = str(value)
    return text[:_MAX_STRING_LENGTH]


def _unavailable(reason: str) -> dict[str, str | int | float | bool]:
    """Produce the uniform "no daemon info" marker payload.

    Returns:
        A dict suitable to merge into a :class:`TelemetryEvent`'s
        ``properties``. ``docker_info_available`` is always ``False``
        so dashboards can filter the two states cleanly;
        ``docker_info_unavailable_reason`` is a categorical string
        (never a raw exception message) for grouping.
    """
    return {
        "docker_info_available": False,
        "docker_info_unavailable_reason": reason,
    }


def _extract(info: Mapping[str, object]) -> dict[str, str | int | float | bool]:
    """Project daemon ``/info`` into the telemetry-safe subset.

    Only keys on the hand-picked allowlist are returned. Missing
    keys are silently dropped (different Docker versions expose
    different fields). Host machine names, container IDs, and
    labels are excluded by omission, not by filtering.

    Also derives ``docker_gpu_runtime_nvidia_available`` from
    ``Runtimes`` so dashboards can split GPU-capable hosts without
    probing ``nvidia-smi`` from a container that doesn't have GPU
    access (the default backend topology). AMD / Intel GPU
    detection intentionally lives outside this path -- neither
    registers a Docker runtime, so there is no daemon-level signal
    to read. Host-side GPU inventory (model, VRAM, driver version)
    is delegated to the Go CLI which probes the host directly.
    """
    result: dict[str, str | int | float | bool] = {
        "docker_info_available": True,
    }

    str_keys: Final[tuple[tuple[str, str], ...]] = (
        ("ServerVersion", "docker_server_version"),
        ("OperatingSystem", "docker_operating_system"),
        ("OSType", "docker_os_type"),
        ("OSVersion", "docker_os_version"),
        ("Architecture", "docker_architecture"),
        ("KernelVersion", "docker_kernel_version"),
        ("Driver", "docker_storage_driver"),
        ("DefaultRuntime", "docker_default_runtime"),
        ("Isolation", "docker_isolation"),
    )
    for src, dst in str_keys:
        raw = info.get(src)
        if raw is None or raw == "":
            continue
        result[dst] = _truncate(raw)

    int_keys: Final[tuple[tuple[str, str], ...]] = (
        ("NCPU", "docker_ncpu"),
        ("MemTotal", "docker_mem_total"),
    )
    for src, dst in int_keys:
        raw = info.get(src)
        if isinstance(raw, bool) or not isinstance(raw, int):
            continue
        result[dst] = raw

    runtimes = info.get("Runtimes")
    result["docker_gpu_runtime_nvidia_available"] = bool(
        isinstance(runtimes, dict) and _NVIDIA_RUNTIME_NAME in runtimes,
    )

    return result


async def fetch_docker_info() -> dict[str, str | int | float | bool]:
    """Fetch a telemetry-safe snapshot of Docker daemon ``/info``.

    Returns the allowlisted fields with
    ``docker_info_available=True`` when the daemon responds. On
    every failure path (socket not bind-mounted, ``aiodocker`` not
    installed, daemon unreachable, daemon returned an error), the
    payload collapses to the ``docker_info_available=False`` marker
    with a categorical reason. The caller merges the result straight
    into a :class:`TelemetryEvent`'s ``properties``.

    Never raises: telemetry must not affect the main application.
    """
    # Local stat on /var/run/docker.sock is O(1) and non-blocking in
    # practice; the ASYNC240 trio.Path recommendation does not fit
    # because the project is asyncio-only. PTH110 is suppressed so
    # tests can monkeypatch ``host_info.os.path.exists`` without
    # chasing a ``Path.exists`` indirection.
    if not os.path.exists(_DOCKER_SOCKET_PATH):  # noqa: PTH110, ASYNC240
        return _unavailable(_REASON_SOCKET_NOT_MOUNTED)

    try:
        import aiodocker  # type: ignore[import-untyped,unused-ignore]  # noqa: PLC0415
    except ImportError:
        logger.debug(
            TELEMETRY_REPORT_FAILED,
            detail="docker_info_aiodocker_missing",
        )
        return _unavailable(_REASON_AIODOCKER_NOT_INSTALLED)

    try:
        client = aiodocker.Docker()
    except Exception as exc:
        logger.warning(
            TELEMETRY_REPORT_FAILED,
            detail="docker_info_client_construction",
            error_type=type(exc).__name__,
        )
        return _unavailable(_REASON_DAEMON_UNREACHABLE)

    try:
        info = await client.system.info()
    except Exception as exc:
        logger.warning(
            TELEMETRY_REPORT_FAILED,
            detail="docker_info_fetch_failed",
            error_type=type(exc).__name__,
        )
        return _unavailable(_REASON_DAEMON_UNREACHABLE)
    finally:
        try:
            await client.close()
        except Exception as exc:
            logger.debug(
                TELEMETRY_REPORT_FAILED,
                detail="docker_info_client_close",
                error_type=type(exc).__name__,
            )

    if not isinstance(info, dict):
        return _unavailable(_REASON_DAEMON_UNREACHABLE)

    return _extract(info)
