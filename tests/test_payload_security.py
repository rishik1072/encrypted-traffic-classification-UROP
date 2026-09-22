"""
Security and Privacy Tests for Traffic Collection.

Strictly asserts that exported metadata NEVER contains payload bytes,
HTTP body contents, or credential-like fields.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from capture.metadata_exporter import MetadataExporter, WHITELISTED_METADATA_FIELDS


class TestPayloadSecurity(unittest.TestCase):
    def test_strict_field_whitelisting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MetadataExporter(output_dir=tmpdir)
            dirty_packet = {
                "timestamp": 100.0,
                "length": 1420,
                "protocol": "TCP",
                "source_port": 443,
                "destination_port": 54321,
                "payload": "GET /secret HTTP/1.1\r\nAuthorization: Bearer xyz",
                "raw_bytes": b"\x16\x03\x03\x00\x05SECRET",
                "cookie": "session_id=attacker_token",
                "user_password": "supersecretpassword",
            }

            meta_file = exporter.export_session_metadata("sec_test_01", "Web", [dirty_packet])
            with open(meta_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                rows = list(reader)

            # Check that only whitelisted fields are present in header
            for col in fieldnames:
                self.assertIn(col, WHITELISTED_METADATA_FIELDS)

            # Assert forbidden content is absent from the file
            with open(meta_file, "r", encoding="utf-8") as f:
                raw_text = f.read()

            self.assertNotIn("Authorization", raw_text)
            self.assertNotIn("supersecretpassword", raw_text)
            self.assertNotIn("attacker_token", raw_text)
            self.assertNotIn("GET /secret", raw_text)


if __name__ == "__main__":
    unittest.main()
