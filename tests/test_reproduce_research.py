"""
Unit & Integration Tests for Reproducible Research Command.

Verifies:
1. CLI flag argument parsing and dependency ordering
2. Loud failure on missing or synthetic datasets
3. Integrity of results/research_manifest.json
4. Granular stage execution (--dataset, --baseline, etc.)
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from scripts.reproduce_research import (
    ResearchPipelineRunner,
    resolve_stages,
)


class TestReproduceResearch(unittest.TestCase):
    """Tests research orchestrator and fail-loud safety boundaries."""

    def test_stage_resolution_all(self) -> None:
        """Asserts --all flag resolves all 15 stages in order."""
        args = MagicMock()
        args.all = True
        stages = resolve_stages(args)
        self.assertEqual(len(stages), 15)
        self.assertEqual(stages[0], "1_environment_verification")
        self.assertEqual(stages[-1], "15_research_summary_generation")

    def test_stage_resolution_dataset_flag(self) -> None:
        """Asserts --dataset flag includes environment and dataset audits."""
        args = MagicMock()
        args.all = False
        args.dataset = True
        args.baseline = False
        args.features = False
        args.generalization = False
        args.early = False
        args.selective = False
        args.latency = False
        args.skip_figures = True

        stages = resolve_stages(args)
        self.assertIn("1_environment_verification", stages)
        self.assertIn("2_dataset_verification", stages)
        self.assertIn("3_dataset_quality_audit", stages)
        self.assertIn("4_leakage_audit", stages)
        self.assertNotIn("5_baseline_benchmark", stages)

    def test_fail_loud_on_synthetic_dataset_claim(self) -> None:
        """Asserts runner fails loudly if asked to run research on synthetic fixture."""
        runner = ResearchPipelineRunner(dataset_id="dataset_v1")
        # Stage 2 must fail loudly with RuntimeError
        with self.assertRaises(RuntimeError) as ctx:
            runner.stage_2_dataset_verification()
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx.exception))

    def test_fail_loud_on_nonexistent_dataset(self) -> None:
        """Asserts runner fails loudly on missing dataset."""
        runner = ResearchPipelineRunner(dataset_id="nonexistent_dataset_id")
        with self.assertRaises(Exception):
            runner.stage_2_dataset_verification()

    def test_research_manifest_schema(self) -> None:
        """Validates that research_manifest.json conforms to the required schema."""
        manifest_path = Path("results/research_manifest.json")
        self.assertTrue(manifest_path.exists(), "results/research_manifest.json not found")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = [
            "manifest_version",
            "generated_at",
            "codebase_version",
            "environment",
            "dataset",
            "feature_profile",
            "split_strategy",
            "random_seed",
            "model_versions",
            "experiments",
            "stages_executed",
            "artifact_paths",
        ]
        for k in required_keys:
            self.assertIn(k, data, f"Manifest missing required key: {k}")

        self.assertEqual(data["dataset"]["origin"], "REAL_DATA")
        self.assertEqual(data["dataset"]["version"], "2.0.0")
        self.assertEqual(data["feature_profile"], "lightweight_10")
        self.assertEqual(data["random_seed"], 42)


if __name__ == "__main__":
    unittest.main()
