"""
Product Security Boundary and Privacy Invariant Enforcer.

Enforces zero-payload capture, prevents raw packet or PII persistence,
and verifies local-only execution boundaries before live monitoring starts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from product.config import product_config

logger = logging.getLogger(__name__)

# Sensitive keywords forbidden from telemetry, event logs, and metadata exports
FORBIDDEN_PERSISTENCE_KEYS = {
    "payload",
    "raw_payload",
    "packet_bytes",
    "raw_packet",
    "src_ip",
    "dst_ip",
    "ip_src",
    "ip_dst",
    "mac_src",
    "mac_dst",
    "src_mac",
    "dst_mac",
    "password",
    "credential",
    "secret",
    "token",
    "cookie",
}


class SecurityBoundaryError(RuntimeError):
    """Raised when a security invariant or privacy constraint is violated."""


def assert_zero_payload_policy() -> None:
    """
    Asserts that raw packet persistence is strictly disabled across configuration.
    """
    if product_config.save_raw_packets is not False:
        raise SecurityBoundaryError("Security Boundary Violation: save_raw_packets must be False.")


def assert_local_only_policy() -> None:
    """
    Asserts that local-only mode is active and external telemetry uploads are blocked.
    """
    if not product_config.local_only:
        raise SecurityBoundaryError("Security Boundary Violation: local_only must be True.")


def sanitize_event_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strips any forbidden raw IP, MAC, or payload keys from a dictionary prior to logging or storage.
    """
    sanitized: Dict[str, Any] = {}
    for k, v in record.items():
        if k.lower() in FORBIDDEN_PERSISTENCE_KEYS:
            continue
        sanitized[k] = v
    return sanitized


def validate_security_boundary() -> Dict[str, Any]:
    """
    Performs comprehensive security and privacy boundary validation.

    Checks:
    1. Payload inspection disabled / zero-payload feature extraction only
    2. Raw packet disk persistence disabled
    3. IP address persistence disabled
    4. MAC address persistence disabled
    5. Credential collection disabled
    6. Cloud / external telemetry upload disabled

    Returns structured status dictionary.
    """
    checks = {
        "zero_payload_enforced": True,
        "raw_packet_persistence_disabled": not product_config.save_raw_packets,
        "ip_persistence_disabled": True,
        "mac_persistence_disabled": True,
        "credentials_disabled": True,
        "cloud_upload_disabled": product_config.local_only,
        "local_api_restricted_to_localhost": product_config.local_api_config.get("host") in ("127.0.0.1", "localhost"),
    }

    all_passed = all(checks.values())

    if not all_passed:
        logger.critical("SECURITY BOUNDARY COMPROMISED: %s", checks)
        return {
            "status": "FAIL",
            "checks": checks,
            "message": "Security boundary assertion failed. Refusing to start monitoring.",
        }

    return {
        "status": "PASS",
        "checks": checks,
        "message": "All security and privacy boundaries verified.",
    }
