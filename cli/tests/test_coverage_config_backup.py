"""Configuration backup, encryption, and recovery contract tests."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from webops_cli import config as m


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return m.Config()


@pytest.mark.parametrize(
    "setting,value",
    [
        ("role", "administrator"),
        ("timeout", 2),
        ("timeout", 301),
        ("retries", -1),
        ("retries", 11),
        ("backup_count", 0),
        ("backup_count", 51),
        ("timeout", "slow"),
        ("token", "short"),
        ("url", "ftp://example.org"),
    ],
)
def test_config_validation_rejects_invalid_bounds(cfg, setting, value):
    with pytest.raises(m.ConfigValidationError):
        cfg._validate_config_schema({setting: value})


def test_required_schema_validation_is_enforced(cfg):
    cfg.CONFIG_SCHEMA = {
        **cfg.CONFIG_SCHEMA,
        "required_custom": {"type": str, "required": True},
    }
    with pytest.raises(m.ConfigValidationError, match="Required"):
        cfg._validate_config_schema({})


def test_schema_allows_missing_optional_fields_and_valid_values(cfg):
    cfg._validate_config_schema(
        {
            "url": "https://panel.example.org",
            "token": "long-secret-token",
            "role": "developer",
            "timeout": 30,
            "verify_ssl": True,
            "retries": 3,
            "backup_count": 5,
        }
    )
    assert not cfg.validate_url(123)
    assert not cfg.validate_token(None)
    assert cfg.validate_url("http://localhost:8000")
    assert cfg.validate_token("long-api-token")


def test_config_roundtrip_encrypted_token_default_values_and_permissions(cfg):
    cfg.save(
        {"url": "https://example.org", "token": "top-secret-token-123", "role": "admin"}
    )
    encoded = cfg.config_file.read_text()
    assert "top-secret-token-123" not in encoded
    loaded = cfg.load()
    assert loaded["token"] == "top-secret-token-123"
    assert loaded["timeout"] == 30
    assert cfg.get_url() == "https://example.org"
    assert cfg.get_token() == "top-secret-token-123"
    assert cfg.is_configured()
    assert (cfg.config_file.stat().st_mode & 0o777) == 0o600
    assert (cfg.backup_dir.stat().st_mode & 0o777) == 0o700


def test_backup_restore_and_retention(cfg):
    cfg.save({"role": "developer"})
    cfg.set("role", "admin")
    backups = cfg.list_backups()
    assert backups
    cfg.restore_from_backup()
    assert cfg.get("role") in ("developer", "admin")
    cfg.restore_from_backup(backups[0])
    cfg._cleanup_old_backups()
    cfg.reset()
    assert cfg.get("role") is None
    assert cfg.get("timeout") == 30


def test_restore_missing_backup_is_reported(cfg):
    with pytest.raises(m.ConfigError, match="No backup"):
        cfg.restore_from_backup()
    with pytest.raises(m.ConfigError, match="not found"):
        cfg.restore_from_backup("20991231_235959")


def test_save_and_reset_with_no_prior_config(cfg):
    assert cfg.load() == {}
    cfg.reset()
    assert cfg.config_file.exists()
    assert cfg.load()["verify_ssl"] is True


def test_backup_copy_error_raises_safe_exception(cfg, monkeypatch):
    cfg.save({"role": "developer"})
    monkeypatch.setattr(
        m.shutil, "copy2", lambda *a: (_ for _ in ()).throw(OSError("disk read only"))
    )
    with pytest.raises(m.ConfigBackupError, match="Failed to create backup"):
        cfg._create_backup()


def test_old_backup_cleanup_is_nonblocking_on_permission_error(cfg, monkeypatch):
    fake = MagicMock()
    fake.stat.side_effect = PermissionError("backup permission")
    monkeypatch.setattr(Path, "glob", lambda *a, **k: [fake])
    assert cfg._cleanup_old_backups() is None


def test_restore_rollback_failure_raises_config_error(cfg, monkeypatch):
    cfg.save({"role": "viewer"})
    backup = cfg.backup_dir / "config_20261122_120000.json"
    backup.write_text('{"role":"developer"}')
    monkeypatch.setattr(
        m.shutil, "copy2", lambda *a: (_ for _ in ()).throw(OSError("disk full"))
    )
    with pytest.raises(m.ConfigError, match="Failed to restore"):
        cfg.restore_from_backup("20261122_120000")


def test_corrupted_config_restores_from_valid_backup(cfg):
    cfg.save({"role": "developer"})
    backup = cfg.backup_dir / "config_20261122_120000.json"
    backup.write_text(cfg.config_file.read_text())
    cfg.config_file.write_text("{invalid JSON")
    assert cfg.load()["role"] == "developer"


def test_corrupt_config_without_backup_fails_safely(cfg):
    cfg.config_file.write_text("{invalid")
    with pytest.raises(m.ConfigError, match="Failed to load"):
        cfg.load()


def test_config_save_failure_does_not_leave_partial_tmp(cfg, monkeypatch):
    cfg.secure_config.encrypt_dict_values = MagicMock(side_effect=OSError("disk fault"))
    with pytest.raises(m.ConfigError, match="Failed to save"):
        cfg.save({"role": "developer"}, create_backup=False)
    assert not cfg.config_file.with_suffix(".tmp").exists()


def test_config_save_cleans_partial_tmp(cfg, monkeypatch):
    temp = cfg.config_file.with_suffix(".tmp")
    orig_chmod = m.os.chmod

    def chmod(path, mode):
        if Path(path) == temp:
            raise PermissionError("unable to set private permissions")
        return orig_chmod(path, mode)

    monkeypatch.setattr(m.os, "chmod", chmod)
    with pytest.raises(m.ConfigError, match="Failed to save"):
        cfg.save({"role": "developer"}, create_backup=False)
    assert not temp.exists()


def test_load_encryption_failure_is_wrapped(cfg):
    cfg.save({"role": "viewer"})
    cfg.secure_config.decrypt_dict_values = MagicMock(
        side_effect=m.EncryptionError("cannot decrypt")
    )
    with pytest.raises(m.ConfigError, match="Failed to decrypt"):
        cfg.load()


def test_get_returns_default_after_corrupt_file(cfg):
    cfg.config_file.write_text("{invalid")
    assert cfg.get("some-key", "fallback") == "fallback"


def test_set_wraps_validation_failure(cfg):
    with pytest.raises(m.ConfigError, match="Failed to set"):
        cfg.set("timeout", 999)


def test_validate_configuration_missing_fields(cfg):
    result = cfg.validate_configuration()
    assert not result["valid"]
    assert "Missing required" in result["errors"][0]


@pytest.mark.parametrize(
    "kind", ["bad_url", "bad_token", "timeout", "retry", "exception"]
)
def test_config_audit_detects_issue_categories(cfg, monkeypatch, kind):
    values = {
        "url": "https://panel.example.org",
        "token": "valid-token-123",
        "timeout": 30,
        "retries": 3,
    }
    if kind == "bad_url":
        values["url"] = "http-untrusted"
    elif kind == "bad_token":
        values["token"] = "tiny"
    elif kind == "timeout":
        values["timeout"] = 900
    elif kind == "retry":
        values["retries"] = 20
    if kind == "exception":
        monkeypatch.setattr(
            cfg, "load", MagicMock(side_effect=m.ConfigError("bad config"))
        )
    else:
        monkeypatch.setattr(cfg, "load", lambda *a, **kw: values)
        monkeypatch.setattr(
            cfg, "get", lambda name, default=None: values.get(name, default)
        )
    result = cfg.validate_configuration()
    if kind == "exception":
        assert not result["valid"]
    else:
        assert result["errors"] or result["warnings"]


def test_backup_list_sorted_newest_first(cfg):
    for name in ("config_20261001_000000.json", "config_20261122_123000.json"):
        (cfg.backup_dir / name).write_text("{}")
    assert cfg.list_backups() == ["20261122_123000", "20261001_000000"]


def test_backup_list_errors_return_empty(cfg, monkeypatch):
    monkeypatch.setattr(
        Path,
        "glob",
        lambda *a, **kw: (_ for _ in ()).throw(PermissionError("no access")),
    )
    assert cfg.list_backups() == []
