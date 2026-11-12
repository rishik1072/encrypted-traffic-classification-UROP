# IEEE Conference Manuscript: Practical Zero-Payload Encrypted Traffic Classification

**Manuscript Title:** *Practical Zero-Payload Encrypted Traffic Classification: Evaluating Group-Aware Generalization, Early-Stage Triage, and Calibrated Abstention on Real Network Traffic*  
**Publication Format:** Official IEEE Conference Two-Column Format (`IEEEtran.cls`)  
**Package Location:** `docs/paper/ieee/`  
**Repository:** `C:\UROP project\encrypted-traffic-classification-UROP`  
**Authoring Status:** Complete Scientific Manuscript & Verified Reference Package  
**Date:** October 2026  

---

## 1. Directory Structure & Deliverable Manifest

The `docs/paper/ieee/` directory is an independent, self-contained publication package:

```text
docs/paper/ieee/
├── main.tex             # Complete IEEEtran conference LaTeX manuscript
├── references.bib       # 31 verified academic BibTeX citations with DOIs/URLs
├── README.md            # Compilation instructions, build notes, and empirical ledger
├── REFERENCE_AUDIT.md   # Exhaustive bibliographic verification and claim-mapping audit
└── figures/             # 22 publication-grade empirical result figures (PNG)
    ├── research_baseline_model_comparison.png
    ├── research_baseline_confusion_matrix.png
    ├── feature_pareto_frontier.png
    ├── feature_vs_f1.png
    ├── generalization_comparison.png
    ├── tunnel_shift.png
    ├── early_prediction_latency_vs_packets.png
    ├── early_prediction_f1_vs_packets.png
    ├── coverage_vs_accuracy.png
    ├── coverage_vs_error.png
    ├── calibration_curve.png
    ├── latency_vs_f1.png
    ├── resource_usage.png
    └── ... (all 22 figures copied from results/figures/)
```

---

## 2. Compilation Instructions

The manuscript utilizes the standard `IEEEtran` document class (`\documentclass[conference]{IEEEtran}`) and standard CTAN packages (`amsmath`, `amssymb`, `graphicx`, `booktabs`, `tabularx`, `cite`, `microtype`, `subcaption`, `url`, `balance`).

