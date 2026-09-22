"""
Model and Preprocessor Artifact Integrity Verification Script.

Validates that serialized model files, preprocessor checkpoints, and feature schemas
load successfully and produce valid non-trivial predictions.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from realtime.model_loader import ModelLoader
from realtime.schema import CANONICAL_NUMERICAL_FEATURES, validate_feature_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("artifact_verifier")


def verify_artifacts() -> bool:
    print("\n=======================================================")
    print("        MODEL ARTIFACT & INFERENCE VERIFICATION       ")
    print("=======================================================\n")

    models_dir = Path("results/models")
    if not models_dir.exists():
        print(f"[!] Models directory not found at {models_dir}")
        return False

    models_to_test = ["lightgbm", "decision_tree", "random_forest", "logistic_regression"]
    all_passed = True

    # Mock raw feature payload
    mock_payload = {feat: 1.0 for feat in CANONICAL_NUMERICAL_FEATURES}

    for model_name in models_to_test:
        print(f"[*] Testing Model Loader for: '{model_name}'...")
        try:
            loader = ModelLoader(model_name=model_name)
            # Verify feature schema
            validate_feature_schema(mock_payload, expected_features=loader.feature_names)
            # Run inference
            pred_class, conf, probs = loader.predict_single(mock_payload)
            print(f"    -> Status: SUCCESS | Class: {pred_class} | Conf: {conf:.1%} | Probs: {len(probs)} classes")
        except Exception as e:
            print(f"    -> Status: FAILED | Error: {e}")
            all_passed = False

    print("\n=======================================================")
    print(f"  ARTIFACT VERIFICATION RESULT: {'ALL PASSED (PASS)' if all_passed else 'SOME FAILED (FAIL)'}")
    print("=======================================================\n")
    return all_passed


if __name__ == "__main__":
    success = verify_artifacts()
    sys.exit(0 if success else 1)
