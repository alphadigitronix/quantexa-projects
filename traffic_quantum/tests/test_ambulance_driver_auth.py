"""Unit tests for Ambulance Driver CAD Registration, Authentication & Security Governance."""

import os
import json
import time
import pytest
from traffic_quantum.hospital_maps import (
    load_registered_drivers,
    register_driver,
    approve_driver,
    authenticate_driver,
    hash_pin,
    verify_pin,
    save_registered_driver,
    generate_hospital_maps_html,
    EMS_DRIVERS_FILE,
)
from traffic_quantum.security import SecurityService


def test_load_registered_drivers_default(tmp_path, monkeypatch):
    """Verify that default EMS driver fleet loads properly with APPROVED status and bcrypt hashes."""
    custom_file = os.path.join(tmp_path, "test_drivers_default.json")
    monkeypatch.setattr("traffic_quantum.hospital_maps.EMS_DRIVERS_FILE", custom_file)

    drivers = load_registered_drivers()
    assert isinstance(drivers, dict)
    assert len(drivers) >= 2
    assert "TN-09-EMS-108" in drivers

    rajesh = drivers["TN-09-EMS-108"]
    assert rajesh["name"] == "Rajesh Kumar"
    assert rajesh["vehicle_number"] == "TN-09-EMS-108"
    assert rajesh["status"] == "APPROVED"
    assert "pin_hash" in rajesh
    assert rajesh["pin_hash"].startswith("$2b$") or rajesh["pin_hash"].startswith("$2a$")
    assert verify_pin("108080", rajesh["pin_hash"])


def test_pin_hashing_and_minimum_6_character_enforcement():
    """Verify that PINs must be at least 6 characters and are bcrypt-hashed."""
    with pytest.raises(ValueError, match="at least 6 characters"):
        hash_pin("1234")  # 4 digits rejected

    with pytest.raises(ValueError, match="at least 6 characters"):
        hash_pin("12345")  # 5 digits rejected

    hashed = hash_pin("Secret123")
    assert hashed.startswith("$2b$")
    assert verify_pin("Secret123", hashed) is True
    assert verify_pin("WrongPass", hashed) is False


def test_registration_creates_pending_account(tmp_path, monkeypatch):
    """(a) Registration creates a PENDING account that cannot log in until approved."""
    custom_file = os.path.join(tmp_path, "test_drivers_reg.json")
    monkeypatch.setattr("traffic_quantum.hospital_maps.EMS_DRIVERS_FILE", custom_file)

    # 1. Registration with < 6 chars must fail
    ok, msg, _ = register_driver(
        name="Officer Priya",
        vehicle_number="TN-02-EMS-5555",
        phone="+91 98400 55555",
        vehicle_type="Advanced Life Support (ALS Trauma Pod)",
        hospital="Apollo Hospitals",
        pin="1234",  # Too short
    )
    assert ok is False
    assert "at least 6 characters" in msg

    # 2. Registration with valid PIN creates PENDING account
    ok, msg, rec = register_driver(
        name="Officer Priya",
        vehicle_number="TN-02-EMS-5555",
        phone="+91 98400 55555",
        vehicle_type="Advanced Life Support (ALS Trauma Pod)",
        hospital="Apollo Hospitals",
        pin="StrongPass789",
    )
    assert ok is True
    assert rec["status"] == "PENDING"
    assert "pin_hash" in rec
    assert rec["pin_hash"].startswith("$2b$")

    # 3. PENDING account is blocked from login
    auth_ok, auth_msg, d, tok = authenticate_driver("TN-02-EMS-5555", "StrongPass789")
    assert auth_ok is False
    assert "PENDING approval" in auth_msg
    assert tok is None

    # 4. Dispatcher approves account
    appr_ok, appr_msg = approve_driver("TN-02-EMS-5555", approved_by="Supervisor_Karthik")
    assert appr_ok is True
    assert "approved" in appr_msg.lower()

    # 5. Approved account can now log in successfully and receives JWT
    auth_ok, auth_msg, d_appr, tok = authenticate_driver("TN-02-EMS-5555", "StrongPass789")
    assert auth_ok is True
    assert tok is not None
    assert d_appr["status"] == "APPROVED"


