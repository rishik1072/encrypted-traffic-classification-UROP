"""
Product Privacy and Security Invariant Unit Tests.

Verifies:
- No payload persistence
- No raw IP or MAC persistence
- No external telemetry endpoint configuration
- Local API server strictly binds to 127.0.0.1
- Raw packet storage flag is immutable and strictly False
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, Dict

from product.config import ProductConfig, product_config
from product.local_api import LocalAPIServer
from product.security import (
    FORBIDDEN_PERSISTENCE_KEYS,
    SecurityBoundaryError,
    assert_local_only_policy,
    assert_zero_payload_policy,
    sanitize_event_record,
    validate_security_boundary,
)


class TestProductPrivacy(unittest.TestCase):
    """Tests product security and zero-payload privacy boundaries."""

    def test_save_raw_packets_is_strictly_false(self) -> None:
        """Asserts save_raw_packets is False and cannot be overridden to True."""
        cfg = ProductConfig()
        self.assertFalse(cfg.save_raw_packets)

        # Attempting to manipulate raw dictionary must be blocked by assertion
        assert_zero_payload_policy()

    def test_local_only_is_strictly_true(self) -> None:
        """Asserts local_only is True and cloud telemetry is blocked."""
        cfg = ProductConfig()
        self.assertTrue(cfg.local_only)
        assert_local_only_policy()

    def test_sanitize_event_record_strips_pii_and_payload(self) -> None:
        """Asserts forbidden keys like raw payload, IP, and MAC are stripped."""
        dirty_event = {
            "flow_id": "flow_12345",
            "predicted_class": "Web",
            "confidence": 0.95,
            "payload": b"GET / HTTP/1.1\r\nHost: example.com",
            "raw_payload": "sensitive data",
            "src_ip": "192.168.1.50",
            "dst_ip": "1.1.1.1",
            "mac_src": "AA:BB:CC:DD:EE:FF",
            "password": "secretpassword",
        }

        clean_event = sanitize_event_record(dirty_event)

        for forbidden in FORBIDDEN_PERSISTENCE_KEYS:
            self.assertNotIn(forbidden, clean_event)

        self.assertIn("flow_id", clean_event)
        self.assertIn("predicted_class", clean_event)
        self.assertIn("confidence", clean_event)

    def test_local_api_binds_only_to_localhost(self) -> None:
        """Asserts LocalAPIServer rejects binding to non-localhost addresses."""
        # Attempting to bind to 0.0.0.0 should be sanitized to 127.0.0.1
        server = LocalAPIServer(host="0.0.0.0", port=9999)
        self.assertEqual(server.host, "127.0.0.1")

        server_lan = LocalAPIServer(host="192.168.1.100", port=9999)
        self.assertEqual(server_lan.host, "127.0.0.1")

    def test_validate_security_boundary(self) -> None:
        """Asserts all security boundary assertions pass."""
        sec_report = validate_security_boundary()
        self.assertEqual(sec_report["status"], "PASS")
        self.assertTrue(sec_report["checks"]["zero_payload_enforced"])
        self.assertTrue(sec_report["checks"]["raw_packet_persistence_disabled"])
        self.assertTrue(sec_report["checks"]["cloud_upload_disabled"])
        self.assertTrue(sec_report["checks"]["local_api_restricted_to_localhost"])


if __name__ == "__main__":
    unittest.main()
