# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"


def _load_telegram_module():
    # Minimal stubs so the notification module can be imported without the full app stack.
    for name in (
        "httpx",
        "loguru",
        "models",
        "services",
        "services.epic_collection_summary_service",
        "services.epic_games_service",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    log_mod = sys.modules["loguru"]

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

    models_mod = sys.modules["models"]

    class PromotionGame:
        def __init__(self, title="", url="", namespace="", id=""):
            self.title = title
            self.url = url
            self.namespace = namespace
            self.id = id

    models_mod.PromotionGame = PromotionGame

    summary_mod = sys.modules["services.epic_collection_summary_service"]

    class CollectionSummary:
        def __init__(
            self,
            all_promotions=None,
            newly_claimed_promotions=None,
            previously_claimed_promotions=None,
            unconfirmed_promotions=None,
            failed_promotions=None,
            error_message="",
        ):
            self.all_promotions = all_promotions or []
            self.newly_claimed_promotions = newly_claimed_promotions or []
            self.previously_claimed_promotions = previously_claimed_promotions or []
            self.unconfirmed_promotions = unconfirmed_promotions or []
            self.failed_promotions = failed_promotions or []
            self.error_message = error_message

    summary_mod.CollectionSummary = CollectionSummary

    games_mod = sys.modules["services.epic_games_service"]
    games_mod.get_promotions = lambda: []

    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    # Ensure package-style imports resolve for nested service modules.
    services_pkg = sys.modules["services"]
    services_pkg.epic_collection_summary_service = summary_mod
    services_pkg.epic_games_service = games_mod

    spec = importlib.util.spec_from_file_location(
        "telegram_notification_service",
        APP_DIR / "services" / "telegram_notification_service.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module, CollectionSummary, PromotionGame


telegram, CollectionSummary, PromotionGame = _load_telegram_module()


def _sample_summary():
    game = PromotionGame(title="Demo Game", url="https://store.epicgames.com/en-US/p/demo")
    return CollectionSummary(
        all_promotions=[game],
        newly_claimed_promotions=[game],
        previously_claimed_promotions=[],
    )


def test_single_account_telegram_message_omits_account_label_by_default():
    message = telegram.build_telegram_summary_message(_sample_summary())
    assert message.startswith("Epic 周免领取结果")
    assert "账号：" not in message
    assert "运行状态：成功" in message
    assert "Demo Game" in message


def test_multi_account_telegram_message_includes_masked_account_label():
    message = telegram.build_telegram_summary_message(
        _sample_summary(),
        account_label="ab***@example.com",
    )
    assert "Epic 周免领取结果" in message
    assert "账号：ab***@example.com" in message
    # Account line should appear before status.
    assert message.index("账号：") < message.index("运行状态：")