def test_account_lockout_after_5_failed_attempts(tmp_path, monkeypatch):
    """(c) Lockout after 5 failed attempts with exponential backoff."""
    custom_file = os.path.join(tmp_path, "test_drivers_lockout.json")
    monkeypatch.setattr("traffic_quantum.hospital_maps.EMS_DRIVERS_FILE", custom_file)

    register_driver(
        name="Officer Vikram",
        vehicle_number="TN-03-EMS-3333",
        phone="+91 98400 33333",
        vehicle_type="Basic Life Support (BLS Quick Response)",
        hospital="Fortis Malar Hospital",
        pin="SecurePin2026",
    )
    approve_driver("TN-03-EMS-3333")

    # Attempt 1-4 with wrong PIN
    for i in range(1, 5):
        ok, msg, _, _ = authenticate_driver("TN-03-EMS-3333", "WrongPassword")
        assert ok is False
        assert f"Attempt {i} of 5" in msg

    # 5th failed attempt triggers lockout
    ok_5, msg_5, _, _ = authenticate_driver("TN-03-EMS-3333", "WrongPassword")
    assert ok_5 is False
    assert "Account locked out" in msg_5

    # 6th attempt (even with CORRECT password) is rejected while locked out
    ok_locked, msg_locked, _, _ = authenticate_driver("TN-03-EMS-3333", "SecurePin2026")
    assert ok_locked is False
    assert "Account is locked" in msg_locked


def test_audit_logging_and_jwt_issuance(tmp_path, monkeypatch):
    """(d) Audit log records events and (e) JWT is issued only from login session."""
    custom_file = os.path.join(tmp_path, "test_drivers_audit.json")
    audit_file = os.path.join(tmp_path, "test_audit.log")
    monkeypatch.setattr("traffic_quantum.hospital_maps.EMS_DRIVERS_FILE", custom_file)
    monkeypatch.setattr("traffic_quantum.security.DEFAULT_CONFIG.security.audit_log_file", audit_file)

    sec = SecurityService()
    sec.log_file = audit_file

    # 1. Register driver
    register_driver(
        name="Officer Deepa",
        vehicle_number="TN-04-EMS-4444",
        phone="+91 98400 44444",
        vehicle_type="Mobile Stroke Unit",
        hospital="Kauvery Hospital",
        pin="CadDriver2026",
    )

    # 2. Approve driver
    approve_driver("TN-04-EMS-4444", approved_by="Dispatcher_01")

    # 3. Failed login
    authenticate_driver("TN-04-EMS-4444", "WrongCode")

    # 4. Successful login -> issues JWT
    ok, msg, d, jwt_token = authenticate_driver("TN-04-EMS-4444", "CadDriver2026")
    assert ok is True
    assert jwt_token is not None

    # Verify JWT validity with SecurityService
    valid, claims, err = sec.verify_token(jwt_token)
    assert valid is True
    assert claims["sub"] == "TN-04-EMS-4444"
    assert claims["role"] == "emergency_dispatch"

    # Verify audit log entries
    logs = sec.read_audit_logs(limit=20)
    actions = [entry.get("action") for entry in logs]
    assert "driver_registration" in actions
    assert "driver_approval" in actions
    assert "driver_login_failed" in actions
    assert "driver_login" in actions


def test_generate_hospital_maps_html_injects_driver_data():
    """Verify that the generated HTML template contains the active driver and vehicle callsign."""
    html = generate_hospital_maps_html(
        driver_name="S. Venkatesh",
        vehicle_number="TN-07-EMS-1084",
        hospital="Kilpauk Medical College Hospital",
    )
    assert "TN-07-EMS-1084" in html
    assert "S. Venkatesh" in html
    assert 'value="TN-07-EMS-1084 (S. Venkatesh)"' in html
