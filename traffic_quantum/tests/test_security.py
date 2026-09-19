"""Test suite for Security layer (JWT authorization, rate limiting, audit logging, input validation)."""

import os
import time
import pytest
from traffic_quantum.config import MasterConfig, SecurityConfig
from traffic_quantum.security import SecurityService


def test_jwt_authentication_valid_and_invalid():
    """Verify cryptographic token generation, verification, and tamper rejection."""
    sec = SecurityService()
    client_id = "ambulance_unit_108"

    # 1. Valid token
    token = sec.generate_token(client_id, role="emergency_dispatch", validity_sec=60)
    is_valid, claims, msg = sec.verify_token(token)
    assert is_valid is True
    assert claims["sub"] == client_id
    assert claims["role"] == "emergency_dispatch"

    # 2. Tampered token
    tampered_token = token[:-4] + "abcd"
    is_valid_tampered, _, _ = sec.verify_token(tampered_token)
    assert is_valid_tampered is False

    # 3. Wrong role token
    wrong_role_token = sec.generate_token(client_id, role="civilian_driver", validity_sec=60)
    is_valid_role, _, err_role = sec.verify_token(wrong_role_token)
    assert is_valid_role is False
    assert "Unauthorized" in err_role

    # 4. Expired token
    expired_token = sec.generate_token(client_id, role="emergency_dispatch", validity_sec=-10)
    is_valid_exp, _, err_exp = sec.verify_token(expired_token)
    assert is_valid_exp is False
    assert "expired" in err_exp.lower()


def test_rate_limiting_enforcement():
    """Verify sliding-window rate limit blocks excess requests."""
    cfg = MasterConfig(security=SecurityConfig(rate_limit_requests=3, rate_limit_window_sec=10))
    sec = SecurityService(config=cfg)
    client_id = "client_rapid_fire"

    now = 1000.0
    # First 3 requests must succeed
    for _ in range(3):
        allowed, _ = sec.check_rate_limit(client_id, current_timestamp=now)
        assert allowed is True

    # 4th request must be blocked
    blocked, reason = sec.check_rate_limit(client_id, current_timestamp=now)
    assert blocked is False
    assert "Rate limit exceeded" in reason

    # After window passes, request should be allowed again
    allowed_later, _ = sec.check_rate_limit(client_id, current_timestamp=now + 15.0)
    assert allowed_later is True


def test_emergency_input_validation():
    """Verify input validation rules for emergency dispatch requests."""
    sec = SecurityService()
    valid_token = sec.generate_token("unit_1")

    # Valid request
    ok, _ = sec.validate_emergency_request(origin=0, destination=5, num_intersections=6, token=valid_token)
    assert ok is True

    # Same origin & destination
    ok_same, err_same = sec.validate_emergency_request(origin=2, destination=2, num_intersections=6, token=valid_token)
    assert ok_same is False
    assert "distinct" in err_same

    # Out of bounds node
    ok_oob, _ = sec.validate_emergency_request(origin=0, destination=99, num_intersections=6, token=valid_token)
    assert ok_oob is False

    # Missing token
    ok_tok, _ = sec.validate_emergency_request(origin=0, destination=3, num_intersections=6, token="")
    assert ok_tok is False


def test_append_only_audit_log(tmp_path):
    """Verify append-only audit logging and SHA-256 entry hashing."""
    test_log = str(tmp_path / "test_audit.jsonl")
    cfg = MasterConfig(security=SecurityConfig(audit_log_file=test_log))
    sec = SecurityService(config=cfg)

    entry1 = sec.log_audit_entry(
        client_id="unit_101",
        action="emergency_preemption",
        details={"origin": 0, "destination": 5},
        outcome="GRANTED",
    )
    assert "entry_hash" in entry1
    assert len(entry1["entry_hash"]) == 64  # SHA-256 hex string

    entry2 = sec.log_audit_entry(
        client_id="unit_102",
        action="road_closure",
        details={"edge": [1, 2]},
        outcome="REJECTED_UNAUTHORIZED",
    )

    logs = sec.read_audit_logs()
    assert len(logs) == 2
    assert logs[0]["client_id"] == "unit_101"
    assert logs[1]["outcome"] == "REJECTED_UNAUTHORIZED"
