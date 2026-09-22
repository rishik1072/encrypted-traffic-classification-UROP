"""
Product Network Adapter Discovery and Validation Unit Tests.

Verifies:
- Adapter enumeration and metadata structure
- Default adapter resolution logic
- Exact and fuzzy adapter validation
- Graceful handling of invalid or missing adapters
- Mocking of Npcap availability and interface discovery states
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from product.adapter_manager import get_default_adapter, list_adapters, validate_adapter


class TestProductAdapters(unittest.TestCase):
    """Tests network adapter discovery and resolution manager."""

    def test_list_adapters_structure(self) -> None:
        """Asserts list_adapters returns required fields."""
        adapters = list_adapters()
        self.assertIsInstance(adapters, list)

        for ad in adapters:
            self.assertIn("friendly_name", ad)
            self.assertIn("interface_description", ad)
            self.assertIn("npcap_name", ad)
            self.assertIn("status", ad)
            self.assertIn("link_speed", ad)
            self.assertIn(ad["status"], ("UP", "DOWN"))

    def test_validate_adapter_valid_and_invalid(self) -> None:
        """Tests adapter validation against existing and nonexistent adapters."""
        adapters = list_adapters()
        if adapters:
            first_name = adapters[0]["friendly_name"]
            res = validate_adapter(first_name)
            self.assertTrue(res["valid"])
            self.assertIsNotNone(res["adapter"])

        # Non-existent adapter
        invalid_res = validate_adapter("NonExistentAdapter_9999")
        self.assertFalse(invalid_res["valid"])
        self.assertIsNone(invalid_res["adapter"])
        self.assertIn("not found", invalid_res["message"].lower())

    @patch("product.adapter_manager.list_scapy_interfaces")
    def test_mock_adapter_priority_wifi_over_ethernet(self, mock_scapy_list: MagicMock) -> None:
        """Asserts get_default_adapter prioritizes active Wi-Fi over Ethernet."""
        mock_scapy_list.return_value = [
            {
                "identifier": "eth0",
                "friendly_name": "Ethernet",
                "description": "Realtek PCIe GbE",
                "network_name": "\\Device\\NPF_{ETH}",
                "guid": "{ETH}",
                "ip": "192.168.1.10",
                "is_up": True,
                "scapy_object": MagicMock(),
            },
            {
                "identifier": "wlan0",
                "friendly_name": "Wi-Fi",
                "description": "Intel Wi-Fi 6 AX201",
                "network_name": "\\Device\\NPF_{WIFI}",
                "guid": "{WIFI}",
                "ip": "192.168.1.20",
                "is_up": True,
                "scapy_object": MagicMock(),
            },
        ]

        def_ad = get_default_adapter()
        self.assertIsNotNone(def_ad)
        self.assertEqual(def_ad["friendly_name"], "Wi-Fi")

    @patch("product.adapter_manager.list_scapy_interfaces")
    def test_mock_npcap_unavailable_empty_list(self, mock_scapy_list: MagicMock) -> None:
        """Asserts list_adapters handles empty or unavailable Npcap gracefully."""
        mock_scapy_list.return_value = []

        adapters = list_adapters()
        self.assertEqual(adapters, [])

        def_ad = get_default_adapter()
        self.assertIsNone(def_ad)

        val_res = validate_adapter("Wi-Fi")
        self.assertFalse(val_res["valid"])
        self.assertIn("No network adapters detected", val_res["message"])


if __name__ == "__main__":
    unittest.main()
