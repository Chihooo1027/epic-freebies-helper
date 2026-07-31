# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"


def _load_accounts_module():
    log_mod = types.ModuleType("loguru")

    class _Logger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

        def success(self, *args, **kwargs):
            return None

        def debug(self, *args, **kwargs):
            return None

    log_mod.logger = _Logger()
    sys.modules["loguru"] = log_mod

    settings_mod = types.ModuleType("settings")

    class _Settings:
        EPIC_ACCOUNTS = None
        EPIC_EMAIL = ""
        EPIC_PASSWORD = SecretStr("")

    settings_mod.settings = _Settings()
    sys.modules["settings"] = settings_mod

    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    spec = importlib.util.spec_from_file_location("accounts", APP_DIR / "accounts.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module, settings_mod.settings


accounts, settings = _load_accounts_module()


def test_mask_email():
    assert accounts.mask_email("abc@example.com") == "ab***@example.com"
    assert accounts.mask_email("a@example.com") == "a***@example.com"
    assert accounts.mask_email("not-an-email") == "***"


def test_is_valid_email():
    assert accounts.is_valid_email("user@example.com")
    assert not accounts.is_valid_email("not-an-email")
    assert not accounts.is_valid_email("user@localhost")
    assert not accounts.is_valid_email("user name@example.com")


def test_parse_multi_accounts_passwords_may_contain_colons():
    raw = "a@example.com:pass:with:colons\nb@example.com:plain"
    parsed, invalid = accounts.parse_multi_accounts(raw)
    assert invalid == []
    assert parsed == [
        ("a@example.com", "pass:with:colons"),
        ("b@example.com", "plain"),
    ]


def test_parse_multi_accounts_collects_invalid_line_numbers():
    raw = "\n".join(
        [
            "good@example.com:secret",
            "missing-colon",
            "not-an-email:password",
            " :empty-email",
            "empty-pass@example.com:",
            "also@example.com:ok",
        ]
    )
    parsed, invalid = accounts.parse_multi_accounts(raw)
    assert parsed == [
        ("good@example.com", "secret"),
        ("also@example.com", "ok"),
    ]
    assert invalid == [2, 3, 4, 5]


def test_parse_accounts_absent_epic_accounts_uses_single_account():
    settings.EPIC_ACCOUNTS = None
    settings.EPIC_EMAIL = "solo@example.com"
    settings.EPIC_PASSWORD = SecretStr("solo-pass")
    assert accounts.parse_accounts() == [("solo@example.com", "solo-pass")]


def test_parse_accounts_fully_invalid_falls_back_to_single_account():
    settings.EPIC_ACCOUNTS = SecretStr("bad-line\nalso-bad")
    settings.EPIC_EMAIL = "solo@example.com"
    settings.EPIC_PASSWORD = SecretStr("solo-pass")
    assert accounts.parse_accounts() == [("solo@example.com", "solo-pass")]


def test_parse_accounts_partially_invalid_raises():
    settings.EPIC_ACCOUNTS = SecretStr("good@example.com:pw\nbad-line")
    settings.EPIC_EMAIL = "solo@example.com"
    settings.EPIC_PASSWORD = SecretStr("solo-pass")
    with pytest.raises(RuntimeError, match="line\\(s\\): 2"):
        accounts.parse_accounts()


def test_swap_account_updates_settings():
    accounts.swap_account("swapped@example.com", "new-secret")
    assert settings.EPIC_EMAIL == "swapped@example.com"
    assert settings.EPIC_PASSWORD.get_secret_value() == "new-secret"
