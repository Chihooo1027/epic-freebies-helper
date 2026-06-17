# -*- coding: utf-8 -*-
"""
Multi-account support for Epic Games freebies helper.

Supports two input formats:
  1. EPIC_ACCOUNTS: multiline env var, one "email:password" per line (recommended)
  2. EPIC_EMAIL + EPIC_PASSWORD: single account fallback (backward compatible)
"""

from __future__ import annotations

from typing import List, Tuple

from loguru import logger
from pydantic import SecretStr


def mask_email(email: str) -> str:
    """Mask an email address before writing it to logs."""
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"

    masked_local = f"{local[:2]}***" if len(local) > 2 else f"{local[:1]}***"
    return f"{masked_local}@{domain}"


def parse_accounts() -> List[Tuple[str, str]]:
    """
    Parse account credentials from settings.

    Priority:
      1. EPIC_ACCOUNTS (multiline, one "email:password" per line)
      2. EPIC_EMAIL + EPIC_PASSWORD (single account fallback)

    Returns:
        List of (email, password) tuples.
    """
    from settings import settings

    # --- Priority 1: EPIC_ACCOUNTS multiline env var ---
    raw = ""
    if settings.EPIC_ACCOUNTS is not None:
        raw = settings.EPIC_ACCOUNTS.get_secret_value().strip()

    if raw:
        accounts: List[Tuple[str, str]] = []
        for i, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue

            # Split on first colon only (passwords may contain colons)
            if ":" not in line:
                logger.warning(
                    "EPIC_ACCOUNTS line {} skipped: missing colon separator (email:password)", i
                )
                continue

            email, password = line.split(":", 1)
            email = email.strip()
            password = password.strip()

            if not email or not password:
                logger.warning("EPIC_ACCOUNTS line {} skipped: empty email or password", i)
                continue

            accounts.append((email, password))

        if accounts:
            logger.info("Parsed {} account(s) from EPIC_ACCOUNTS", len(accounts))
            return accounts

        logger.warning("EPIC_ACCOUNTS is set but no valid entries found")
        return []

    # --- Priority 2: EPIC_EMAIL + EPIC_PASSWORD (single account) ---
    email = (settings.EPIC_EMAIL or "").strip()
    password = settings.EPIC_PASSWORD.get_secret_value().strip()

    if email and password:
        logger.info("Using single account from EPIC_EMAIL/EPIC_PASSWORD")
        return [(email, password)]

    return []


def swap_account(email: str, password: str) -> None:
    """Swap the active account credentials on the global settings object."""
    from settings import settings

    settings.EPIC_EMAIL = email
    settings.EPIC_PASSWORD = SecretStr(password)

    logger.info("Switched to account: {}", mask_email(email))
