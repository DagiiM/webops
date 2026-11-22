"""Security, encryption and failure-path coverage without storing secrets."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import builtins
import os
import json
import pytest
from cryptography.fernet import Fernet
from webops_cli import encryption as enc
from webops_cli import errors as err


@pytest.fixture
def secure(monkeypatch, tmp_path):
    monkeypatch.delenv("WEBOPS_ENCRYPTION_KEY", raising=False)
    keyfile = tmp_path / "provisioning" / ".encryption_key"
    monkeypatch.setattr(enc.os.path, "expanduser", lambda path: str(keyfile))
    cipher = enc.SecureConfig()
    return cipher, keyfile


def test_key_file_created_private_and_reused(secure):
    first, file = secure
    assert file.is_file()
    assert file.read_bytes() == first.key
    assert (file.stat().st_mode & 0o777) == 0o600
    assert enc.SecureConfig().key == first.key


def test_config_key_from_env(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv("WEBOPS_ENCRYPTION_KEY", key.decode())
    assert enc.SecureConfig().key == key


def test_invalid_environment_key_is_rejected(monkeypatch):
    monkeypatch.setenv("WEBOPS_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(enc.EncryptionError, match="environment"):
        enc.SecureConfig()


def test_unreadable_persisted_key_is_rejected(secure, monkeypatch):
    obj, keyfile = secure
    original_open = builtins.open
    def broken(path, *a, **k):
        if str(path) == str(keyfile):
            raise PermissionError("private file denied")
        return original_open(path, *a, **k)
    monkeypatch.setattr(builtins, "open", broken)
    with pytest.raises(enc.EncryptionError, match="Failed to read"):
        enc.SecureConfig()


def test_generate_key_write_error_is_wrapped(secure, monkeypatch):
    obj, keyfile = secure
    keyfile.unlink()
    monkeypatch.setattr(enc.Fernet, "generate_key", MagicMock(side_effect=OSError("no entropy")))
    with pytest.raises(enc.EncryptionError, match="generate"):
        obj._get_or_create_key()


@pytest.mark.parametrize("value", [None, 123, {}, []])
def test_encrypt_value_requires_str(secure, value):
    with pytest.raises(enc.EncryptionError, match="string"):
        secure[0].encrypt_value(value)


@pytest.mark.parametrize("value", [None, 123, {}, []])
def test_decrypt_value_requires_str(secure, value):
    with pytest.raises(enc.EncryptionError, match="string"):
        secure[0].decrypt_value(value)


def test_encrypted_secret_roundtrip_and_classifier(secure):
    crypt, _ = secure
    protected = crypt.encrypt_value("sample-key-value")
    assert crypt.is_encrypted(protected)
    assert crypt.decrypt_value(protected) == "sample-key-value"
    assert not crypt.is_encrypted("plaintext-secret")
    assert not crypt.is_encrypted(42)


def test_bad_cipher_encrypt_and_decrypt_do_not_expose_internal_errors(secure):
    crypt, _ = secure
    protected = crypt.encrypt_value("secret")
    crypt.cipher = MagicMock()
    crypt.cipher.encrypt.side_effect = RuntimeError("cipher unavailable")
    crypt.cipher.decrypt.side_effect = RuntimeError("cipher unavailable")
    with pytest.raises(enc.EncryptionError, match="Failed to encrypt"):
        crypt.encrypt_value("secret")
    with pytest.raises(enc.EncryptionError, match="Failed to decrypt"):
        crypt.decrypt_value(protected)
    assert not crypt.is_encrypted(protected)


@pytest.mark.parametrize("data", [None, "text", [], 0])
def test_encrypt_config_rejects_non_dictionary(secure, data):
    with pytest.raises(enc.EncryptionError):
        secure[0].encrypt_dict_values(data, ["token"])


@pytest.mark.parametrize("data", [None, "text", [], 0])
def test_decrypt_config_rejects_non_dictionary(secure, data):
    with pytest.raises(enc.EncryptionError):
        secure[0].decrypt_dict_values(data, ["token"])


def test_sensitive_dict_preserves_unknown_fields_and_skips_none(secure):
    crypt, _ = secure
    original = {"token": "sensitive-token", "key": None, "role": "developer"}
    result = crypt.encrypt_dict_values(original, ["token", "key"])
    assert original["token"] == "sensitive-token"
    assert result["key"] is None
    assert result["role"] == "developer"
    assert crypt.is_encrypted(result["token"])
    assert crypt.encrypt_dict_values(result, ["token"]) == result
    assert crypt.decrypt_dict_values(result, ["token", "key"]) == original


def test_sensitive_dict_decrypt_failure_preserves_value(secure, monkeypatch):
    crypt, _ = secure
    value = crypt.encrypt_value("secret")
    monkeypatch.setattr(crypt, "decrypt_value",
                        MagicMock(side_effect=enc.EncryptionError("tampered")))
    assert crypt.decrypt_dict_values({"token": value}, ["token"])["token"] == value


@pytest.mark.parametrize("length", [0, 3, 11])
def test_password_minimum_length(length):
    with pytest.raises(ValueError):
        enc.PasswordManager.generate_secure_password(length)


def test_generated_password_required_complexity_is_retryable(monkeypatch):
    payloads = iter([b"aaaaaaaaaaaa", b"Aa1_abcdefghij"])
    monkeypatch.setattr(enc.base64, "urlsafe_b64encode", lambda *_: next(payloads))
    password = enc.PasswordManager.generate_secure_password(12)
    assert password == "Aa1_abcdefgh"


@pytest.mark.parametrize("value,valid", [
    ("Aa1!some-secret-password", True),
    ("abc", False), ("abcdefghijklmnop", False),
    ("ABCDEFGHIJKLMN12!", False), ("abcdefghij12345!", False),
    ("Abcdefghijklmno!", False), ("Abcdefghijklmno1", False),
    ("password", False),
])
def test_password_strength_and_failure_advice(value, valid):
    result = enc.PasswordManager.validate_password_strength(value)
    assert result["valid"] is valid
    assert 0 <= result["score"] <= 5
    if not valid:
        assert result["issues"]


def test_pbkdf2_key_derivation_with_optional_salt():
    first, salt = enc.derive_key_from_password("my password")
    second, _ = enc.derive_key_from_password("my password", salt)
    third, _ = enc.derive_key_from_password("another password", salt)
    assert first == second and first != third and len(salt) == 16


def test_hashing_with_optional_salt_and_constant_time_verify():
    hashed, salt = enc.hash_sensitive_data("important")
    same, _ = enc.hash_sensitive_data("important", salt)
    assert hashed == same
    assert enc.verify_sensitive_data("important", hashed, salt)
    assert not enc.verify_sensitive_data("different", hashed, salt)


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setattr(err, "console", MagicMock())
    return err.ErrorHandler()


@pytest.mark.parametrize("message", [
    "connection refused", "401 unauthorized", "permission denied",
    "service not found", "database unavailable", "celery worker unavailable",
    "disk full", "python module not found", "git clone failed",
    "address already in use", "unrecognized problem",
])
def test_error_classifier_and_generic_fallback(handler, message):
    kind = handler.identify_error_type(message)
    suggestions = handler.get_suggestions(message)
    assert suggestions
    assert (kind is None) is (message == "unrecognized problem")


@pytest.mark.parametrize("message,context,suggestions", [
    ("server down", None, False), ("Unauthorized 401", "syncing", True),
    ("permission denied", "starting deployment", True),
])
def test_error_panel_rendering(handler, message, context, suggestions):
    handler.display_error(ValueError(message), context=context, show_suggestions=suggestions)
    err.console.print.assert_called()


def test_custom_error_suggestions_are_used(handler):
    failure = err.ConfigurationError("custom failure", ["Use approved access token"])
    handler.display_error(failure, "configuration")
    err.console.print.assert_called()


@pytest.mark.parametrize("error", [
    RuntimeError("connection refused"), RuntimeError("401 Unauthorized"),
    RuntimeError("unidentified HTTP error"),
])
def test_api_error_recovery_paths(handler, monkeypatch, error):
    display = MagicMock()
    monkeypatch.setattr(handler, "display_error", display)
    handler.handle_api_error(error, "deploy")
    display.assert_called_once()
    assert isinstance(display.call_args.args[0], err.WebOpsError)


@pytest.mark.parametrize("component", ["database", "celery", "web", "unknown"])
def test_component_recovery_routes(handler, monkeypatch, component):
    display = MagicMock()
    monkeypatch.setattr(handler, "display_error", display)
    handler.handle_system_error(OSError("service offline"), component)
    assert display.called


def test_keyboard_cancel_has_standard_130_exit(monkeypatch):
    with pytest.raises(SystemExit) as captured:
        err.handle_keyboard_interrupt()
    assert captured.value.code == 130


def test_global_exception_handler_exits_with_expected_code(monkeypatch):
    with pytest.raises(SystemExit) as captured:
        err.handle_exception(OSError("problem"), "provisioning", exit_code=7)
    assert captured.value.code == 7


@pytest.mark.parametrize("configured,url,token,failure", [
    (False, None, None, True), (True, "ftp://panel.org", "long-api-token", True),
    (True, "https://panel.org", "tiny", True),
    (True, "https://panel.org", "very-long-secure-token", False),
])
def test_config_preflight_catches_unusable_auth_details(configured, url, token, failure):
    config = SimpleNamespace(is_configured=lambda: configured,
                             get_url=lambda: url, get_token=lambda: token)
    if failure:
        with pytest.raises(err.ConfigurationError):
            err.validate_configuration(config)
    else:
        err.validate_configuration(config)


def test_auto_config_preflight_protects_missing_config(monkeypatch):
    from webops_cli import config as c
    monkeypatch.setattr(c, "Config", lambda: SimpleNamespace(is_configured=lambda: False))
    with pytest.raises(err.ConfigurationError):
        err.validate_configuration()


@pytest.mark.parametrize("user_id,allowed", [(0, True), (1001, False)])
def test_privileged_operation_requires_root(monkeypatch, user_id, allowed):
    monkeypatch.setattr(os, "geteuid", lambda: user_id)
    if allowed:
        err.require_root_privileges("service restart")
    else:
        with pytest.raises(err.PermissionError):
            err.require_root_privileges("service restart")

