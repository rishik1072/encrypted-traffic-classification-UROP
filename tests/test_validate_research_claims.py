"""
Unit & Integration Tests for Hardened Research Claim Validator (Task 3B).

Verifies:
1. Baseline provenance enforcement: matching provenance, mismatched provenance,
   unavailable provenance, and hybrid benchmark disclosure.
2. Generalization table claim verification: sample counts, baseline lookup,
   exact F1 difference calculations, missing regimes, and asymmetric tunnel degradation.
3. Evidence-driven latency validation: decision tree warm inference, feature extraction,
   non-negative finite percentiles, percentile monotonicity, and threshold checks.
4. Real-time pipeline invariants: independent testing of each privacy/security invariant,
   flow accounting counters, LIVE_MODE status, and DEMO_MODE segregation.
5. Selective prediction claims: validation-split evidence requirement, threshold matching,
   coverage and error rate consistency, and monotonic risk reduction.
6. Robust numeric parsing: structured rejection of NaN, Inf, negative counts, non-integers.
7. Honest overall status reporting: nonzero exit status for failures, UNVERIFIED claims noted.
8. Current repository audit: verification of all active research tables and provenance guard.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_research_claims import (
    REQUIRED_BASELINE_COLUMNS,
    REQUIRED_EARLY_PREDICTION_COLUMNS,
    REQUIRED_GENERALIZATION_COLUMNS,
    REQUIRED_LATENCY_COLUMNS,
    REQUIRED_REALTIME_COLUMNS,
    REQUIRED_SELECTIVE_PREDICTION_COLUMNS,
    ClaimResult,
    ResearchClaimValidator,
    ValidationStatus,
    main,
    safe_float,
    safe_int,
    safe_probability,
    validate_baseline_table,
    validate_claims,
    validate_claims_ledger,
    validate_dataset_provenance,
    validate_early_prediction_table,
    validate_generalization_table,
    validate_latency_table,
    validate_realtime_table,
    validate_selective_prediction_table,
    validate_stale_synthetic_rejection,
    verify_early_accuracy_denominators,
)
from training.dataset_registry import DatasetOrigin, DatasetRegistry


class TestValidateResearchClaims(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tables_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # =========================================================================
    # 1. Missing Result Files and Missing Required Columns
    # =========================================================================
    def test_missing_result_files_produce_fail(self) -> None:
        """Asserts that missing result CSV files produce a clear FAIL status."""
        missing_baseline = self.tables_dir / "research_baseline.csv"
        res_baseline = validate_baseline_table(missing_baseline)
        self.assertEqual(res_baseline.status, ValidationStatus.FAIL)
        self.assertIn("does not exist", res_baseline.reason)

        missing_early = self.tables_dir / "research_early_prediction.csv"
        res_early = validate_early_prediction_table(missing_early)
        self.assertEqual(res_early.status, ValidationStatus.FAIL)
        self.assertIn("does not exist", res_early.reason)

        # Overall validation must fail when required files are missing
        success = validate_claims(tables_dir=self.tables_dir, project_root=PROJECT_ROOT)
        self.assertFalse(success)

    def test_missing_required_columns_produce_fail(self) -> None:
        """Asserts that omitted required columns in empirical CSV tables produce FAIL."""
        incomplete_baseline = self.tables_dir / "research_baseline.csv"
        cols = [c for c in REQUIRED_BASELINE_COLUMNS if c not in ("test_macro_f1", "is_selected_winner")]
        with open(incomplete_baseline, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerow({c: "0.5" for c in cols})

        res_b = validate_baseline_table(incomplete_baseline)
        self.assertEqual(res_b.status, ValidationStatus.FAIL)
        self.assertIn("Missing required columns", res_b.reason)
        self.assertIn("test_macro_f1", res_b.reason)

        incomplete_early = self.tables_dir / "research_early_prediction.csv"
        e_cols = [c for c in REQUIRED_EARLY_PREDICTION_COLUMNS if c not in ("coverage", "flows_classified")]
        with open(incomplete_early, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=e_cols)
            writer.writeheader()
            writer.writerow({c: "1" for c in e_cols})

        res_e = validate_early_prediction_table(incomplete_early)
        self.assertEqual(res_e.status, ValidationStatus.FAIL)
        self.assertIn("Missing required columns", res_e.reason)
        self.assertIn("coverage", res_e.reason)

    # =========================================================================
    # 2. Invalid or Non-Finite Metrics
    # =========================================================================
    def test_invalid_or_non_finite_metrics_produce_fail(self) -> None:
        """Asserts that NaN, Inf, negative latencies, or out-of-range probabilities produce FAIL."""
        baseline_csv = self.tables_dir / "research_baseline.csv"

        def write_baseline_row(overrides: dict) -> None:
            row = {
                "experiment_id": "EXP-R09-DT",
                "dataset_version": "2.0.0",
                "dataset_origin": "HYBRID_PERTURBED",
                "feature_profile": "baseline_21_zero_payload",
                "model": "decision_tree",
                "split_strategy": "group_aware_session_stratified_70_15_15",
                "train_count": "205",
                "validation_count": "48",
                "test_count": "48",
                "val_accuracy": "0.5417",
                "val_macro_f1": "0.5382",
                "val_balanced_accuracy": "0.5417",
                "test_accuracy": "0.5833",
                "test_macro_precision": "0.6657",
                "test_macro_recall": "0.5833",
                "test_macro_f1": "0.5802",
                "test_weighted_f1": "0.5802",
                "test_balanced_accuracy": "0.5833",
                "mean_inference_latency_ms": "0.0866",
                "median_inference_latency_ms": "0.0694",
                "p95_inference_latency_ms": "0.1893",
                "model_size_kb": "9.58",
                "is_selected_winner": "YES",
            }
            row.update(overrides)
            with open(baseline_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_BASELINE_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

        # Case A: NaN in test_macro_f1
        write_baseline_row({"test_macro_f1": "NaN"})
        res = validate_baseline_table(baseline_csv)
        self.assertEqual(res.status, ValidationStatus.FAIL)
        self.assertIn("test_macro_f1", res.reason)

        # Case B: Probability > 1.0
        write_baseline_row({"val_accuracy": "1.4500"})
        res = validate_baseline_table(baseline_csv)
        self.assertEqual(res.status, ValidationStatus.FAIL)
        self.assertIn("val_accuracy", res.reason)

        # Case C: Negative latency
        write_baseline_row({"mean_inference_latency_ms": "-0.5000"})
        res = validate_baseline_table(baseline_csv)
        self.assertEqual(res.status, ValidationStatus.FAIL)
        self.assertIn("Invalid latency", res.reason)

        # Case D: Non-integer sample count
        write_baseline_row({"train_count": "205.5"})
        res = validate_baseline_table(baseline_csv)
        self.assertEqual(res.status, ValidationStatus.FAIL)
        self.assertIn("Non-integer count", res.reason)

    # =========================================================================
    # 3. Stale Synthetic Summary Values
    # =========================================================================
    def test_stale_synthetic_summary_values_rejected(self) -> None:
        """Asserts that obsolete 0.95 Macro-F1 synthetic fixtures are rejected from current empirical results."""
        stale_summary = self.tables_dir / "final_results_summary.csv"
        with open(stale_summary, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["evaluation_regime", "model", "macro_f1", "sample_count"])
            writer.writerow(["Random Split (Baseline)", "LightGBM", "0.9500", "12"])

        res_stale = validate_stale_synthetic_rejection(self.tables_dir)
        self.assertEqual(res_stale.status, ValidationStatus.PASS)
        self.assertIn("STALE_SYNTHETIC", res_stale.reason)
        self.assertIn("quarantined", res_stale.reason)

        # Synthetic fixture (0.95 F1 on <=12 samples) presented as baseline must FAIL
        synthetic_baseline = self.tables_dir / "research_baseline.csv"
        row = {
            "experiment_id": "EXP-01-SYNTHETIC",
            "dataset_version": "1.0.0",
            "dataset_origin": "SYNTHETIC_FIXTURE",
            "feature_profile": "baseline_21",
            "model": "lightgbm",
            "split_strategy": "random_split",
            "train_count": "8",
            "validation_count": "2",
            "test_count": "12",
            "val_accuracy": "0.9500",
            "val_macro_f1": "0.9500",
            "val_balanced_accuracy": "0.9500",
            "test_accuracy": "0.9500",
            "test_macro_precision": "0.9500",
            "test_macro_recall": "0.9500",
            "test_macro_f1": "0.9500",
            "test_weighted_f1": "0.9500",
            "test_balanced_accuracy": "0.9500",
            "mean_inference_latency_ms": "0.5000",
            "median_inference_latency_ms": "0.5000",
            "p95_inference_latency_ms": "0.5000",
            "model_size_kb": "154.0",
            "is_selected_winner": "YES",
        }
        with open(synthetic_baseline, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REQUIRED_BASELINE_COLUMNS)
            writer.writeheader()
            writer.writerow(row)

        res_b = validate_baseline_table(synthetic_baseline)
        self.assertEqual(res_b.status, ValidationStatus.FAIL)
        self.assertIn("Stale synthetic fixture metric", res_b.reason)

    # =========================================================================
    # 4. Hybrid Dataset Provenance Distinction
    # =========================================================================
    def test_hybrid_dataset_provenance_distinction(self) -> None:
        """Asserts that provenance distinguishes pure REAL_DATA from HYBRID_PERTURBED."""
        res_prov = validate_dataset_provenance(PROJECT_ROOT)
        self.assertEqual(res_prov.status, ValidationStatus.PASS)
        self.assertIn("dataset_real_v1 is pure REAL_DATA", res_prov.reason)
        self.assertIn("dataset_v2 is HYBRID_PERTURBED", res_prov.reason)

        reg = DatasetRegistry(PROJECT_ROOT)
        v2 = reg.get_dataset("dataset_v2")
        self.assertEqual(v2.origin, DatasetOrigin.HYBRID_PERTURBED)
        self.assertFalse(v2.is_real_data)
        self.assertTrue(v2.is_hybrid)
        self.assertEqual(v2.physical_flow_count, 121)
        self.assertEqual(v2.synthetic_flow_count, 180)

        real_v1 = reg.get_dataset("dataset_real_v1")
        self.assertEqual(real_v1.origin, DatasetOrigin.REAL_DATA)
        self.assertTrue(real_v1.is_real_data)
        self.assertFalse(real_v1.is_hybrid)
        self.assertEqual(real_v1.synthetic_flow_count, 0)

    # =========================================================================
    # 5. Baseline Provenance Enforcement (Task 3B Hardening)
    # =========================================================================
    def test_baseline_provenance_matching_and_mismatch(self) -> None:
        """
        Validates matching provenance, mismatched provenance, unavailable provenance,
        and hybrid benchmark disclosure.
        """
        baseline_csv = self.tables_dir / "baseline_test.csv"

        def make_baseline_rows(origin: str, version: str) -> list:
            return [
                {
                    "experiment_id": "EXP-R09-DT",
                    "dataset_version": version,
                    "dataset_origin": origin,
                    "feature_profile": "baseline_21_zero_payload",
                    "model": "decision_tree",
                    "split_strategy": "group_aware_session_stratified_70_15_15",
                    "train_count": "205",
                    "validation_count": "48",
                    "test_count": "48",
                    "val_accuracy": "0.5417",
                    "val_macro_f1": "0.5382",
                    "val_balanced_accuracy": "0.5417",
                    "test_accuracy": "0.5833",
                    "test_macro_precision": "0.6657",
                    "test_macro_recall": "0.5833",
                    "test_macro_f1": "0.5802",
                    "test_weighted_f1": "0.5802",
                    "test_balanced_accuracy": "0.5833",
                    "mean_inference_latency_ms": "0.0866",
                    "median_inference_latency_ms": "0.0694",
                    "p95_inference_latency_ms": "0.1893",
                    "model_size_kb": "9.58",
                    "is_selected_winner": "YES",
                }
            ]

        def write_rows(rows: list) -> None:
            with open(baseline_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_BASELINE_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # 1. Mismatched provenance: row asserts REAL_DATA, but v2.0.0 is HYBRID_PERTURBED -> FAIL
        write_rows(make_baseline_rows(origin="REAL_DATA", version="2.0.0"))
        res_mismatch = validate_baseline_table(baseline_csv, PROJECT_ROOT)
        self.assertEqual(res_mismatch.status, ValidationStatus.FAIL)
        self.assertIn("Provenance contradiction", res_mismatch.reason)
        self.assertIn("HYBRID_PERTURBED", res_mismatch.reason)

        # 2. Matching hybrid benchmark disclosure: row truthfully asserts HYBRID_PERTURBED -> PASS
        write_rows(make_baseline_rows(origin="HYBRID_PERTURBED", version="2.0.0"))
        res_hybrid = validate_baseline_table(baseline_csv, PROJECT_ROOT)
        self.assertEqual(res_hybrid.status, ValidationStatus.PASS)
        self.assertEqual(res_hybrid.details.get("benchmark_type"), "HYBRID_PERTURBED")
        self.assertIn("Disclosed as HYBRID_PERTURBED", res_hybrid.reason)

        # 3. Matching pure real data: row asserts REAL_DATA on pure real dataset_real_v1 (1.1.0) -> PASS
        write_rows(make_baseline_rows(origin="REAL_DATA", version="1.1.0"))
        res_real = validate_baseline_table(baseline_csv, PROJECT_ROOT)
        self.assertEqual(res_real.status, ValidationStatus.PASS)
        self.assertEqual(res_real.details.get("benchmark_type"), "REAL_DATA")
        self.assertIn("Verified pure REAL_DATA", res_real.reason)

        # 4. Unavailable provenance: dataset version not registered in DatasetRegistry -> UNVERIFIED
        write_rows(make_baseline_rows(origin="REAL_DATA", version="99.9.9"))
        res_unavail = validate_baseline_table(baseline_csv, PROJECT_ROOT)
        self.assertEqual(res_unavail.status, ValidationStatus.UNVERIFIED)
        self.assertIn("not cataloged in DatasetRegistry", res_unavail.reason)

        # 5. Synthetic fixture dataset used as baseline -> FAIL
        write_rows(make_baseline_rows(origin="SYNTHETIC_FIXTURE", version="1.0.0"))
        res_synth = validate_baseline_table(baseline_csv, PROJECT_ROOT)
        self.assertEqual(res_synth.status, ValidationStatus.FAIL)
        self.assertIn("cannot be used for empirical research baseline", res_synth.reason)

    # =========================================================================
    # 6. Generalization Claims Verification (Task 3B Hardening)
    # =========================================================================
    def test_generalization_claims_verification(self) -> None:
        """
        Validates generalization metrics, sample counts, baseline lookup, exact F1 delta calculation,
        and asymmetric tunnel degradation evidence.
        """
        gen_csv = self.tables_dir / "research_generalization_scorecard.csv"

        valid_rows = [
            {
                "regime_id": "REG-01",
                "regime_name": "1. Random/Group Baseline",
                "dataset_version": "2.0.0",
                "sample_count": "301",
                "train_count": "205",
                "test_count": "48",
                "accuracy": "0.6042",
                "macro_f1": "0.6060",
                "weighted_f1": "0.6060",
                "latency": "16.0520",
                "f1_delta_vs_baseline": "0.0000",
                "robustness_rating": "ROBUST",
            },
            {
                "regime_id": "REG-08a",
                "regime_name": "8a. Tunnel Shift (Tunneled -> Direct)",
                "dataset_version": "2.0.0",
                "sample_count": "301",
                "train_count": "265",
                "test_count": "36",
                "accuracy": "1.0000",
                "macro_f1": "1.0000",
                "weighted_f1": "1.0000",
                "latency": "16.5656",
                "f1_delta_vs_baseline": "0.3940",  # 1.0000 - 0.6060 = +0.3940
                "robustness_rating": "ROBUST",
            },
            {
                "regime_id": "REG-08b",
                "regime_name": "8b. Tunnel Shift (Direct -> Tunneled)",
                "dataset_version": "2.0.0",
                "sample_count": "301",
                "train_count": "36",
                "test_count": "265",
                "accuracy": "0.3585",
                "macro_f1": "0.3407",
                "weighted_f1": "0.3411",
                "latency": "16.7935",
                "f1_delta_vs_baseline": "-0.2653",  # 0.3407 - 0.6060 = -0.2653
                "robustness_rating": "SEVERE_DEGRADATION",
            },
        ]

        def write_gen(rows: list) -> None:
            with open(gen_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_GENERALIZATION_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # 1. Valid table passes with asymmetric tunnel degradation verified
        write_gen(valid_rows)
        res_valid = validate_generalization_table(gen_csv)
        self.assertEqual(res_valid.status, ValidationStatus.PASS)
        self.assertIn("Asymmetric tunnel degradation verified", res_valid.reason)

        # 2. Missing baseline regime REG-01 -> FAIL
        no_baseline = [r for r in valid_rows if r["regime_id"] != "REG-01"]
        write_gen(no_baseline)
        res_no_base = validate_generalization_table(gen_csv)
        self.assertEqual(res_no_base.status, ValidationStatus.FAIL)
        self.assertIn("Missing required baseline regime", res_no_base.reason)

        # 3. Missing tunnel regimes -> FAIL
        no_tunnel = [r for r in valid_rows if r["regime_id"] == "REG-01"]
        write_gen(no_tunnel)
        res_no_tunnel = validate_generalization_table(gen_csv)
        self.assertEqual(res_no_tunnel.status, ValidationStatus.FAIL)
        self.assertIn("Missing required tunnel-regime rows", res_no_tunnel.reason)

        # 4. Incorrect F1 delta vs baseline -> FAIL
        wrong_delta = [dict(r) for r in valid_rows]
        wrong_delta[1]["f1_delta_vs_baseline"] = "0.9999"  # Claims +0.9999 when actual is +0.3940
        write_gen(wrong_delta)
        res_wrong_delta = validate_generalization_table(gen_csv)
        self.assertEqual(res_wrong_delta.status, ValidationStatus.FAIL)
        self.assertIn("F1 delta mismatch in regime 'REG-08a'", res_wrong_delta.reason)

        # 5. Invalid sample counts (train_count + test_count > sample_count) -> FAIL
        bad_counts = [dict(r) for r in valid_rows]
        bad_counts[0]["train_count"] = "250"
        bad_counts[0]["test_count"] = "100"  # 250 + 100 = 350 > 301
        write_gen(bad_counts)
        res_bad_cnt = validate_generalization_table(gen_csv)
        self.assertEqual(res_bad_cnt.status, ValidationStatus.FAIL)
        self.assertIn("Count inconsistency in regime 'REG-01'", res_bad_cnt.reason)

        # 6. Tunnel asymmetry contradicted (e.g. REG-08b improves or doesn't degrade) -> FAIL
        symmetric = [dict(r) for r in valid_rows]
        symmetric[2]["macro_f1"] = "0.9500"
        symmetric[2]["f1_delta_vs_baseline"] = str(round(0.9500 - 0.6060, 4))
        write_gen(symmetric)
        res_sym = validate_generalization_table(gen_csv)
        self.assertEqual(res_sym.status, ValidationStatus.FAIL)
        self.assertIn("Asymmetric tunnel degradation claim contradicted", res_sym.reason)

    # =========================================================================
    # 7. Evidence-Driven Latency Validation (Task 3B Hardening)
    # =========================================================================
    def test_latency_table_evidence_driven(self) -> None:
        """
        Validates decision-tree warm inference requirement, extractor requirement,
        non-negative finite percentiles, percentile monotonicity, and threshold checks.
        """
        lat_csv = self.tables_dir / "research_latency.csv"

        valid_lat_rows = [
            {
                "model": "N/A (Extractor)",
                "feature_profile": "profile_21_features",
                "feature_count": "21",
                "stage": "feature_extraction",
                "execution_phase": "warm",
                "p50_ms": "0.3681",
                "p95_ms": "7.0281",
            },
            {
                "model": "decision_tree",
                "feature_profile": "profile_21_features",
                "feature_count": "21",
                "stage": "inference",
                "execution_phase": "warm",
                "p50_ms": "0.0541",
                "p95_ms": "0.0713",
            },
        ]

        def write_lat(rows: list) -> None:
            with open(lat_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_LATENCY_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # 1. Valid rows pass with verified numbers
        write_lat(valid_lat_rows)
        res_valid = validate_latency_table(lat_csv)
        self.assertEqual(res_valid.status, ValidationStatus.PASS)
        self.assertAlmostEqual(res_valid.details["dt_warm_inference_p50_ms"], 0.0541)
        self.assertAlmostEqual(res_valid.details["ext_warm_extraction_p50_ms"], 0.3681)

        # 2. Missing decision tree warm inference row -> FAIL (no 0.0 substitution)
        no_dt = [valid_lat_rows[0]]
        write_lat(no_dt)
        res_no_dt = validate_latency_table(lat_csv)
        self.assertEqual(res_no_dt.status, ValidationStatus.FAIL)
        self.assertIn("decision tree warm inference row not found", res_no_dt.reason)

        # 3. Missing feature extractor row -> FAIL (no 0.0 substitution)
        no_ext = [valid_lat_rows[1]]
        write_lat(no_ext)
        res_no_ext = validate_latency_table(lat_csv)
        self.assertEqual(res_no_ext.status, ValidationStatus.FAIL)
        self.assertIn("feature extraction warm execution row not found", res_no_ext.reason)

        # 4. Percentile inversion: p95_ms < p50_ms -> FAIL
        inverted = [dict(r) for r in valid_lat_rows]
        inverted[1]["p50_ms"] = "0.5000"
        inverted[1]["p95_ms"] = "0.1000"  # p95 < p50
        write_lat(inverted)
        res_inv = validate_latency_table(lat_csv)
        self.assertEqual(res_inv.status, ValidationStatus.FAIL)
        self.assertIn("Percentile inversion", res_inv.reason)

        # 5. Decision tree latency violates sub-millisecond threshold (>= 1.0 ms) -> FAIL
        slow_dt = [dict(r) for r in valid_lat_rows]
        slow_dt[1]["p50_ms"] = "1.5000"
        slow_dt[1]["p95_ms"] = "2.0000"
        write_lat(slow_dt)
        res_slow = validate_latency_table(lat_csv)
        self.assertEqual(res_slow.status, ValidationStatus.FAIL)
        self.assertIn("fails real-time threshold", res_slow.reason)

    # =========================================================================
    # 8. Realtime Pipeline Invariants & Flow Accounting (Task 3B Hardening)
    # =========================================================================
    def test_realtime_pipeline_independent_invariant_failures(self) -> None:
        """
        Validates realtime pipeline: independent failure of each invariant,
        numeric counter validation, LIVE_MODE status, and DEMO_MODE segregation.
        """
        rt_csv = self.tables_dir / "realtime_research_validation.csv"

        def make_valid_rt_rows() -> list:
            return [
                {
                    "operating_mode": "DEMO_MODE",
                    "model_id": "lightgbm",
                    "test_phase": "demo_synthetic_replay",
                    "packets_observed": "68",
                    "flows_generated": "12",
                    "flows_classified": "44",
                    "dropped_flows": "0",
                    "processing_failures": "0",
                    "payload_persistence_check": "PASSED",
                    "zero_payload_features_check": "PASSED",
                    "tls_decryption_check": "PASSED",
                    "status": "VALIDATED",
                },
                {
                    "operating_mode": "LIVE_MODE",
                    "model_id": "lightgbm",
                    "test_phase": "controlled_live_traffic",
                    "packets_observed": "142",
                    "flows_generated": "15",
                    "flows_classified": "112",
                    "dropped_flows": "0",
                    "processing_failures": "0",
                    "payload_persistence_check": "PASSED",
                    "zero_payload_features_check": "PASSED",
                    "tls_decryption_check": "PASSED",
                    "status": "VALIDATED",
                },
            ]

        def write_rt(rows: list) -> None:
            with open(rt_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_REALTIME_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # Case A: Valid rows pass
        write_rt(make_valid_rt_rows())
        res_valid = validate_realtime_table(rt_csv)
        self.assertEqual(res_valid.status, ValidationStatus.PASS)
        self.assertIn("All security/privacy invariants verified", res_valid.reason)

        # Case B: Each of the 3 canonical invariants independently failing in LIVE_MODE
        for inv_key in ["payload_persistence_check", "zero_payload_features_check", "tls_decryption_check"]:
            broken = make_valid_rt_rows()
            broken[1][inv_key] = "FAILED"
            write_rt(broken)
            res = validate_realtime_table(rt_csv)
            self.assertEqual(res.status, ValidationStatus.FAIL, f"Failed to catch broken {inv_key}")
            self.assertIn(inv_key, res.reason)

        # Case C: LIVE_MODE status not 'VALIDATED' -> FAIL
        unval = make_valid_rt_rows()
        unval[1]["status"] = "UNVERIFIED"
        write_rt(unval)
        res_unval = validate_realtime_table(rt_csv)
        self.assertEqual(res_unval.status, ValidationStatus.FAIL)
        self.assertIn("expected 'VALIDATED'", res_unval.reason)

        # Case D: LIVE_MODE dropped flows or processing failures > 0 -> FAIL
        dropped = make_valid_rt_rows()
        dropped[1]["dropped_flows"] = "3"
        write_rt(dropped)
        res_drop = validate_realtime_table(rt_csv)
        self.assertEqual(res_drop.status, ValidationStatus.FAIL)
        self.assertIn("dropped flows", res_drop.reason)

        # Case E: Missing LIVE_MODE row -> FAIL
        no_live = [make_valid_rt_rows()[0]]
        write_rt(no_live)
        res_no_live = validate_realtime_table(rt_csv)
        self.assertEqual(res_no_live.status, ValidationStatus.FAIL)
        self.assertIn("Missing LIVE_MODE verification row", res_no_live.reason)

        # Case F: Missing DEMO_MODE row -> FAIL
        no_demo = [make_valid_rt_rows()[1]]
        write_rt(no_demo)
        res_no_demo = validate_realtime_table(rt_csv)
        self.assertEqual(res_no_demo.status, ValidationStatus.FAIL)
        self.assertIn("Missing DEMO_MODE verification row", res_no_demo.reason)

        # Case G: DEMO_MODE traffic not segregated (test_phase not indicating replay) -> FAIL
        unsegregated = make_valid_rt_rows()
        unsegregated[0]["test_phase"] = "live_production"
        write_rt(unsegregated)
        res_unseg = validate_realtime_table(rt_csv)
        self.assertEqual(res_unseg.status, ValidationStatus.FAIL)
        self.assertIn("not properly segregated", res_unseg.reason)

    # =========================================================================
    # 9. Selective Prediction Claims Verification (Task 3B Hardening)
    # =========================================================================
    def test_selective_prediction_verification(self) -> None:
        """
        Validates selective prediction: validation-split evidence requirement,
        threshold selection matching, denominator consistency, and monotonicity.
        """
        sel_csv = self.tables_dir / "research_selective_prediction.csv"

        valid_rows = [
            # Validation split (where tau*=0.70 was selected)
            {
                "split": "validation",
                "threshold": "0.0",
                "coverage": "1.0",
                "accepted_samples": "48",
                "total_samples": "48",
                "selective_accuracy": "0.5625",
                "error_rate_accepted": "0.4375",
                "selective_macro_f1": "0.5664",
                "is_selected_threshold": "NO",
            },
            {
                "split": "validation",
                "threshold": "0.7",
                "coverage": "0.5",
                "accepted_samples": "24",
                "total_samples": "48",
                "selective_accuracy": "0.75",
                "error_rate_accepted": "0.25",
                "selective_macro_f1": "0.7741",
                "is_selected_threshold": "YES",
            },
            # Test split (operating at selected tau*=0.70)
            {
                "split": "test",
                "threshold": "0.0",
                "coverage": "1.0",
                "accepted_samples": "48",
                "total_samples": "48",
                "selective_accuracy": "0.5417",
                "error_rate_accepted": "0.4583",
                "selective_macro_f1": "0.5474",
                "is_selected_threshold": "NO",
            },
            {
                "split": "test",
                "threshold": "0.7",
                "coverage": "0.5417",
                "accepted_samples": "26",
                "total_samples": "48",
                "selective_accuracy": "0.7308",
                "error_rate_accepted": "0.2692",
                "selective_macro_f1": "0.6515",
                "is_selected_threshold": "YES",
            },
            {
                "split": "test",
                "threshold": "0.9",
                "coverage": "0.2083",
                "accepted_samples": "10",
                "total_samples": "48",
                "selective_accuracy": "0.9",
                "error_rate_accepted": "0.1",
                "selective_macro_f1": "0.9",
                "is_selected_threshold": "NO",
            },
        ]

        def write_sel(rows: list) -> None:
            with open(sel_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REQUIRED_SELECTIVE_PREDICTION_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # 1. Valid selective prediction passes
        write_sel(valid_rows)
        res_valid = validate_selective_prediction_table(sel_csv)
        self.assertEqual(res_valid.status, ValidationStatus.PASS)
        self.assertAlmostEqual(res_valid.details["selected_threshold"], 0.7)

        # 2. Missing validation split rows -> UNVERIFIED (cannot verify threshold selection without validation data)
        no_val = [r for r in valid_rows if r["split"] != "validation"]
        write_sel(no_val)
        res_no_val = validate_selective_prediction_table(sel_csv)
        self.assertEqual(res_no_val.status, ValidationStatus.UNVERIFIED)
        self.assertIn("Validation split rows absent", res_no_val.reason)

        # 3. Contradictory threshold flags: test marks tau=0.9 selected, but validation chose tau=0.7 -> FAIL
        contradictory = [dict(r) for r in valid_rows]
        contradictory[3]["is_selected_threshold"] = "NO"
        contradictory[4]["is_selected_threshold"] = "YES"  # Test marks 0.9
        write_sel(contradictory)
        res_contra = validate_selective_prediction_table(sel_csv)
        self.assertEqual(res_contra.status, ValidationStatus.FAIL)
        self.assertIn("Contradictory threshold selection", res_contra.reason)

        # 4. Inconsistent denominator: coverage does not equal accepted_samples / total_samples -> FAIL
        bad_cov = [dict(r) for r in valid_rows]
        bad_cov[1]["coverage"] = "0.9000"  # 24 / 48 is 0.5000, not 0.9000
        write_sel(bad_cov)
        res_bad_cov = validate_selective_prediction_table(sel_csv)
        self.assertEqual(res_bad_cov.status, ValidationStatus.FAIL)
        self.assertIn("Coverage calculation mismatch", res_bad_cov.reason)

        # 5. Non-monotonic error rate reduction -> FAIL
        non_monotonic = [dict(r) for r in valid_rows]
        non_monotonic[4]["error_rate_accepted"] = "0.3500"  # 0.3500 > 0.2692 at tau=0.7
        non_monotonic[4]["selective_accuracy"] = "0.6500"
        write_sel(non_monotonic)
        res_non_mono = validate_selective_prediction_table(sel_csv)
        self.assertEqual(res_non_mono.status, ValidationStatus.FAIL)
        self.assertIn("Monotonic error reduction violated", res_non_mono.reason)

    # =========================================================================
    # 10. Numeric Parsing Hardening (Task 3B)
    # =========================================================================
    def test_numeric_parsing_hardening(self) -> None:
        """Verifies safe_float, safe_int, and safe_probability reject invalid/non-finite inputs."""
        # safe_float
        self.assertEqual(safe_float("0.5417", "f")[0], 0.5417)
        self.assertIsNone(safe_float("NaN", "f")[0])
        self.assertIn("Non-finite", safe_float("NaN", "f")[1])
        self.assertIsNone(safe_float("Infinity", "f")[0])
        self.assertIsNone(safe_float("-inf", "f")[0])
        self.assertIsNone(safe_float(math.nan, "f")[0])
        self.assertIsNone(safe_float(math.inf, "f")[0])
        self.assertIsNone(safe_float("bad_str", "f")[0])
        self.assertIsNone(safe_float("", "f")[0])
        self.assertIsNone(safe_float(None, "f")[0])

        # safe_int
        self.assertEqual(safe_int("205", "i")[0], 205)
        self.assertIsNone(safe_int("205.5", "i")[0])
        self.assertIn("Non-integer count", safe_int("205.5", "i")[1])
        self.assertIsNone(safe_int("-5", "i", allow_negative=False)[0])
        self.assertIsNone(safe_int("NaN", "i")[0])
        self.assertIsNone(safe_int("", "i")[0])

        # safe_probability
        self.assertEqual(safe_probability("0.85", "p")[0], 0.85)
        self.assertIsNone(safe_probability("1.05", "p")[0])
        self.assertIn("out of range", safe_probability("1.05", "p")[1])
        self.assertIsNone(safe_probability("-0.01", "p")[0])
        self.assertIsNone(safe_probability("NaN", "p")[0])

    # =========================================================================
    # 11. Early-Prediction Coverage and Classified-Flow Denominators
    # =========================================================================
    def test_early_prediction_coverage_and_denominators(self) -> None:
        """Validates coverage calculation, classified denominator, and selective accuracy distinction."""
        early_csv = self.tables_dir / "research_early_prediction.csv"

        def write_early_rows(rows: list) -> None:
            fieldnames = list(rows[0].keys())
            with open(early_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

        valid_row_3 = {
            "observation_point": "3 packets",
            "packet_horizon": "3",
            "is_full_flow": "False",
            "coverage": "0.9167",
            "accuracy": "0.6364",  # 7 / 11 = 0.6364
            "macro_f1": "0.6111",
            "median_latency_ms": "84.33",
            "median_observation_delay_ms": "64.04",
            "total_test_flows": "12",
            "flows_meeting_horizon": "12",
            "flows_classified": "11",
            "model": "random_forest",
        }
        valid_row_full = {
            "observation_point": "full flow",
            "packet_horizon": "full",
            "is_full_flow": "True",
            "coverage": "0.3333",
            "accuracy": "0.0",
            "macro_f1": "0.0",
            "median_latency_ms": "59666.52",
            "median_observation_delay_ms": "59650.29",
            "total_test_flows": "12",
            "flows_meeting_horizon": "12",
            "flows_classified": "4",
            "model": "random_forest",
        }

        # Case A: Valid rows pass
        write_early_rows([valid_row_3, valid_row_full])
        res = validate_early_prediction_table(early_csv)
        self.assertEqual(res.status, ValidationStatus.PASS)

        # Case B: Broken coverage formula
        broken_cov = dict(valid_row_3)
        broken_cov["coverage"] = "0.5000"
        write_early_rows([broken_cov, valid_row_full])
        res_cov = validate_early_prediction_table(early_csv)
        self.assertEqual(res_cov.status, ValidationStatus.FAIL)
        self.assertIn("Coverage calculation mismatch", res_cov.reason)

        # Case C: flows_classified > total_test_flows
        broken_denom = dict(valid_row_3)
        broken_denom["flows_classified"] = "15"
        write_early_rows([broken_denom, valid_row_full])
        res_denom = validate_early_prediction_table(early_csv)
        self.assertEqual(res_denom.status, ValidationStatus.FAIL)
        self.assertIn("Flow denominator violation", res_denom.reason)

        # Case D: Denominator inconsistency where coverage < 1.0 but flows_classified == total_test_flows
        broken_denom_inconsistent = dict(valid_row_3)
        broken_denom_inconsistent["flows_classified"] = "12"
        broken_denom_inconsistent["coverage"] = "0.9167"
        write_early_rows([broken_denom_inconsistent, valid_row_full])
        res_denom_inconsistent = validate_early_prediction_table(early_csv)
        self.assertEqual(res_denom_inconsistent.status, ValidationStatus.FAIL)
        self.assertIn("Denominator inconsistency", res_denom_inconsistent.reason)

        # Case E: Selective accuracy mistakenly asserted as equal to full-test accuracy when coverage < 1.0
        conflated = dict(valid_row_3)
        conflated["full_test_accuracy"] = conflated["accuracy"]
        write_early_rows([conflated, valid_row_full])
        res_confl = validate_early_prediction_table(early_csv)
        self.assertEqual(res_confl.status, ValidationStatus.FAIL)
        self.assertIn("Selective accuracy conflated with full-test accuracy", res_confl.reason)

        # Case F: Helper function verify_early_accuracy_denominators
        self.assertFalse(verify_early_accuracy_denominators(0.6364, 0.9167, 0.6364))
        self.assertTrue(verify_early_accuracy_denominators(0.6364, 0.9167, 0.6364 * 0.9167))

    # =========================================================================
    # 12. Nonzero Exit Status for Invalid Claims
    # =========================================================================
    def test_nonzero_exit_status_for_invalid_required_claims(self) -> None:
        """Asserts that main() exits with code 1 when required claims fail validation."""
        empty_dir = self.tables_dir / "empty_dir"
        empty_dir.mkdir(parents=True, exist_ok=True)

        exit_code = main(["--tables-dir", str(empty_dir)])
        self.assertEqual(exit_code, 1)

    # =========================================================================
    # 13. Explicit UNVERIFIED Status When Evidence Is Insufficient
    # =========================================================================
    def test_explicit_unverified_status_when_evidence_insufficient(self) -> None:
        """
        Asserts that claims with insufficient evidence produce an explicit UNVERIFIED status,
        and unverified claims never produce 'ALL CLAIMS VERIFIED'.
        """
        mock_ledger = self.tables_dir / "MOCK_CLAIMS_LEDGER.md"
        mock_ledger.write_text(
            """# Claims Ledger
