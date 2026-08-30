#!/usr/bin/env python3
"""DBA Data Masking and Tenant Anonymization Utility.

Sanitizes sensitive production records (PII, credentials, access tokens)
for staging environment hydration and disaster recovery drill datasets.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def mask_phone_number(phone: str | None) -> str | None:
    """Masks a phone number preserving country code format."""
    if not phone:
        return phone
    # Keep leading '+' and first 3 digits, mask the rest
    clean = re.sub(r"[^\d+]", "", phone)
    if clean.startswith("+") and len(clean) > 4:
        return clean[:4] + "0" * (len(clean) - 4)
    if len(clean) > 3:
        return clean[:3] + "0" * (len(clean) - 3)
    return "000000"


def mask_email(email: str | None) -> str | None:
    """Anonymizes email address with deterministic pseudonym."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    hashed_local = hashlib.sha256(local.encode("utf-8")).hexdigest()[:8]
    return f"dev_{hashed_local}@{domain}"


def mask_encrypted_token(token: str | None) -> str | None:
    """Replaces production encrypted secrets with synthetic test tokens."""
    if not token:
        return token
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"mock_enc_tok_{token_hash}"


def sanitize_user_record(user: dict[str, Any]) -> dict[str, Any]:
    """Sanitizes user PII fields."""
    sanitized = user.copy()
    if "whatsappPhone" in sanitized and sanitized["whatsappPhone"]:
        sanitized["whatsappPhone"] = mask_phone_number(sanitized["whatsappPhone"])
    if "email" in sanitized and sanitized["email"]:
        sanitized["email"] = mask_email(sanitized["email"])
    if "displayName" in sanitized and sanitized["displayName"]:
        sanitized["displayName"] = f"Anonymized User {sanitized.get('_id', 'unknown')[:6]}"
    return sanitized


def sanitize_social_account(account: dict[str, Any]) -> dict[str, Any]:
    """Sanitizes sensitive OAuth credentials."""
    sanitized = account.copy()
    if "accessTokenEncrypted" in sanitized:
        sanitized["accessTokenEncrypted"] = mask_encrypted_token(sanitized["accessTokenEncrypted"])
    if "authorUrn" in sanitized and sanitized["authorUrn"]:
        sanitized["authorUrn"] = "urn:li:person:ANONYMIZED_TEST_USER"
    return sanitized


def sanitize_whatsapp_session(session: dict[str, Any]) -> dict[str, Any]:
    """Sanitizes WhatsApp session phone metadata."""
    sanitized = session.copy()
    if "phone" in sanitized:
        sanitized["phone"] = mask_phone_number(sanitized["phone"])
    return sanitized


def compute_snapshot_checksum(payload: dict[str, Any]) -> str:
    """Computes SHA-256 integrity checksum for a dataset snapshot."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