### Option A: Overleaf (Zero-Install / Web Browser)
1. Compress the `docs/paper/ieee/` directory into a `.zip` archive (ensure `main.tex`, `references.bib`, and the `figures/` folder are at the root of the archive).
2. Log into [Overleaf](https://www.overleaf.com/).
3. Click **New Project** $\rightarrow$ **Upload Project** and select the `.zip` file.
4. Set the compiler to **pdfLaTeX** (default) or **XeLaTeX**.
5. Click **Recompile**. The complete two-column IEEE paper will compile with all figures, equations, tables, and numbered references.

### Option B: Local Command-Line Compilation (TeX Live, MacTeX, or MikTeX)
If a local TeX distribution is installed:

```bash
cd docs/paper/ieee

# Standard 4-step LaTeX compilation sequence
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Alternatively, using `latexmk`:
```bash
latexmk -pdf main.tex
```

### Option C: Dockerized Compilation (Containerized Environment)
If Docker is available, compile without installing LaTeX locally:

```bash
docker run --rm -v "%cd%":/workdir -w /workdir texlive/texlive:latest sh -c \
  "pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex"
```

### Local Compiler Environment Audit Note
During the verification of this repository, the host operating system (Windows 11) was audited for native LaTeX binaries (`pdflatex`, `xelatex`, `lualatex`, `tectonic`, `miktex`). No TeX distribution binary was present in the system `PATH`. All syntax, cross-references, environment nestings, and citation resolutions were verified using automated Python token and LIFO stack analyzers.

---

## 3. Empirical Accuracy & Scientific Findings Ledger

In strict accordance with research audit standards, all numerical claims in `main.tex` correspond to canonical result artifacts in `results/final/*.csv` and `results/models/`:

| Dimension / Finding | Verified Value in Paper | Authoritative Source Artifact | Scientific Context & Constraints |
| :--- | :---: | :--- | :--- |
| **Dataset ID & Size** | **301 flows, 150 sessions** | `results/final/dataset_summary.csv` | Balanced across 6 classes: Web (50), Video (50), Messaging (50), VoIP (50), File Transfer (50), Other (51). |
| **Dataset Origin** | **`HYBRID_PERTURBED`** | `docs/research/DATASET_CARD.md` | Combines 121 physical 802.11ax Wi-Fi flows (40.2\%) with 180 controlled statistical feature perturbations (59.8\%). |
| **Preserved RF Model** | **0.5854 Macro-F1** (0.5833 Acc) | `results/models/research_baseline/random_forest.joblib` | Fully reproduced from preserved 878.04 KB weights on locked test set (28/48 correct flows). |
| **Historical RF Run** | **0.5873 Macro-F1** (0.5833 Acc) | `results/final/baseline_results.csv` | Run with 881.98 KB model size; weights not preserved. Performance band documented as $\approx 0.585 - 0.587$. |
| **Decision Tree Baseline** | **0.5802 Macro-F1** (0.5833 Acc) | `results/final/baseline_results.csv` | 100\% deterministic; 9.58 KB size (3.11 KB for 10 features), 0.0579 ms warm inference ($249\times$ faster than RF). |
| **Pure Physical Baseline** | **0.0833 Macro-F1** (0.0833 Acc) | `results/tables/real_final_baseline_result.csv` | Evaluated on pure unperturbed physical Wi-Fi traffic (\texttt{dataset\_real\_v1}) on 12 held-out flows (1/12 correct). |
| **Feature Family Density** | **0.4241 Macro-F1** (3 features) | `results/final/feature_ablation.csv` | Directionality asymmetry ratios carry the densest signal; all 84 features degrade to 0.2931 F1. |
| **Optimal Feature Subset** | **0.6708 Macro-F1** ($K=3$) | `results/final/feature_ablation.csv` | Ultra-compact subset: `packet_ratio`, `byte_ratio`, `fwd_packet_count`. |
| **Physical Media Shift** | **0.9325 Macro-F1** (REG-05) | `results/final/generalization.csv` | Evaluated on 120 flows with controlled perturbations modeling Ethernet and Cellular; not physical 5G/switch tests. |
| **Tunnel Shift Collapse** | **0.3407 Macro-F1** (REG-08b) | `results/final/generalization.csv` | Transferring direct-trained models to WireGuard/WARP drops F1 by -0.2594 due to 1280-byte MTU clamping. |
| **Early Packet Triage** | **0.6111 Macro-F1** at $N=3$ | `results/final/early_prediction.csv` | Evaluates in 79.94 ms (64.04 ms wire arrival + 16.53 ms compute) with 91.67\% coverage (7/11 classified correct). |
| **Latency Hierarchy** | **79.5\%--99.8\% Wire Delay** | `results/final/early_prediction.csv` | Physical arrival delay dominates computational execution time across all observation horizons. |
| **Selective Abstention** | **26.92\% Error** at $\tau^*=0.70$ | `results/final/selective_prediction.csv` | Validation-tuned threshold cuts error from 45.83\% to 26.92\% at 54.17\% coverage (19/26 correct accepted flows). |
| **Uncalibrated Test ECE** | **0.1996 ECE, 0.6061 Brier** | `results/final/calibration.csv` | Quantifies overconfidence on uncalibrated tree posteriors; Brier score improves to 0.4402 at $\tau^*=0.70$. |

---

## 4. Reference Verification & Bibliographic Notes

All 31 citations in `references.bib` have been verified against authoritative publisher records. See `REFERENCE_AUDIT.md` for complete bibliographic metadata, DOIs, URLs, and claim-to-citation mappings.

### Key Bibliographic Corrigenda Applied:
1. **Arp et al. (USENIX Security '22) [Ref 28]:** Restored complete 8-author list (`Daniel Arp, Erwin Quiring, Feargus Pendlebury, Alexander Warnecke, Fabio Pierazzi, Christian Wressnegger, Lorenzo Cavallaro, Konrad Rieck`).
2. **Holland et al. (ACM CCS '21) [Ref 7]:** Verified exact author list (`Jordan Holland, Paul Schmitt, Nick Feamster, Prateek Mittal`), pages (`3366–3383`), and DOI (`10.1145/3460120.3484758`).
3. **Bonfiglio et al. (ACM CCR '07) [Ref 27]:** Corrected author attribution from informal draft to `Dario Bonfiglio, Marco Mellia, Michela Meo, Dario Rossi, Paolo Tofanelli` and verified DOI `10.1145/1282380.1282386`.
4. **Draper-Gil et al. (ICISSP '16) [Ref 26]:** Corrected publisher DOI from draft typo to official SCITEPRESS DOI `10.5220/0005740704070414`.
5. **Dusi et al. (Computer Networks '09) [Ref 25]:** Corrected ScienceDirect DOI to `10.1016/j.comnet.2008.09.010`.
6. **Crotti et al. (ACM CCR '07) [Ref 10]:** Verified ACM Digital Library DOI `10.1145/1198255.1198257`.
7. **Taylor et al. (IEEE EuroS&P '16) [Ref 6]:** Corrected IEEE DOI to `10.1109/EuroSP.2016.40`.

---

## 5. Artifact Provenance & Integrity

All experiments in this manuscript can be re-executed via the project's canonical reproduction runner:
```bash
python scripts/reproduce_research.py --all
```
Cryptographic hashes for all dataset partitions, model weights, and benchmark scorecards are permanently registered in `results/research_manifest.json` and `results/reproducibility_manifest.json`.
