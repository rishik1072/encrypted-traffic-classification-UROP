"""
Deterministic Unit and Regression Tests for Research Documentation and Claims Audit.

Verifies:
1. Known retired synthetic headline metrics (0.95 Macro-F1) are not presented as active real-data results.
2. Pure-real-data claims are not attached to hybrid datasets (dataset_v2 is identified as HYBRID_PERTURBED).
3. Contradictions between dataset provenance and documentation are eliminated.
4. Early-prediction metrics distinguish selective accuracy on classified flows, coverage, and full-test accuracy.
5. Selective-prediction metrics include explicit coverage context.
6. Real-time latency claims distinguish physical packet observation delay from CPU model inference.
7. Outdated claims that "all research claims are verified" are prevented when unverified claims exist.
8. Historical results are preserved and clearly labeled as historical/quarantined for audit trail integrity.
9. Deterministic fixture tests that demonstrate the auditor correctly flags synthetic conflations,
   pure-real mislabels, and selective accuracy without coverage.
"""

from __future__ import annotations

import re
from pathlib import Path
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def audit_text_for_unqualified_synthetic_headline(text: str) -> list[str]:
    """
    Audits a text document for unqualified assertions of retired synthetic headline metrics
    (e.g., 0.95 Macro-F1) presented as active real-data results.
    Permits mentions when explicitly marked as historical, synthetic, or quarantined.
    """
    violations = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if "0.95" in line or "95%" in line:
            # Check if this line asserts 0.95 as baseline Macro-F1 or accuracy
            is_headline_assertion = any(
                term in line.lower()
                for term in ["baseline", "macro-f1", "accuracy", "classification fidelity"]
            )
            is_quarantined = any(
                term in line.lower()
                for term in [
                    "synthetic",
                    "historical",
                    "quarantined",
                    "fixture",
                    "dataset_v1",
                    "exp-01",
                    "exp-r08",
                    "abstain",
                    "coverage: 0.0",
                    "0.0% coverage",
                    "caveat",
                    "prior",
                    "literature",
                    "disallowed",
                    "contradicted",
                    "stale",
                    "deceptive",
                    "retracted",
                ]
            )
            if is_headline_assertion and not is_quarantined:
                violations.append(f"Line {idx}: Unqualified 0.95 assertion: {line.strip()}")
    return violations


def audit_text_for_pure_real_claim_on_hybrid(text: str) -> list[str]:
    """
    Audits text to ensure dataset_v2 is never claimed to be 100% physical real traffic
    without disclosing its hybrid / perturbed nature.
    """
    violations = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        line_lower = line.lower()
        if "dataset_v2" in line_lower:
            # Check for claims of pure physical traffic
            claims_pure_real = any(
                phrase in line_lower
                for phrase in [
                    "exclusively physical",
                    "pure physical real-world",
                    "pure real data",
                    "100% physical",
                    "grounded strictly in real physical",
                    "across physical 802.11ax wi-fi, gigabit ethernet",
                ]
            )
            discloses_hybrid = any(
                phrase in line_lower
                for phrase in ["hybrid", "perturb", "semi-synthetic", "40.2%", "121 physical"]
            )
            if claims_pure_real and not discloses_hybrid:
                violations.append(f"Line {idx}: Pure real claim on hybrid dataset_v2: {line.strip()}")
    return violations


def audit_selective_accuracy_coverage(text: str) -> list[str]:
    """
    Audits selective prediction statements to ensure selective accuracy is accompanied
    by coverage context and not presented as full-test accuracy.
    """
    violations = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        line_lower = line.lower()
        if "selective accuracy" in line_lower or "73.08%" in line_lower:
            has_coverage = any(
                term in line_lower for term in ["coverage", "cov", "accepted", "abstain", "26 / 48", "26/48", "54.17%", "54.2%"]
            )
            if not has_coverage:
                violations.append(f"Line {idx}: Selective accuracy reported without coverage context: {line.strip()}")
    return violations


def audit_realtime_operational_claims(text: str) -> list[str]:
    """
    Ensures integration test passes are not overstated as universal production readiness.
    """
    violations = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        line_lower = line.lower()
        if "production readiness" in line_lower or "universal external validity" in line_lower:
            is_disallowed_context = any(
                term in line_lower for term in ["disallowed", "not claim", "does not imply", "limitation", "cannot be interpreted"]
            )
            if not is_disallowed_context:
                violations.append(f"Line {idx}: Overstated operational claim: {line.strip()}")
    return violations


