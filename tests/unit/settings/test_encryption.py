"""Unit tests for settings encryption."""

import pytest
from cryptography.fernet import Fernet

from synthorg.settings.encryption import SettingsEncryptor
from synthorg.settings.errors import SettingsEncryptionError


@pytest.mark.unit
class TestSettingsEncryptor:
    """Tests for Fernet encrypt/decrypt wrapper."""

    @pytest.fixture
    def key(self) -> bytes:
        return Fernet.generate_key()

    @pytest.fixture
    def encryptor(self, key: bytes) -> SettingsEncryptor:
        return SettingsEncryptor(key)

    def test_roundtrip(self, encryptor: SettingsEncryptor) -> None:
        plaintext = "my-secret-api-key"
        ciphertext = encryptor.encrypt(plaintext)
        assert ciphertext != plaintext
        assert encryptor.decrypt(ciphertext) == plaintext

    def test_roundtrip_empty_string(self, encryptor: SettingsEncryptor) -> None:
        ciphertext = encryptor.encrypt("")
        assert encryptor.decrypt(ciphertext) == ""

    def test_roundtrip_unicode(self, encryptor: SettingsEncryptor) -> None:
        plaintext = "p\u00e4ssw\u00f6rd-\U0001f512-\u6d4b\u8bd5"
        ciphertext = encryptor.encrypt(plaintext)
        assert encryptor.decrypt(ciphertext) == plaintext

    def test_decrypt_with_wrong_key_raises(self) -> None:
        enc1 = SettingsEncryptor(Fernet.generate_key())
        enc2 = SettingsEncryptor(Fernet.generate_key())
        ciphertext = enc1.encrypt("secret")
        with pytest.raises(SettingsEncryptionError, match="wrong key"):
            enc2.decrypt(ciphertext)

    def test_decrypt_invalid_ciphertext_raises(
        self, encryptor: SettingsEncryptor
    ) -> None:
        with pytest.raises(SettingsEncryptionError):
            encryptor.decrypt("not-valid-ciphertext")

    def test_from_env_returns_encryptor(
        self, key: bytes, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SYNTHORG_SETTINGS_KEY", key.decode("ascii"))
        enc = SettingsEncryptor.from_env()
        assert enc is not None
        assert enc.decrypt(enc.encrypt("test")) == "test"

    def test_from_env_returns_none_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SYNTHORG_SETTINGS_KEY", raising=False)
        assert SettingsEncryptor.from_env() is None

    def test_from_env_raises_for_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SYNTHORG_SETTINGS_KEY", "   ")
        with pytest.raises(SettingsEncryptionError, match="set but empty"):
            SettingsEncryptor.from_env()

    def test_from_env_raises_for_invalid_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SYNTHORG_SETTINGS_KEY", "not-a-valid-fernet-key")
        with pytest.raises(SettingsEncryptionError, match="Invalid Fernet key"):
            SettingsEncryptor.from_env()
