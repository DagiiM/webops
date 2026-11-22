"""Boundary-value CLI validation regressions, including injection prevention."""
from unittest.mock import MagicMock
import pytest
from webops_cli import validators as m

V = m.InputValidator

@pytest.mark.parametrize("value", [
    "", "www", "mail", "ftp", "admin", "root", "api",
    "-started", "trailing-", "double--dash", "unsafe space",
    "a"*65, "bad/name", "semicolon;",
])
def test_name_guards_reject_reserved_and_malformed_values(value):
    with pytest.raises(m.ValidationError):
        V.validate_deployment_name(value)

@pytest.mark.parametrize("value", ["api-web", "v1", "A42", "A"*63+"Z"])
def test_name_guards_accept_safe_names(value):
    assert V.validate_deployment_name(value) == value

@pytest.mark.parametrize("value", [
    "", "ftp://example.com/repo.git", "file:///tmp/repo.git",
    "https://user:secret@example.com/repo.git", "https://example.com/../repo.git",
    "http://", "x"*2049, "ldap://example.org/a",
])
def test_repository_url_rejects_unsafe_forms(value):
    with pytest.raises(m.ValidationError):
        V.validate_git_url(value)

@pytest.mark.parametrize("value", [
    "https://github.com/owner/repo.git",
    "ssh://git@github.com/owner/repo",
    "git@github.com:team/service",
    "git://github.com/team/repo.git",
])
def test_repository_url_accepts_valid_protocols(value):
    assert V.validate_git_url(value) == value

def test_repository_url_parse_exception_is_wrapped(monkeypatch):
    monkeypatch.setattr(m, "urlparse", MagicMock(side_effect=ValueError("invalid port")))
    with pytest.raises(m.ValidationError, match="Invalid URL format"):
        V.validate_git_url("https://example.org/project")

@pytest.mark.parametrize("value", ["", "feature/valid-branch", "stable"])
def test_valid_branches_or_main_default(value):
    assert V.validate_git_branch(value) == ("main" if not value else value)

@pytest.mark.parametrize("value", ["-unsafe", "feature/", "bad branch", "x"*256])
def test_branches_reject_injection_and_invalid_limits(value):
    with pytest.raises(m.ValidationError):
        V.validate_git_branch(value)

@pytest.mark.parametrize("value,expected", [
    ("", ""), ("App.Example.COM", "app.example.com"),
    ("app.local", "app.local"), ("127.0.0.1", "127.0.0.1"),
])
def test_optional_domain_normalization(value, expected):
    assert V.validate_domain_name(value) == expected

@pytest.mark.parametrize("value", [".example.com", "example.com.",
                                  "example..com", "x"*254, "bad_domain!"])
def test_domain_rejection(value):
    with pytest.raises(m.ValidationError):
        V.validate_domain_name(value)

@pytest.mark.parametrize("value", ["", "bad-var", "9PORT", "X"*256])
def test_environment_key_guard(value):
    with pytest.raises(m.ValidationError):
        V.validate_env_var_key(value)

def test_environment_empty_and_safe_multiline_values():
    assert V.validate_env_var_value(None) == ""
    assert V.validate_env_var_value("line 1\nline 2\tvalue") == "line 1\nline 2\tvalue"
    assert V.validate_env_var_key("_TOKEN_2") == "_TOKEN_2"

@pytest.mark.parametrize("value", ["value\x00unsafe", "value\x1f", "x"*8193])
def test_environment_value_rejects_control_bytes_and_oversize(value):
    with pytest.raises(m.ValidationError):
        V.validate_env_var_value(value)

@pytest.mark.parametrize("value", ["", "short", "bad token with spaces", "x"*1025])
def test_api_auth_token_rejects_bad_length_and_whitespace(value):
    with pytest.raises(m.ValidationError):
        V.validate_api_token(value)

def test_api_auth_token_accepts_reasonable_allowed_characters():
    assert V.validate_api_token("safe-API_token_012345") == "safe-API_token_012345"

@pytest.mark.parametrize("value", [
    "", "file:///etc/passwd", "ftp://example.com", "http://",
    "https://.invalid.example", "x"*2049,
])
def test_panel_url_format_guards(value):
    with pytest.raises(m.ValidationError):
        V.validate_url(value)

def test_panel_url_normalizes_trailing_slash():
    assert V.validate_url("https://panel.example.org/") == "https://panel.example.org"

def test_panel_url_parsing_error_is_safe(monkeypatch):
    monkeypatch.setattr(m, "urlparse", MagicMock(side_effect=ValueError("bad URL")))
    with pytest.raises(m.ValidationError, match="Invalid URL format"):
        V.validate_url("https://panel.example.org")

@pytest.mark.parametrize("validator,value", [
    (V.validate_page_number, 0), (V.validate_page_number, 1001),
    (V.validate_per_page, 0), (V.validate_per_page, 101),
    (V.validate_tail_count, 0), (V.validate_tail_count, 10001),
])
def test_pagination_and_log_tail_bounds(validator, value):
    with pytest.raises(m.ValidationError):
        validator(value)

def test_pagination_per_page_and_tail_allowed_values():
    assert V.validate_page_number(1) == 1
    assert V.validate_page_number(1000) == 1000
    assert V.validate_per_page(1) == 1
    assert V.validate_per_page(100) == 100
    assert V.validate_tail_count(None) is None
    assert V.validate_tail_count(10) == 10

@pytest.mark.parametrize("fields", [
    ["MALFORMED"], ["KEY="], ["9INVALID=abc"],
    ["VALID=abc\x00unsafe"], ["VALID="+("x"*8193)],
])
def test_custom_environment_rejects_invalid_entries(fields):
    with pytest.raises(m.ValidationError):
        V.sanitize_custom_env_vars(fields)

def test_custom_environment_preserves_equal_sign_in_values():
    assert V.sanitize_custom_env_vars(["TOKEN=abc=def", "PORT=8080"]) == {
        "TOKEN": "abc=def", "PORT": "8080"}

@pytest.mark.parametrize("value,maxlen,pattern", [
    ("", 20, r"^a+$"), ("a"*21, 20, r"^a+$"),
    ("bad-input", 20, r"^a+$"),
])
def test_generic_validator_rejects_empty_oversized_or_wrong_pattern(value,maxlen,pattern):
    with pytest.raises(m.ValidationError):
        m.validate_input(value, pattern, maxlen)

def test_generic_validator_good_value():
    assert m.validate_input("abc", r"^[a-z]+$", 10)

