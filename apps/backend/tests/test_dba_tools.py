from __future__ import annotations

from scripts.dba_data_masker import (
    compute_snapshot_checksum,
    mask_email,
    mask_encrypted_token,
    mask_phone_number,
    sanitize_social_account,
    sanitize_user_record,
    sanitize_whatsapp_session,
)


def test_mask_phone_number() -> None:
    assert mask_phone_number("+51987654321") == "+51900000000"
    assert mask_phone_number("+12025550199") == "+12000000000"
    assert mask_phone_number(None) is None


def test_mask_email() -> None:
    masked = mask_email("lead.engineer@company.com")
    assert masked is not None
    assert masked.startswith("dev_")
    assert masked.endswith("@company.com")
    assert mask_email(None) is None


def test_mask_encrypted_token() -> None:
    secret = "AQICAHj89...production_secret_token_12345"
    masked = mask_encrypted_token(secret)
    assert masked is not None
    assert masked.startswith("mock_enc_tok_")
    assert "production_secret" not in masked


def test_sanitize_user_record() -> None:
    raw_user = {
        "_id": "usr_998877",
        "displayName": "John Doe",
        "email": "john.doe@example.com",
        "whatsappPhone": "+51987654321",
        "createdAt": 1714500000,
    }
    sanitized = sanitize_user_record(raw_user)
    assert sanitized["displayName"].startswith("Anonymized User usr_99")
    assert sanitized["email"].startswith("dev_")
    assert sanitized["whatsappPhone"] == "+51900000000"
    assert sanitized["createdAt"] == 1714500000


def test_sanitize_social_account() -> None:
    raw_account = {
        "_id": "soc_123",
        "userId": "usr_998877",
        "provider": "linkedin",
        "authorUrn": "urn:li:person:abcdef12345",
        "accessTokenEncrypted": "real_encrypted_token_value",
    }
    sanitized = sanitize_social_account(raw_account)
    assert sanitized["authorUrn"] == "urn:li:person:ANONYMIZED_TEST_USER"
    assert sanitized["accessTokenEncrypted"].startswith("mock_enc_tok_")


def test_sanitize_whatsapp_session() -> None:
    raw_session = {
        "_id": "sess_456",
        "userId": "usr_998877",
        "phone": "+51987654321",
        "expiresAt": 1714586400,
    }
    sanitized = sanitize_whatsapp_session(raw_session)
    assert sanitized["phone"] == "+51900000000"


def test_compute_snapshot_checksum() -> None:
    payload_a = {"users": [{"id": 1, "name": "test"}], "version": "1.0"}
    payload_b = {"version": "1.0", "users": [{"id": 1, "name": "test"}]}
    # Keys ordering differences should still produce matching deterministic checksums
    assert compute_snapshot_checksum(payload_a) == compute_snapshot_checksum(payload_b)
