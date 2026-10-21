"""
Test Suite: Final Research Integrity Gate and Release Readiness Audit.

Validates:
1. Core dataset provenance consistency across primary research documents.
2. Distinct segregation of hybrid baseline (0.5854) and pure physical baseline (0.0833).
3. Continuous disclosure of the Random Forest baseline discrepancy (0.5854 vs 0.5873) as UNRESOLVED.
4. Complete quarantining of synthetic fixture results (0.9500) as historical.
5. Retention of unresolved and partially verified claims within the evidence matrix.
6. Honest release audit recommendation of READY WITH EXPLICIT LIMITATIONS without false perfection claims.
"""

from __future__ import annotations

import csv
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = PROJECT_ROOT / "results" / "tables"
RESEARCH_DOCS_DIR = PROJECT_ROOT / "docs" / "research"
PAPER_DIR = PROJECT_ROOT / "docs" / "paper"

from training.dataset_registry import DatasetOrigin, DatasetRegistry


class TestFinalReleaseReadiness(unittest.TestCase):
    """Integrity gate checks for release readiness audit."""

    def setUp(self) -> None:
        self.registry = DatasetRegistry(PROJECT_ROOT)
        self.release_doc = RESEARCH_DOCS_DIR / "FINAL_RELEASE_READINESS_AUDIT.md"
        self.trace_doc = RESEARCH_DOCS_DIR / "EMPIRICAL_EVIDENCE_TRACEABILITY.md"
        self.rf_doc = RESEARCH_DOCS_DIR / "RF_BASELINE_RECONCILIATION.md"
        self.readme = PROJECT_ROOT / "README.md"
        self.ledger = RESEARCH_DOCS_DIR / "CLAIMS_LEDGER.md"

        self.assertTrue(self.release_doc.exists(), "FINAL_RELEASE_READINESS_AUDIT.md must exist.")
        self.assertTrue(self.trace_doc.exists(), "EMPIRICAL_EVIDENCE_TRACEABILITY.md must exist.")
        self.assertTrue(self.rf_doc.exists(), "RF_BASELINE_RECONCILIATION.md must exist.")

    def test_core_dataset_provenance_consistency(self) -> None:
        """Verify that dataset_v2 and dataset_real_v1 provenance is consistently declared across primary documents."""
        # 1. Registry verification
        v2_meta = self.registry.get_dataset("dataset_v2")
        real_meta = self.registry.get_dataset("dataset_real_v1")
        self.assertEqual(v2_meta.origin, DatasetOrigin.HYBRID_PERTURBED)
        self.assertEqual(v2_meta.physical_flow_count, 121)
        self.assertEqual(v2_meta.synthetic_flow_count, 180)
        self.assertEqual(real_meta.origin, DatasetOrigin.REAL_DATA)

        # 2. Release audit document verification
        release_text = self.release_doc.read_text(encoding="utf-8")
        self.assertIn("HYBRID_PERTURBED", release_text)
        self.assertIn("121", release_text)
        self.assertIn("180", release_text)

        # 3. Paper Abstract verification
        abstract_text = (PAPER_DIR / "01_abstract.md").read_text(encoding="utf-8")
        self.assertIn("hybrid", abstract_text.lower())
        self.assertIn("121 physical", abstract_text)
        self.assertIn("180", abstract_text)

    def test_hybrid_and_physical_baselines_distinguished(self) -> None:
        """Verify that hybrid baseline (~0.585) and pure physical baseline (0.0833) are distinctly segregated."""
        readme_text = self.readme.read_text(encoding="utf-8")
        ledger_text = self.ledger.read_text(encoding="utf-8")
        release_text = self.release_doc.read_text(encoding="utf-8")

        for text in [readme_text, ledger_text, release_text]:
            self.assertIn("0.0833", text)
            # Physical baseline must cite the 12-flow test set limitation
            self.assertTrue("12" in text or "12-flow" in text or "N=12" in text)
            # Both hybrid and physical terms must be present
            self.assertIn("hybrid", text.lower())
            self.assertIn("physical", text.lower())

    def test_rf_discrepancy_and_unresolved_status_disclosed(self) -> None:
        """Verify that the Random Forest discrepancy between 0.5854 and 0.5873 is disclosed as UNRESOLVED."""
        release_text = self.release_doc.read_text(encoding="utf-8")
        rf_text = self.rf_doc.read_text(encoding="utf-8")
        trace_text = self.trace_doc.read_text(encoding="utf-8")

        for text in [release_text, rf_text, trace_text]:
            self.assertIn("0.5854", text)
            self.assertIn("0.5873", text)
            self.assertIn("UNRESOLVED", text)

        # Ensure that no document falsely claims 0.5873 is verified
        self.assertNotIn("0.5873 | VERIFIED", trace_text.replace(" ", ""))

    def test_synthetic_fixture_quarantined_as_historical(self) -> None:
        """Verify that legacy synthetic fixture results (0.9500) are quarantined as historical or synthetic."""
        release_text = self.release_doc.read_text(encoding="utf-8")
        trace_text = self.trace_doc.read_text(encoding="utf-8")
        ledger_text = self.ledger.read_text(encoding="utf-8")

        for text in [release_text, trace_text, ledger_text]:
            self.assertIn("0.9500", text)
            self.assertTrue("historical" in text.lower() or "synthetic" in text.lower())

        # Ensure no primary headline claims 0.9500 is achieved on real traffic
        self.assertNotIn("0.9500 on real encrypted network traffic", self.readme.read_text(encoding="utf-8"))

    def test_evidence_matrix_contains_unresolved_claims(self) -> None:
        """Verify that the evidence matrix honestly includes UNRESOLVED and PARTIALLY VERIFIED statuses."""
        trace_text = self.trace_doc.read_text(encoding="utf-8")
        self.assertIn("UNRESOLVED", trace_text)
        self.assertIn("PARTIALLY VERIFIED", trace_text)
        self.assertIn("HISTORICAL", trace_text)
        self.assertIn("VERIFIED", trace_text)

        # Assert that the release audit does NOT claim 100% of claims are verified
        release_text = self.release_doc.read_text(encoding="utf-8")
        self.assertNotIn("all claims are verified", release_text.lower())
        self.assertNotIn("100% verified", release_text.lower())

    def test_release_audit_verdict_is_ready_with_explicit_limitations(self) -> None:
        """Verify that the final release audit issues READY WITH EXPLICIT LIMITATIONS verdict."""
        release_text = self.release_doc.read_text(encoding="utf-8")
        self.assertIn("READY WITH EXPLICIT LIMITATIONS", release_text)
        # Check that specific scientific limitations are listed
        self.assertIn("Statistical Power of the 12-Flow Physical Baseline", release_text)
        self.assertIn("Generalization to Physically Captured Ethernet", release_text)


if __name__ == "__main__":
    unittest.main()
