"""Tests for engine message sanitization helpers."""

import pytest

from synthorg.engine.sanitization import sanitize_message

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestSanitizeMessagePaths:
    """Path patterns are redacted."""

    @pytest.mark.parametrize(
        ("label", "raw", "expected"),
        [
            (
                "windows_path",
                r"Failed at C:\Users\dev\project\secret.key",
                "Failed at [REDACTED_PATH]",
            ),
            (
                "unix_home",
                "Config loaded from /home/user/.ssh/id_rsa",
                "Config loaded from [REDACTED_PATH]",
            ),
            (
                "unix_var",
                "Log at /var/log/synthorg/engine.log",
                "Log at [REDACTED_PATH]",
            ),
            (
                "unix_tmp",
                "Wrote to /tmp/scratch/data.json",
                "Wrote to [REDACTED_PATH]",
            ),
            (
                "unix_etc",
                "Reading /etc/synthorg/config.yaml",
                "Reading [REDACTED_PATH]",
            ),
            (
                "unix_opt",
                "Binary at /opt/synthorg/bin/run",
                "Binary at [REDACTED_PATH]",
            ),
            (
                "unix_app",
                "Running from /app/src/main.py",
                "Running from [REDACTED_PATH]",
            ),
            (
                "relative_dot",
                "Found ./config/secrets.yaml",
                "Found [REDACTED_PATH]",
            ),
            (
                "relative_dotdot",
                "Resolved ../parent/key.pem",
                "Resolved [REDACTED_PATH]",
            ),
        ],
    )
    def test_path_redacted(self, label: str, raw: str, expected: str) -> None:
        assert sanitize_message(raw) == expected


@pytest.mark.unit
class TestSanitizeMessageUrls:
    """URL patterns are redacted."""

    @pytest.mark.parametrize(
        ("label", "raw", "expected"),
        [
            (
                "https_url",
                "Request to https://api.example.com/v1/models failed",
                "Request to [REDACTED_URL] failed",
            ),
            (
                "http_url",
                "Connecting to http://localhost:8080/health",
                "Connecting to [REDACTED_URL]",
            ),
            (
                "url_with_query",
                "Auth at https://provider.io/token?key=abc123",
                "Auth at [REDACTED_URL]",
            ),
        ],
    )
    def test_url_redacted(self, label: str, raw: str, expected: str) -> None:
        assert sanitize_message(raw) == expected


@pytest.mark.unit
class TestSanitizeMessageMixed:
    """Messages with both paths and URLs have both redacted."""

    def test_path_and_url_both_redacted(self) -> None:
        raw = r"Error in C:\app\run.py calling https://api.example.com/v1"
        result = sanitize_message(raw)
        assert "[REDACTED_PATH]" in result
        assert "[REDACTED_URL]" in result
        assert "C:\\app" not in result
        assert "https://" not in result


@pytest.mark.unit
class TestSanitizeMessageTruncation:
    """Length limiting and custom max_length."""

    def test_default_max_length_200(self) -> None:
        raw = "a" * 300
        assert len(sanitize_message(raw)) == 200

    def test_custom_max_length(self) -> None:
        raw = "a" * 300
        assert len(sanitize_message(raw, max_length=50)) == 50

    def test_short_message_unchanged(self) -> None:
        raw = "simple error"
        assert sanitize_message(raw) == "simple error"


@pytest.mark.unit
class TestSanitizeMessageNonPrintable:
    """Non-printable characters are stripped."""

    def test_non_printable_stripped(self) -> None:
        raw = "error\x00with\x01control\x02chars"
        result = sanitize_message(raw)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert result == "errorwithcontrolchars"


@pytest.mark.unit
class TestSanitizeMessageFallback:
    """Edge cases that produce the 'details redacted' fallback."""

    def test_empty_string(self) -> None:
        assert sanitize_message("") == "details redacted"

    def test_all_non_alphanumeric(self) -> None:
        assert sanitize_message("!@#$%^&*()") == "details redacted"

    def test_only_non_printable(self) -> None:
        assert sanitize_message("\x00\x01\x02") == "details redacted"


@pytest.mark.unit
class TestSanitizeMessagePassthrough:
    """Clean messages pass through unchanged."""

    def test_clean_message(self) -> None:
        raw = "LLM provider returned rate limit error"
        assert sanitize_message(raw) == raw

    def test_message_with_numbers(self) -> None:
        raw = "Timeout after 30 seconds on attempt 3"
        assert sanitize_message(raw) == raw