## 2. Master Claims Table
| Claim | Source Artifact | Experiment ID | Dataset Version | Verified? | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0.5873 Real Baseline Test Macro-F1** | `results/tables/research_baseline.csv` | `EXP-R09` | `dataset_v2` | **VERIFIED (REAL)** | Evaluated on 301 flows. |
| **Unsubstantiated 0.99 Accuracy Claim** | `non_existent_file.csv` | `EXP-FAKE` | `dataset_fake` | **UNVERIFIED** | No physical evidence. |
""",
            encoding="utf-8",
        )

        results = validate_claims_ledger(mock_ledger, PROJECT_ROOT)
        self.assertEqual(len(results), 2)

        # 1. 0.5873 Real Baseline must be UNVERIFIED as pure real data due to hybrid provenance
        r09 = next(r for r in results if "EXP-R09" in r.claim_id)
        self.assertEqual(r09.status, ValidationStatus.UNVERIFIED)
        self.assertIn("HYBRID_PERTURBED", r09.reason)

        # 2. Fake claim with missing file must be UNVERIFIED
        rfake = next(r for r in results if "EXP-FAKE" in r.claim_id)
        self.assertEqual(rfake.status, ValidationStatus.UNVERIFIED)

        # 3. Report printing must never say ALL CLAIMS VERIFIED when UNVERIFIED claims are present
        validator = ResearchClaimValidator(
            tables_dir=PROJECT_ROOT / "results" / "tables",
            ledger_path=mock_ledger,
        )
        _, all_res = validator.validate_all()

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            validator.print_report(all_res)

        output = buf.getvalue()
        self.assertNotIn("ALL CLAIMS VERIFIED", output)
        self.assertIn("Unverified claims noted", output)
        self.assertIn("UNVERIFIED", output)

    # =========================================================================
    # 14. Empirical Table Auditing on Current Workspace
    # =========================================================================
    def test_current_repository_empirical_tables_audit(self) -> None:
        """
        Audits all canonical empirical tables in results/tables/.
        Asserts that:
        - early prediction, generalization, selective prediction, latency, realtime,
          dataset provenance, and stale synthetic guard PASS.
        - historical research_baseline.csv FAILS due to provenance contradiction
          (dataset_origin='REAL_DATA' contradicted by DatasetRegistry classification of
          dataset_v2 as HYBRID_PERTURBED).
        """
        tables_path = PROJECT_ROOT / "results" / "tables"

        # 1. Early Prediction table passes
        res_early = validate_early_prediction_table(tables_path / "research_early_prediction.csv")
        self.assertEqual(res_early.status, ValidationStatus.PASS, res_early.reason)

        # 2. Generalization scorecard passes (asymmetric tunnel degradation verified)
        res_gen = validate_generalization_table(tables_path / "research_generalization_scorecard.csv")
        self.assertEqual(res_gen.status, ValidationStatus.PASS, res_gen.reason)
        self.assertIn("Asymmetric tunnel degradation verified", res_gen.reason)

        # 3. Latency table passes (DT warm inference and extractor verified)
        res_lat = validate_latency_table(tables_path / "research_latency.csv")
        self.assertEqual(res_lat.status, ValidationStatus.PASS, res_lat.reason)

        # 4. Realtime pipeline passes (all invariants passed, DEMO_MODE segregated)
        res_rt = validate_realtime_table(tables_path / "realtime_research_validation.csv")
        self.assertEqual(res_rt.status, ValidationStatus.PASS, res_rt.reason)

        # 5. Selective prediction passes (validation split supports tau*=0.70)
        res_sel = validate_selective_prediction_table(tables_path / "research_selective_prediction.csv")
        self.assertEqual(res_sel.status, ValidationStatus.PASS, res_sel.reason)

        # 6. Dataset provenance passes
        res_prov = validate_dataset_provenance(PROJECT_ROOT)
        self.assertEqual(res_prov.status, ValidationStatus.PASS, res_prov.reason)

        # 7. Stale synthetic rejection passes
        res_stale = validate_stale_synthetic_rejection(tables_path)
        self.assertEqual(res_stale.status, ValidationStatus.PASS, res_stale.reason)

        # 8. Baseline table on historical results/tables/research_baseline.csv FAILS
        # because it asserts dataset_origin='REAL_DATA' on dataset_v2 (HYBRID_PERTURBED).
        # This confirms that false-positive validation of the provenance contradiction is eliminated.
        res_base = validate_baseline_table(tables_path / "research_baseline.csv", PROJECT_ROOT)
        self.assertEqual(res_base.status, ValidationStatus.FAIL)
        self.assertIn("Provenance contradiction", res_base.reason)


if __name__ == "__main__":
    unittest.main()
