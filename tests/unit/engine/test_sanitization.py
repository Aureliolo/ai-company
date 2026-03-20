"""Tests for engine message sanitization helpers."""

import pytest

from synthorg.engine.sanitization import sanitize_message

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestSanitizeMessagePaths:
    """Path patterns are redacted."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param(
                r"Failed at C:\Users\dev\project\secret.key",
                "Failed at [REDACTED_PATH]",
                id="windows_path",
            ),
            pytest.param(
                "Config loaded from /home/user/.ssh/id_rsa",
                "Config loaded from [REDACTED_PATH]",
                id="unix_home",
            ),
            pytest.param(
                "Log at /var/log/synthorg/engine.log",
                "Log at [REDACTED_PATH]",
                id="unix_var",
            ),
            pytest.param(
                "Wrote to /tmp/scratch/data.json",
                "Wrote to [REDACTED_PATH]",
                id="unix_tmp",
            ),
            pytest.param(
                "Reading /etc/synthorg/config.yaml",
                "Reading [REDACTED_PATH]",
                id="unix_etc",
            ),
            pytest.param(
                "Binary at /opt/synthorg/bin/run",
                "Binary at [REDACTED_PATH]",
                id="unix_opt",
            ),
            pytest.param(
                "Running from /app/src/main.py",
                "Running from [REDACTED_PATH]",
                id="unix_app",
            ),
            pytest.param(
                "Found ./config/secrets.yaml",
                "Found [REDACTED_PATH]",
                id="relative_dot",
            ),
            pytest.param(
                "Resolved ../parent/key.pem",
                "Resolved [REDACTED_PATH]",
                id="relative_dotdot",
            ),
            pytest.param(
                "Leaked /proc/self/environ",
                "Leaked [REDACTED_PATH]",
                id="unix_proc",
            ),
            pytest.param(
                "Secret at /run/secrets/db_password",
                "Secret at [REDACTED_PATH]",
                id="unix_run_secrets",
            ),
            pytest.param(
                "Mount at /mnt/efs/data/keys.pem",
                "Mount at [REDACTED_PATH]",
                id="unix_mnt",
            ),
            pytest.param(
                r"Share at \\server\share\secrets\key.pem",
                "Share at [REDACTED_PATH]",
                id="unc_backslash",
            ),
            pytest.param(
                "Share at //server/share/path",
                "Share at [REDACTED_PATH]",
                id="unc_forward",
            ),
        ],
    )
    def test_path_redacted(self, raw: str, expected: str) -> None:
        assert sanitize_message(raw) == expected

    def test_single_char_after_slash_not_redacted(self) -> None:
        raw = "option /n is invalid"
        assert sanitize_message(raw) == raw

    def test_standalone_slash_not_redacted(self) -> None:
        raw = "choose a / b"
        assert sanitize_message(raw) == raw


@pytest.mark.unit
class TestSanitizeMessageUrls:
    """URL patterns are redacted."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param(
                "Request to https://api.example.com/v1/models failed",
                "Request to [REDACTED_URL] failed",
                id="https_url",
            ),
            pytest.param(
                "Connecting to http://localhost:8080/health",
                "Connecting to [REDACTED_URL]",
                id="http_url",
            ),
            pytest.param(
                "Auth at https://provider.io/token?key=abc123",
                "Auth at [REDACTED_URL]",
                id="url_with_query",
            ),
            pytest.param(
                "DB at postgresql://user:pass@host:5432/db",
                "DB at [REDACTED_URL]",
                id="postgresql_uri",
            ),
            pytest.param(
                "Cache at redis://:secret@redis-host:6379/0",
                "Cache at [REDACTED_URL]",
                id="redis_uri",
            ),
            pytest.param(
                "Store at mongodb://admin:pass@mongo:27017/data",
                "Store at [REDACTED_URL]",
                id="mongodb_uri",
            ),
        ],
    )
    def test_url_redacted(self, raw: str, expected: str) -> None:
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
        assert len(sanitize_message(raw)) <= 200

    def test_custom_max_length(self) -> None:
        raw = "a" * 300
        assert len(sanitize_message(raw, max_length=50)) <= 50

    def test_short_message_unchanged(self) -> None:
        raw = "simple error"
        assert sanitize_message(raw) == "simple error"

    def test_zero_max_length(self) -> None:
        assert sanitize_message("hello", max_length=0) == "details redacted"


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
