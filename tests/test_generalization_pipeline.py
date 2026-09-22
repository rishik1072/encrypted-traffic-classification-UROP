import csv
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.calibration_analysis import compute_calibration_curve
from training.class_mapping import map_external_label
from training.dataset_manifest_hasher import compute_file_sha256
from training.statistical_analysis import compute_bootstrap_ci


class TestGeneralizationPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_class_mapping(self):
        # Known mappings
        self.assertEqual(map_external_label("youtube"), "Video")
        self.assertEqual(map_external_label("HTTPS"), "Web")
        self.assertEqual(map_external_label("skype"), "VoIP")
        self.assertEqual(map_external_label("sftp"), "File Transfer")
        self.assertEqual(map_external_label("whatsapp"), "Messaging")
        # Unknown falls back to Other
        self.assertEqual(map_external_label("unknown_protocol_xyz"), "Other")

    def test_calibration_curve_calculation(self):
        confidences = [0.9, 0.8, 0.7, 0.6]
        correctness = [True, True, True, False]
        buckets, ece = compute_calibration_curve(confidences, correctness, num_buckets=2)
        self.assertEqual(len(buckets), 2)
        self.assertTrue(0.0 <= ece <= 1.0)

    def test_bootstrap_uncertainty(self):
        y_true = [0, 1, 2, 0, 1, 2]
        y_pred = [0, 1, 2, 0, 1, 0]
        classes = ["Web", "Video", "Messaging"]
        res = compute_bootstrap_ci(y_true, y_pred, classes, metric_name="accuracy", n_bootstraps=50)
        self.assertIn("estimate", res)
        self.assertIn("lower_ci", res)
        self.assertIn("upper_ci", res)
        self.assertTrue(res["lower_ci"] <= res["estimate"] <= res["upper_ci"] + 0.1)

    def test_sha256_hasher(self):
        test_f = self.base_path / "sample.txt"
        with open(test_f, "w") as f:
            f.write("hello network traffic")
        sha = compute_file_sha256(test_f)
        self.assertEqual(len(sha), 64)


if __name__ == "__main__":
    unittest.main()