class TestDocumentationClaimsAudit(unittest.TestCase):
    """Automated audit test suite for research documentation and scientific claims."""

    def setUp(self) -> None:
        self.readme_path = PROJECT_ROOT / "README.md"
        self.ledger_path = PROJECT_ROOT / "docs" / "research" / "CLAIMS_LEDGER.md"
        self.abstract_path = PROJECT_ROOT / "docs" / "paper" / "01_abstract.md"
        self.intro_path = PROJECT_ROOT / "docs" / "paper" / "02_introduction.md"
        self.rq_path = PROJECT_ROOT / "docs" / "paper" / "04_research_questions.md"
        self.dataset_path = PROJECT_ROOT / "docs" / "paper" / "05_dataset.md"
        self.results_path = PROJECT_ROOT / "docs" / "paper" / "10_results.md"
        self.discussion_path = PROJECT_ROOT / "docs" / "paper" / "11_discussion.md"
        self.limitations_path = PROJECT_ROOT / "docs" / "paper" / "12_limitations.md"
        self.conclusion_path = PROJECT_ROOT / "docs" / "paper" / "13_conclusion.md"
        self.reproducibility_path = PROJECT_ROOT / "docs" / "paper" / "14_reproducibility.md"
        self.final_results_path = PROJECT_ROOT / "results" / "final" / "FINAL_RESULTS.md"
        self.findings_path = PROJECT_ROOT / "docs" / "final_findings.md"
        self.presentation_path = PROJECT_ROOT / "docs" / "presentation" / "12_results.md"

    # 1. README Headline & Historical Distinction
    def test_readme_headline_distinguishes_authoritative_and_historical(self) -> None:
        """Verifies README.md presents empirical hybrid/physical baselines and quarantines synthetic 0.95."""
        content = self.readme_path.read_text(encoding="utf-8")
        
        # Authoritative empirical values must be present in README
        self.assertIn("0.5857", content)
        self.assertIn("0.0833", content)
        self.assertIn("dataset_v2", content)
        self.assertIn("HYBRID_PERTURBED", content)

        # 0.95 must not appear as an unqualified active real-data headline
        headline_violations = audit_text_for_unqualified_synthetic_headline(content)
        self.assertEqual(headline_violations, [], f"Unqualified synthetic headline found in README: {headline_violations}")

        # The historical section must explicitly label dataset_v1 as historical/quarantined
        self.assertIn("Historical Synthetic Fixture Measurements", content)
        self.assertIn("HISTORICAL / SYNTHETIC ONLY", content)

    # 2. Test count in README
    def test_readme_does_not_assert_stale_27_tests_count(self) -> None:
        """Verifies README.md does not claim the repository only has 27 tests."""
        content = self.readme_path.read_text(encoding="utf-8")
        self.assertNotIn("27 comprehensive unit & smoke tests", content)
        # Should state 100% passing
        self.assertIn("100% Passing", content)

    # 3. Paper Abstract Disclosures
    def test_paper_abstract_discloses_dataset_v2_provenance_and_baseline(self) -> None:
        """Verifies 01_abstract.md accurately discloses hybrid provenance and physical baseline."""
        content = self.abstract_path.read_text(encoding="utf-8")
        
        # Must disclose hybrid nature
        self.assertIn("hybrid benchmark", content.lower())
        self.assertIn("121 physical", content)
        self.assertIn("180 controlled statistical", content)

        # Must mention pure real baseline result
        self.assertIn("0.0833", content)
        self.assertIn("dataset_real_v1", content)

        # Must not claim pure real across Ethernet/Cellular
        pure_real_violations = audit_text_for_pure_real_claim_on_hybrid(content)
        self.assertEqual(pure_real_violations, [])

    # 4. Paper Chapters No Unqualified Pure Real Claims on Hybrid Dataset
    def test_paper_chapters_disclose_hybrid_nature_of_dataset_v2(self) -> None:
        """Verifies paper chapters do not claim dataset_v2 is 100% physical real traffic."""
        chapters = [
            self.intro_path,
            self.rq_path,
            self.dataset_path,
            self.results_path,
            self.discussion_path,
            self.limitations_path,
            self.conclusion_path,
            self.reproducibility_path,
        ]
        for ch_path in chapters:
            if ch_path.exists():
                text = ch_path.read_text(encoding="utf-8")
                violations = audit_text_for_pure_real_claim_on_hybrid(text)
                self.assertEqual(violations, [], f"Found pure real claim on hybrid data in {ch_path.name}: {violations}")

    # 5. Early Prediction Denominators and Latency Decomposition
    def test_early_prediction_documentation_distinguishes_denominators(self) -> None:
        """Verifies CLAIMS_LEDGER.md and results chapters distinguish selective vs full-test accuracy and delay."""
        ledger = self.ledger_path.read_text(encoding="utf-8")
        
        # Check Claim 37 in ledger
        self.assertIn("63.64% Selective Accuracy", ledger)
        self.assertIn("91.67%", ledger)
        self.assertIn("58.33% full-test accuracy", ledger)
        self.assertIn("64.04 ms", ledger)
        self.assertIn("observation delay", ledger.lower())

    # 6. Selective Prediction Coverage Context
    def test_selective_prediction_documentation_includes_coverage_context(self) -> None:
        """Verifies CLAIMS_LEDGER.md reports selective accuracy alongside coverage and full-test accuracy."""
        ledger = self.ledger_path.read_text(encoding="utf-8")
        
        # Check Claim 38 in ledger
        self.assertIn("73.08% Selective Accuracy", ledger)
        self.assertIn("54.17%", ledger)
        self.assertIn("26.92% Error Rate", ledger)
        self.assertIn("39.58% full-test accuracy", ledger)

        # Check for selective accuracy statements lacking coverage
        violations = audit_selective_accuracy_coverage(ledger)
        self.assertEqual(violations, [])

    # 7. Presentation Slides Disclose Historical Metrics
    def test_presentation_slides_disclose_historical_synthetic_metrics(self) -> None:
        """Verifies docs/presentation/12_results.md distinguishes current empirical from synthetic metrics."""
        content = self.presentation_path.read_text(encoding="utf-8")
        self.assertIn("0.5873", content)
        self.assertIn("0.5802", content)
        self.assertIn("0.0833", content)
        self.assertIn("Historical Synthetic Fixtures", content)
        self.assertIn("Quarantined", content)

    # 8. Historical Final Findings Document Contains Audit Banner
    def test_final_findings_contains_audit_banner(self) -> None:
        """Verifies docs/final_findings.md has an audit notice identifying it as historical synthetic data."""
        content = self.findings_path.read_text(encoding="utf-8")
        self.assertIn("Historical Synthetic Findings Notice", content)
        self.assertIn("dataset_v1", content)
        self.assertIn("superseded", content.lower())

    # 9. No Unqualified "ALL CLAIMS VERIFIED" When Unverified Claims Exist
    def test_no_unqualified_all_claims_verified_when_unverified_claims_exist(self) -> None:
        """Verifies CLAIMS_LEDGER.md explicitly documents unverified claims (e.g. pure real baseline on dataset_v2)."""
        content = self.ledger_path.read_text(encoding="utf-8")
        self.assertIn("UNVERIFIED (PURE REAL)", content)
        self.assertNotIn("ALL CLAIMS VERIFIED", content)

    # 10. Fixture Test: Auditor catches unqualified synthetic headline
    def test_fixture_detector_catches_unqualified_synthetic_headline(self) -> None:
        """Verifies auditor flags synthetic 0.95 presented as real without quarantine."""
        bad_text = (
            "# Benchmark Report\n"
            "Our model achieves a Baseline Macro-F1 of 0.9500 on real encrypted traffic.\n"
        )
        violations = audit_text_for_unqualified_synthetic_headline(bad_text)
        self.assertEqual(len(violations), 1)
        self.assertIn("0.95 assertion", violations[0])

        good_text = (
            "# Benchmark Report\n"
            "LightGBM achieved 0.9500 Macro-F1 on an initial 12-flow synthetic fixture (dataset_v1).\n"
        )
        self.assertEqual(audit_text_for_unqualified_synthetic_headline(good_text), [])

    # 11. Fixture Test: Auditor catches pure-real claim on hybrid dataset
    def test_fixture_detector_catches_pure_real_claim_on_hybrid(self) -> None:
        """Verifies auditor flags claims that dataset_v2 is exclusively physical traffic."""
        bad_text = (
            "We evaluated our system on dataset_v2, which is an exclusively physical real-world capture.\n"
        )
        violations = audit_text_for_pure_real_claim_on_hybrid(bad_text)
        self.assertEqual(len(violations), 1)
        self.assertIn("Pure real claim on hybrid dataset_v2", violations[0])

        good_text = (
            "We evaluated our system on dataset_v2, a hybrid benchmark of 121 physical flows and 180 perturbations.\n"
        )
        self.assertEqual(audit_text_for_pure_real_claim_on_hybrid(good_text), [])

    # 12. Fixture Test: Auditor catches selective accuracy without coverage context
    def test_fixture_detector_catches_selective_accuracy_without_coverage(self) -> None:
        """Verifies auditor flags selective accuracy claims when coverage is omitted."""
        bad_text = "The classifier achieved 73.08% Selective Accuracy on test data.\n"
        violations = audit_selective_accuracy_coverage(bad_text)
        self.assertEqual(len(violations), 1)
        self.assertIn("coverage context", violations[0])

        good_text = "The classifier achieved 73.08% Selective Accuracy at 54.17% coverage (26 / 48 flows accepted).\n"
        self.assertEqual(audit_selective_accuracy_coverage(good_text), [])


if __name__ == "__main__":
    unittest.main()
