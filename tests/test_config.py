import sys
import unittest
from pathlib import Path
import yaml

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig(unittest.TestCase):
    def test_config_loading(self):
        config_path = Path(__file__).parent.parent / "config.yaml"
        self.assertTrue(config_path.exists())

        try:
            import yaml  # type: ignore
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            self.assertIn("traffic_classes", cfg)
            self.assertEqual(
                set(cfg["traffic_classes"]),
                {"Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"},
            )
            self.assertIn("features", cfg)
            self.assertIn("numerical_features", cfg["features"])
            self.assertGreater(len(cfg["features"]["numerical_features"]), 10)
        except ImportError:
            # Basic fallback validation if PyYAML is not installed in the global interpreter
            with open(config_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Web", text)
            self.assertIn("Video", text)
            self.assertIn("traffic_classes", text)


if __name__ == "__main__":
    unittest.main()
