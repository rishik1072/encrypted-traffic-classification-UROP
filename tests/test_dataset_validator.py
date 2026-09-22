import csv
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset_validator import DatasetValidator


class TestDatasetValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.pcap_dir = self.base_path / "data/raw/pcap"
        self.pcap_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy pcap file
        (self.pcap_dir / "valid_sample.pcap").touch()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_manifest(self, rows):
        manifest_path = self.base_path / "manifest.csv"
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "file_id",
                    "pcap_path",
                    "traffic_class",
                    "source",
                    "capture_date",
                    "duration_seconds",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        return manifest_path

    def test_valid_manifest(self):
        manifest_path = self._write_manifest([
            {
                "file_id": "test_01",
                "pcap_path": "data/raw/pcap/valid_sample.pcap",
                "traffic_class": "Web",
                "source": "Lab",
                "capture_date": "2026-08-23",
                "duration_seconds": "60",
            }
        ])
        validator = DatasetValidator(
            manifest_path=manifest_path,
            allowed_classes=["Web", "Video", "Other"],
            base_dir=self.base_path,
        )
        res = validator.validate(check_file_existence=True)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.valid_records, 1)
        self.assertEqual(res.class_counts.get("Web"), 1)

    def test_invalid_label_detection(self):
        manifest_path = self._write_manifest([
            {
                "file_id": "test_02",
                "pcap_path": "data/raw/pcap/valid_sample.pcap",
                "traffic_class": "MalwareBitTorrent",  # Not allowed
                "source": "Lab",
                "capture_date": "2026-08-23",
                "duration_seconds": "60",
            }
        ])
        validator = DatasetValidator(
            manifest_path=manifest_path,
            allowed_classes=["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            base_dir=self.base_path,
        )
        res = validator.validate(check_file_existence=True)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.invalid_records, 1)
        self.assertTrue(any("invalid" in err.lower() for err in res.errors))

    def test_missing_pcap_detection(self):
        manifest_path = self._write_manifest([
            {
                "file_id": "test_03",
                "pcap_path": "data/raw/pcap/non_existent.pcap",
                "traffic_class": "Web",
                "source": "Lab",
                "capture_date": "2026-08-23",
                "duration_seconds": "60",
            }
        ])
        validator = DatasetValidator(
            manifest_path=manifest_path,
            allowed_classes=["Web"],
            base_dir=self.base_path,
        )
        res = validator.validate(check_file_existence=True)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("not found" in err.lower() for err in res.errors))

    def test_duplicate_file_id_detection(self):
        manifest_path = self._write_manifest([
            {
                "file_id": "duplicate_id",
                "pcap_path": "data/raw/pcap/valid_sample.pcap",
                "traffic_class": "Web",
                "source": "Lab",
                "capture_date": "2026-08-23",
                "duration_seconds": "60",
            },
            {
                "file_id": "duplicate_id",
                "pcap_path": "data/raw/pcap/valid_sample.pcap",
                "traffic_class": "Web",
                "source": "Lab",
                "capture_date": "2026-08-23",
                "duration_seconds": "60",
            },
        ])
        validator = DatasetValidator(
            manifest_path=manifest_path,
            allowed_classes=["Web"],
            base_dir=self.base_path,
        )
        res = validator.validate(check_file_existence=True)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("duplicate" in err.lower() for err in res.errors))


if __name__ == "__main__":
    unittest.main()
