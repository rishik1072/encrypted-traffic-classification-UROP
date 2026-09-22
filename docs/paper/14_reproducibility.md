# Chapter 14: Artifact Availability & Reproducibility Guide

## 14.1 Open-Science Reproducibility Philosophy

In accordance with modern empirical research standards, this study is fully reproducible. All experimental pipelines, preprocessed flow datasets, feature registries, trained model weights, evaluation tables, and publication figures are packaged within the repository. Every numerical claim in this manuscript can be re-generated from scratch using deterministic scripts with fixed pseudo-random seeds.

---

## 14.2 The Unified Research Command

The entire scientific evaluation pipeline is orchestrated via a single entry point:

```powershell
python scripts/reproduce_research.py --all
```

### Execution Lifecycle:
The orchestrator executes 15 sequential stages in strict dependency order:
1. **Environment Verification:** Validates Python version (3.10+), OS architecture, core dependencies (`numpy`, `pandas`, `scikit-learn`, `lightgbm`, `scipy`, `scapy`, `psutil`), and filesystem write permissions.
2. **Dataset Verification:** Asserts the cryptographic integrity (SHA-256) and `REAL_DATA` origin tag of `dataset_v2`. Rejects missing or modified files.
3. **Dataset Quality Audit:** Verifies class balance (6 classes), minimum packet counts, and missing-value policies, generating `results/tables/research_dataset_inventory.csv`.
4. **Leakage Audit:** Scans train/validation/test partitions to prove zero overlap of session identifiers and verify the complete excision of Layer-3/4 addressing shortcuts.
5. **Baseline Benchmark (EXP-R09):** Evaluates all 4 candidate models under group-aware session splitting, generating `results/tables/research_baseline.csv`.
6. **Feature Ablation (EXP-R10):** Evaluates individual feature families, generating `results/tables/feature_family_ablation_research.csv`.
7. **Feature Reduction (EXP-R10):** Evaluates feature counts $K \in \{3, 5, 10, 15, 20, 30, 84\}$, generating `results/tables/feature_count_tradeoff_research.csv`.
8. **Model Comparison:** Cross-evaluates baseline estimators on multi-objective accuracy-cost trade-offs.
9. **Generalization Benchmark (EXP-R11):** Evaluates all 8 distribution shifts, generating `results/tables/research_generalization_scorecard.csv`.
10. **Early Prediction Study (EXP-R12):** Evaluates observation prefixes (3 to 50 packets and full flow), generating `results/tables/research_early_prediction.csv`.
11. **Selective Classification & Calibration (EXP-R13):** Sweeps rejection thresholds and computes ECE/Brier scores, generating `results/tables/research_selective_prediction.csv` and `research_calibration.csv`.
12. **Latency & Resource Benchmark (EXP-R14):** Profiles cold start, warm inference, CPU time, and memory working set, generating `results/tables/research_latency.csv` and `research_resource_usage.csv`.
13. **Result Aggregation:** Validates all generated tables in `results/tables/` and compiles standardized outputs in `results/final/`.
14. **Figure Generation:** Renders and saves all 22 publication figures in `results/figures/`.
15. **Research Manifest Generation:** Generates the cryptographic provenance file `results/research_manifest.json`.

---

## 14.3 Granular CLI Execution Options

For targeted auditing, individual stages can be executed independently while automatically resolving prerequisite dependencies:

| Command | Target Scope | Executed Stages |
| :--- | :--- | :--- |
| `python scripts/reproduce_research.py --all` | Full Pipeline | Stages 1 through 15 |
| `python scripts/reproduce_research.py --dataset` | Dataset & Hygiene Audit | Stages 1–4, 13–15 |
| `python scripts/reproduce_research.py --baseline` | Baseline Models | Stages 1–2, 5, 8, 13–15 |
| `python scripts/reproduce_research.py --features` | Feature Ablation & Reduction | Stages 1–2, 6, 7, 13–15 |
| `python scripts/reproduce_research.py --generalization` | Domain Shifts & Tunnels | Stages 1–2, 9, 13–15 |
| `python scripts/reproduce_research.py --early` | Early-Stage Horizons | Stages 1–2, 10, 13–15 |
| `python scripts/reproduce_research.py --selective` | Confidence & Calibration | Stages 1–2, 11, 13–15 |
| `python scripts/reproduce_research.py --latency` | Computational Efficiency | Stages 1–2, 12, 13–15 |
| `python scripts/reproduce_research.py --skip-figures` | Fast Table-Only Run | Skips figure re-rendering |

---

## 14.4 Cryptographic Manifest Schema (`results/research_manifest.json`)

Every execution of the reproduction script automatically writes `results/research_manifest.json`, providing a tamper-evident audit record:

```json
{
  "manifest_version": "1.0.0",
  "generated_at": "2026-09-22T09:08:32Z",
  "codebase_version": "0dea637199",
  "environment": {
    "os": "Windows-11-10.0.26200-SP0",
    "python_version": "3.14.7",
    "processor": "Intel64 Family 6 Model 154 Stepping 3, GenuineIntel",
    "machine": "Rouge017"
  },
  "dataset": {
    "dataset_id": "dataset_v2",
    "version": "2.0.0",
    "origin": "REAL_DATA",
    "flow_count": 301,
    "session_count": 150,
    "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
    "checksum_sha256": "cd3193ecdd2ecb4859ba6b23bb75153571e205930f05fa2dc7323fcfc1a2c16d"
  },
  "feature_profile": "lightweight_10",
  "split_strategy": "group_aware_session_split",
  "random_seed": 42,
  "model_versions": {
    "lightgbm": "1.0.0",
    "random_forest": "1.0.0",
    "decision_tree": "1.0.0",
    "logistic_regression": "1.0.0"
  },
  "artifact_paths": {
    "tables": { ... },
    "figures": [ ... ]
  }
}
```

---

## 14.5 Step-by-Step Instructions for Third-Party Auditors

### Prerequisites:
- Windows 10/11 x64 (or Linux/macOS for offline evaluation scripts).
- Python 3.10+ (tested on Python 3.14.7).

### Reproduction Steps:
1. Clone the repository and navigate to the project root:
   ```bash
   cd encrypted-traffic-classification-UROP
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the automated test suite:
   ```bash
   pytest tests/test_product_*.py tests/test_dashboard_*.py tests/test_reproduce_research.py -v
   ```
4. Execute the complete reproduction orchestrator:
   ```bash
   python scripts/reproduce_research.py --all
   ```
5. Inspect the generated tables in `results/final/` and `results/tables/`. All metrics will match the tables presented in Chapter 10 bit-for-bit.
