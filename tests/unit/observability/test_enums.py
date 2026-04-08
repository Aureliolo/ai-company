"""Tests for observability-specific enumerations."""

import pytest

from synthorg.observability.enums import (
    LogLevel,
    OtlpProtocol,
    RotationStrategy,
    SinkType,
    SyslogFacility,
    SyslogProtocol,
)


@pytest.mark.unit
class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_all_members_exist(self) -> None:
        members = set(LogLevel)
        assert len(members) == 5
        assert LogLevel.DEBUG in members
        assert LogLevel.INFO in members
        assert LogLevel.WARNING in members
        assert LogLevel.ERROR in members
        assert LogLevel.CRITICAL in members

    def test_values_are_strings(self) -> None:
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_membership(self) -> None:
        assert "DEBUG" in LogLevel.__members__.values()
        assert "INFO" in LogLevel.__members__.values()

    def test_is_str_subclass(self) -> None:
        assert isinstance(LogLevel.DEBUG, str)


@pytest.mark.unit
class TestRotationStrategy:
    """Tests for RotationStrategy enum."""

    def test_all_members_exist(self) -> None:
        members = set(RotationStrategy)
        assert len(members) == 2
        assert RotationStrategy.BUILTIN in members
        assert RotationStrategy.EXTERNAL in members

    def test_values_are_strings(self) -> None:
        assert RotationStrategy.BUILTIN.value == "builtin"
        assert RotationStrategy.EXTERNAL.value == "external"

    def test_is_str_subclass(self) -> None:
        assert isinstance(RotationStrategy.BUILTIN, str)


@pytest.mark.unit
class TestSinkType:
    """Tests for SinkType enum."""

    def test_all_members_exist(self) -> None:
        members = set(SinkType)
        assert len(members) == 6
        assert SinkType.CONSOLE in members
        assert SinkType.FILE in members
        assert SinkType.SYSLOG in members
        assert SinkType.HTTP in members
        assert SinkType.PROMETHEUS in members
        assert SinkType.OTLP in members

    def test_values_are_strings(self) -> None:
        assert SinkType.CONSOLE.value == "console"
        assert SinkType.FILE.value == "file"
        assert SinkType.SYSLOG.value == "syslog"
        assert SinkType.HTTP.value == "http"
        assert SinkType.PROMETHEUS.value == "prometheus"
        assert SinkType.OTLP.value == "otlp"

    def test_is_str_subclass(self) -> None:
        assert isinstance(SinkType.CONSOLE, str)


@pytest.mark.unit
class TestSyslogFacility:
    """Tests for SyslogFacility enum."""

    def test_all_members_exist(self) -> None:
        members = set(SyslogFacility)
        assert len(members) == 13
        for name in (
            "USER",
            "LOCAL0",
            "LOCAL1",
            "LOCAL2",
            "LOCAL3",
            "LOCAL4",
            "LOCAL5",
            "LOCAL6",
            "LOCAL7",
            "DAEMON",
            "SYSLOG",
            "AUTH",
            "KERN",
        ):
            assert hasattr(SyslogFacility, name)

    def test_values_are_lowercase_strings(self) -> None:
        for member in SyslogFacility:
            assert member.value == member.name.lower()

    def test_is_str_subclass(self) -> None:
        assert isinstance(SyslogFacility.USER, str)


@pytest.mark.unit
class TestSyslogProtocol:
    """Tests for SyslogProtocol enum."""

    def test_all_members_exist(self) -> None:
        members = set(SyslogProtocol)
        assert len(members) == 2
        assert SyslogProtocol.TCP in members
        assert SyslogProtocol.UDP in members

    def test_values_are_strings(self) -> None:
        assert SyslogProtocol.TCP.value == "tcp"
        assert SyslogProtocol.UDP.value == "udp"

    def test_is_str_subclass(self) -> None:
        assert isinstance(SyslogProtocol.TCP, str)


@pytest.mark.unit
class TestOtlpProtocol:
    """Tests for OtlpProtocol enum."""

    def test_all_members_exist(self) -> None:
        members = set(OtlpProtocol)
        assert len(members) == 2
        assert OtlpProtocol.HTTP_JSON in members
        assert OtlpProtocol.GRPC in members

    def test_values_are_strings(self) -> None:
        assert OtlpProtocol.HTTP_JSON.value == "http/json"
        assert OtlpProtocol.GRPC.value == "grpc"

    def test_is_str_subclass(self) -> None:
        assert isinstance(OtlpProtocol.HTTP_JSON, str)
