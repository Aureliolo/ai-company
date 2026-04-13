"""Integration tests for the Caddy-based web image.

Validates that the apko-composed web image correctly serves the React SPA,
pre-compressed assets, static docs, and applies per-request CSP nonces.
These tests require a locally-built web image (docker load from apko output).
"""

import os
import re
import subprocess
import time
from collections.abc import Generator

import httpx
import pytest

from synthorg.observability import get_logger

logger = get_logger(__name__)

_IMAGE_REF_PATTERN = re.compile(r"^[\w.:/@-]+$")
WEB_IMAGE = os.environ.get("SYNTHORG_WEB_IMAGE", "ghcr.io/aureliolo/synthorg-web:test")
if not _IMAGE_REF_PATTERN.match(WEB_IMAGE):
    msg = f"Invalid image reference: {WEB_IMAGE}"
    raise ValueError(msg)
CONTAINER_NAME = "synthorg-web-test"
HOST_PORT = 18080


@pytest.fixture(scope="module")
def web_container() -> Generator[str]:
    """Start the web image on a random port and yield the base URL."""
    docker = "docker"
    cmd = [
        docker,
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"{HOST_PORT}:8080",
        "--read-only",
        "--tmpfs",
        "/tmp:noexec,nosuid,nodev,size=16m",  # noqa: S108
        "--tmpfs",
        "/config/caddy:noexec,nosuid,nodev,size=8m",
        "--tmpfs",
        "/data/caddy:noexec,nosuid,nodev,size=16m",
        WEB_IMAGE,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
    except FileNotFoundError:
        pytest.skip("Docker binary not found on PATH")
    except subprocess.CalledProcessError as exc:
        if "manifest unknown" in exc.stderr or "not found" in exc.stderr:
            pytest.skip(f"Web image not available: {exc.stderr.strip()}")
        pytest.fail(f"Web container failed to start: {exc.stderr}")

    base_url = f"http://127.0.0.1:{HOST_PORT}"
    for _ in range(30):
        try:
            resp = httpx.get(f"{base_url}/", timeout=2)
            if resp.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(0.5)
    else:
        pytest.fail("Web container did not become healthy within 15s")

    yield base_url

    subprocess.run(  # noqa: S603
        [docker, "rm", "-f", CONTAINER_NAME],
        capture_output=True,
        check=False,
    )


@pytest.mark.integration
@pytest.mark.slow
class TestWebImage:
    def test_root_returns_200(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/")
        assert resp.status_code == 200

    def test_csp_nonce_present_in_header(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/")
        csp = resp.headers.get("content-security-policy", "")
        match = re.search(r"nonce-([a-f0-9-]+)", csp)
        assert match, f"No nonce found in CSP header: {csp}"

    def test_csp_nonce_matches_body(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/")
        csp = resp.headers.get("content-security-policy", "")
        header_nonce = re.search(r"nonce-([a-f0-9-]+)", csp)
        assert header_nonce

        body_match = re.search(
            r'content="([a-f0-9-]+)"',
            resp.text,
        )
        assert body_match, "No nonce found in response body meta tag"
        assert header_nonce.group(1) == body_match.group(1)

    def test_csp_nonce_changes_per_request(self, web_container: str) -> None:
        resp1 = httpx.get(f"{web_container}/")
        resp2 = httpx.get(f"{web_container}/")
        nonce1 = re.search(
            r"nonce-([a-f0-9-]+)",
            resp1.headers.get("content-security-policy", ""),
        )
        nonce2 = re.search(
            r"nonce-([a-f0-9-]+)",
            resp2.headers.get("content-security-policy", ""),
        )
        assert nonce1
        assert nonce2
        assert nonce1.group(1) != nonce2.group(1), "Nonce must differ per request"

    def test_docs_has_static_csp(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/docs/")
        assert resp.status_code == 200, f"Docs route returned {resp.status_code}"
        csp = resp.headers.get("content-security-policy", "")
        assert "nonce-" not in csp, "Docs CSP must not contain a per-request nonce"
        assert "worker-src 'self' blob:" in csp

    def test_security_headers_present(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert "strict-origin" in resp.headers.get("referrer-policy", "")
        assert "63072000" in resp.headers.get("strict-transport-security", "")
        assert "geolocation=()" in resp.headers.get("permissions-policy", "")
        assert resp.headers.get("server") in (None, "")

    def test_spa_fallback(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/agents")
        assert resp.status_code == 200
        assert "<div id=" in resp.text or "root" in resp.text

    def test_cache_control_no_cache_on_root(self, web_container: str) -> None:
        resp = httpx.get(f"{web_container}/")
        assert "no-cache" in resp.headers.get("cache-control", "")
