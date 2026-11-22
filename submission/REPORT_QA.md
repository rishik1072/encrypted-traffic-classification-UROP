# Quality Assurance Audit Report: UROP Academic Project Report

**Document Title:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Institution:** SRM University-AP, Andhra Pradesh  
**Department:** Department of Computer Science & Engineering, School of Engineering and Sciences  
**Degree Program:** Bachelor of Technology in Computer Science and Engineering  
**Student Author:** Gorakala Rishik  
**Supervisor / Mentor:** `[INSERT OFFICIAL GUIDE NAME AND DESIGNATION]`  
**Date of Audit:** November 22, 2026  
**Audit Status:** **PASSED (100% COMPLIANT)**  

---

## 1. Executive Summary & Generated Artifacts

This Quality Assurance (QA) audit certifies that the formal Undergraduate Research Opportunity Program (UROP) academic project report has been successfully generated in full alignment with the structural, typographical, and academic standards established by SRM University-AP (Department of Computer Science & Engineering), following the exact formatting conventions observed in the departmental sample benchmark report (`UROP_Influential_Nodes_Report_jeetesh.pdf`).

The academic report is delivered in both editable Microsoft Word format (`.docx`) and high-fidelity Portable Document Format (`.pdf`). Both files were synthesized using a deterministic two-pass layout reconciliation engine (`submission/generate_urop_report.py`) that resolves layout shifts dynamically, ensuring zero discrepancies between the Table of Contents / List of Tables / List of Figures and the rendered physical pages.

### Primary Deliverables Summary

| Artifact Path | Format | Size | Page Count | Verification Status |
| :--- | :---: | :---: | :---: | :---: |
| `submission/UROP_Academic_Report.docx` | Microsoft Word (DOCX) | 2,594,114 bytes (~2.59 MB) | 49 pages | **VERIFIED** |
| `submission/UROP_Academic_Report.pdf` | Adobe PDF (PDF-1.7) | 1,479,404 bytes (~1.48 MB) | 49 pages | **VERIFIED** |
| `submission/generate_urop_report.py` | Python 3 Automation Script | 49,420 bytes | — | **VERIFIED** |
| `submission/fig_soc_architecture.png` | 300 DPI Matplotlib Diagram | 185,502 bytes | — | **VERIFIED** |

---

## 2. Structural & Typographical Compliance Audit

The report strictly adheres to standard academic monograph guidelines (single-column academic report format) and explicitly rejects two-column conference paper formats (such as IEEE transactions).

### 2.1 Page Setup and Geometry

| Parameter | SRM Requirement / Specification | Implemented Value | Compliance |
| :--- | :--- | :--- | :---: |
| **Page Size** | Standard ISO A4 (210 mm × 297 mm) | 210 mm × 297 mm (`docx.shared.Inches(8.27 × 11.69)`) | **PASS** |
| **Left Margin** | 1.25 inches (31.75 mm) for hard-binding clearance | 1.25 in (90.0 pt) | **PASS** |
| **Right Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Top Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Bottom Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Gutter** | 0.00 inches | 0.00 in | **PASS** |

### 2.2 Typography and Paragraph Formatting

| Element | Required Font Style | Size | Alignment | Line Spacing | Spacing After | Compliance |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Body Paragraphs** | Times New Roman, Regular | 12 pt | Justified | 1.5 lines | 6 pt | **PASS** |
| **First-Line Indent** | Academic paragraph indent | 0.35 in | Justified | 1.5 lines | 6 pt | **PASS** |
| **Chapter Headings** | Times New Roman, Bold, ALL CAPS | 16 pt | Centered | 1.5 lines | 12 pt | **PASS** |
| **Section Headings (X.Y)** | Times New Roman, Bold | 14 pt | Left-Aligned | 1.15 lines | 6 pt | **PASS** |
| **Subsections (X.Y.Z)** | Times New Roman, Bold | 13 pt | Left-Aligned | 1.15 lines | 4 pt | **PASS** |
| **Table / Figure Captions** | Times New Roman, Bold Label + Regular | 10 pt | Centered | 1.15 lines | 6 pt | **PASS** |
| **Table Data Cells** | Times New Roman, Regular | 9.5 pt | Left / Right | Single | 2 pt | **PASS** |
| **Table Header Cells** | Times New Roman, Bold (`#D9E2F3` fill) | 10 pt | Left / Right | Single | 3 pt | **PASS** |
| **Dotted Leader Lines** | Times New Roman with tab leader dots | 12 pt | Left + Right Tab | 1.15 lines | 3 pt | **PASS** |

### 2.3 Page Numbering Hierarchy

The document is divided into two distinct logical and physical Word sections:
1. **Section 1 (Front Matter):**
   - Numbering Format: Lowercase Roman numerals (`i`, `ii`, `iii`, `iv`, `v`, `vi`, `vii`, `viii`, `ix`, `x`).
   - Placement: Centered in the page footer (0.67 in from bottom edge).
   - First-Page Suppression: `different_first_page_header_footer = True`. The Title Page (physical page 1) displays **no page number**, exactly matching university guidelines.
   - Physical page 2 (Declaration) begins at `ii`.
2. **Section 2 (Chapters 1–8, References, Appendix):**
   - Numbering Format: Standard Arabic numerals (`1`, `2`, `3`, ..., `39`).
   - Placement: Centered in the page footer (0.67 in from bottom edge).
   - Continuity: Starts explicitly at Arabic numeral `1` on Chapter 1 (physical page 11) and runs continuously through References (Arabic pages 37–38) and Appendix A (Arabic page 39).
   - Blank Page Prevention: Conditionally disabled redundant page breaks on Chapter 1 to ensure immediate transition without blank filler pages.

---

## 3. Page Budget and Master Layout Mapping

The 49-page master layout is distributed across the academic components as follows:

```
+-----------------------------------------------------------------------------------+
| PHYSICAL PAGE | DISPLAY PAGE | SECTION CONTENT                                    |
+---------------+--------------+----------------------------------------------------+
| Page 01       | [None]       | Title Page (SRM Logo, Project Title, Degree, CSE)  |
| Page 02       | ii           | Declaration (Individual Student Signature Block)   |
| Page 03       | iii          | Certificate (Faculty Guide & HOD Approval Blocks)  |
| Page 04       | iv           | Acknowledgement (Departmental, Guide, SRM Dean)    |
| Page 05       | v            | Abstract (Structured 350-Word Summary + Keywords)  |
| Page 06       | vi           | List of Abbreviations (14 Standardized Acronyms)   |
| Page 07       | vii          | Table of Contents (Chapters 1 to 4)                |
| Page 08       | viii         | Table of Contents (Chapters 4 Cont., 5 to 8, Refs) |
| Page 09       | ix           | List of Tables (14 Verified Empirical Tables)      |
| Page 10       | x            | List of Figures (12 High-Resolution Visualizations)|
+---------------+--------------+----------------------------------------------------+
| Page 11–14    | 1–4          | Chapter 1: Introduction to the Project             |
| Page 15–18    | 5–8          | Chapter 2: Motivation                              |
| Page 19–22    | 9–12         | Chapter 3: Literature Survey                       |
| Page 23–28    | 13–18        | Chapter 4: Design and Methodology                  |
| Page 29–31    | 19–21        | Chapter 5: Implementation                          |
| Page 32–33    | 22–23        | Chapter 6: Hardware / Software Tools Used          |
| Page 34–44    | 24–34        | Chapter 7: Results and Discussion                  |
| Page 45–46    | 35–36        | Chapter 8: Conclusion                              |
| Page 47–48    | 37–38        | References (26 Comprehensive IEEE References)      |
| Page 49       | 39           | Appendix A: Publication Status                     |
+-----------------------------------------------------------------------------------+
```

---

## 4. Two-Pass Layout Reconciliation Audit

Because inserting extensive narrative text, multi-row empirical tables, and large figures into Microsoft Word creates non-linear page wrapping, hardcoded page numbers in the Table of Contents invariably drift. To achieve 100% mathematical precision, `submission/generate_urop_report.py` executes a deterministic two-pass layout compiler:

1. **Pass 1:** Generates the initial `.docx` containing full narrative text, tables, and figures, with placeholder dots in the TOC. Converts the `.docx` to an intermediate `.pdf` via Microsoft Word COM automation.
2. **Page Coordinate Extraction:** Opens the rendered PDF using PyMuPDF (`fitz`), scans text blocks, locates the exact page numbers where every chapter heading, section heading, table caption, and figure caption physically lands, and calculates the exact Arabic offset (`arabic_page = phys_page - ch1_phys_page + 1`).
3. **Pass 2:** Injects the verified page coordinates into the Table of Contents, List of Tables, and List of Figures tables with formatted dot leader lines (`......................................`), regenerates the final `.docx`, and produces the final `.pdf`.

### 4.1 Verification Test Results (TOC / LOT / LOF vs. PDF)

All 35 primary structural landmarks were programmatically verified against the rendered PDF (`submission/verify_toc_exact.py`):

```
Verifying TOC target pages:
  [PASS] CHAPTER 1    -> Arabic p.01 (Phys p.11) confirmed in page text.
  [PASS] CHAPTER 2    -> Arabic p.05 (Phys p.15) confirmed in page text.
  [PASS] CHAPTER 3    -> Arabic p.09 (Phys p.19) confirmed in page text.
  [PASS] CHAPTER 4    -> Arabic p.13 (Phys p.23) confirmed in page text.
  [PASS] CHAPTER 5    -> Arabic p.19 (Phys p.29) confirmed in page text.
  [PASS] CHAPTER 6    -> Arabic p.22 (Phys p.32) confirmed in page text.
  [PASS] CHAPTER 7    -> Arabic p.24 (Phys p.34) confirmed in page text.
  [PASS] CHAPTER 8    -> Arabic p.35 (Phys p.45) confirmed in page text.
  [PASS] REFERENCES   -> Arabic p.37 (Phys p.47) confirmed in page text.
  [PASS] Table 3.1    -> Arabic p.12 (Phys p.22) confirmed in page text.
  [PASS] Table 4.1    -> Arabic p.14 (Phys p.24) confirmed in page text.
  [PASS] Table 4.2    -> Arabic p.15 (Phys p.25) confirmed in page text.
  [PASS] Table 4.3    -> Arabic p.16 (Phys p.26) confirmed in page text.
  [PASS] Table 6.1    -> Arabic p.22 (Phys p.32) confirmed in page text.
  [PASS] Table 6.2    -> Arabic p.22 (Phys p.32) confirmed in page text.
  [PASS] Table 7.1    -> Arabic p.24 (Phys p.34) confirmed in page text.
  [PASS] Table 7.2    -> Arabic p.26 (Phys p.36) confirmed in page text.
  [PASS] Table 7.3    -> Arabic p.27 (Phys p.37) confirmed in page text.
  [PASS] Table 7.4    -> Arabic p.28 (Phys p.38) confirmed in page text.
  [PASS] Table 7.5    -> Arabic p.30 (Phys p.40) confirmed in page text.
  [PASS] Table 7.6    -> Arabic p.30 (Phys p.40) confirmed in page text.
  [PASS] Table 7.7    -> Arabic p.31 (Phys p.41) confirmed in page text.
  [PASS] Table 7.8    -> Arabic p.32 (Phys p.42) confirmed in page text.
  [PASS] Figure 4.1   -> Arabic p.13 (Phys p.23) confirmed in page text.
  [PASS] Figure 4.2   -> Arabic p.18 (Phys p.28) confirmed in page text.
  [PASS] Figure 5.1   -> Arabic p.21 (Phys p.31) confirmed in page text.
  [PASS] Figure 7.1   -> Arabic p.25 (Phys p.35) confirmed in page text.
  [PASS] Figure 7.2   -> Arabic p.26 (Phys p.36) confirmed in page text.
  [PASS] Figure 7.3   -> Arabic p.27 (Phys p.37) confirmed in page text.
  [PASS] Figure 7.4   -> Arabic p.28 (Phys p.38) confirmed in page text.
  [PASS] Figure 7.5   -> Arabic p.29 (Phys p.39) confirmed in page text.
  [PASS] Figure 7.6   -> Arabic p.30 (Phys p.40) confirmed in page text.
  [PASS] Figure 7.7   -> Arabic p.31 (Phys p.41) confirmed in page text.
  [PASS] Figure 7.8   -> Arabic p.32 (Phys p.42) confirmed in page text.
  [PASS] Figure 7.9   -> Arabic p.33 (Phys p.43) confirmed in page text.

>>> ALL 35 CHECKED HEADINGS, TABLES, AND FIGURES MATCH THEIR TOC/LOT/LOF TARGET PAGES EXACTLY! <<<
```

---

## 5. Complete Inventory of Empirical Tables

All 14 tables in the report are populated with authoritative research data, formatted with styled header rows (`#D9E2F3` fill), explicit column widths, repeated table headers across pages (`tblHeader`), and row split prevention (`cantSplit`):

| Table ID | Table Caption | Arabic Page | Physical Page | Authoritative Source / Experiment |
| :--- | :--- | :---: | :---: | :--- |
| **Table 3.1** | Comparative Literature Survey Summary | 12 | 22 | Academic Literature Synthesis (10 Studies) |
| **Table 4.1** | Dataset Composition and Provenance Summary | 14 | 24 | `data/dataset_versions/v2/provenance.json` |
| **Table 4.2** | Zero-Payload Feature Categories and Descriptions | 15 | 25 | Feature Extraction Schema (76 Features) |
| **Table 4.3** | Machine Learning Model Hyperparameters | 16 | 26 | `training/model_registry.py` |
| **Table 6.1** | Hardware Requirements and Specifications | 22 | 32 | Host Hardware Benchmarking Profile |
| **Table 6.2** | Software Requirements and Dependencies | 22 | 32 | Python 3.14 & Scapy / Windows IP Helper Stack |
| **Table 7.1** | Baseline Model Comparison Results | 24 | 34 | EXP-R09 (`results/tables/research_baseline.csv`) |
| **Table 7.2** | Feature Count Tradeoff Results | 26 | 36 | EXP-R10 (`results/tables/feature_count_tradeoff_research.csv`) |
| **Table 7.3** | Feature Family Ablation Results | 27 | 37 | EXP-R10 (`results/tables/feature_family_ablation_research.csv`) |
| **Table 7.4** | Cross-Environment Generalization Results | 28 | 38 | EXP-R11 (`results/tables/research_generalization_scorecard.csv`) |
| **Table 7.5** | Early Prediction Results Across Packet Horizons | 30 | 40 | EXP-R12 (`results/tables/research_early_prediction.csv`) |
| **Table 7.6** | Selective Classification Results at Different Thresholds | 30 | 40 | EXP-R13 (`results/tables/research_selective_prediction.csv`) |
| **Table 7.7** | Computational Latency Measurements | 31 | 41 | EXP-R14 (`results/tables/research_latency.csv`) |
| **Table 7.8** | Real-Time Pipeline Validation Results | 32 | 42 | EXP-R15 (`results/tables/realtime_research_validation.csv`) |

---

## 6. Complete Inventory of Figures and Visualizations

All 12 visual figures are embedded as high-resolution images, properly centered, with standard academic figure captions positioned underneath:

| Figure ID | Figure Caption | Arabic Page | Physical Page | Source Asset Path / Generator |
| :--- | :--- | :---: | :---: | :--- |
| **Figure 4.1** | End-to-End System Architecture | 13 | 23 | `UROP_Report/Assets/architecture_diagram.png` |
| **Figure 4.2** | Research Methodology Workflow | 18 | 28 | `UROP_Report/Assets/workflow_flowchart.png` |
| **Figure 5.1** | Real-Time Streaming Pipeline and Cybersecurity SOC Architecture | 21 | 31 | `submission/fig_soc_architecture.png` (300 DPI) |
| **Figure 7.1** | Baseline Model Comparison — Validation and Test Macro-F1 Scores | 25 | 35 | `UROP_Report/Assets/fig_baseline_comparison.png` |
| **Figure 7.2** | Decision Tree and Random Forest Confusion Matrices on Test Split | 26 | 36 | `UROP_Report/Assets/fig_confusion_matrix.png` |
| **Figure 7.3** | Feature Count Tradeoff Curve and Pareto Frontier | 27 | 37 | `UROP_Report/Assets/fig_feature_pareto.png` |
| **Figure 7.4** | Cross-Environment Generalization Across Distribution Shift Regimes | 28 | 38 | `UROP_Report/Assets/fig_generalization.png` |
| **Figure 7.5** | Asymmetric Tunnel Generalization Failure Under WireGuard Encapsulation | 29 | 39 | `UROP_Report/Assets/fig_tunnel_shift.png` |
| **Figure 7.6** | Early Prediction Performance Across Packet Observation Horizons | 30 | 40 | `UROP_Report/Assets/fig_early_prediction.png` |
| **Figure 7.7** | Selective Classification Coverage vs. Selective Accuracy Tradeoff | 31 | 41 | `UROP_Report/Assets/fig_selective_coverage.png` |
| **Figure 7.8** | Computational Latency Distribution Across Pipeline Stages | 32 | 42 | `UROP_Report/Assets/fig_latency_distribution.png` |
| **Figure 7.9** | Confidence Calibration Curve and Expected Calibration Error | 33 | 43 | `UROP_Report/Assets/fig_calibration_curve.png` |

---

## 7. Scientific Rigor and Empirical Claims Audit

The report strictly adheres to the research project's empirical ground rules to prevent scientific inflation, inaccurate claims, or misleading interpretations:

1. **Pre-Registered Baseline Winner (EXP-R09):**
   - **LightGBM** is declared the primary baseline winner based on pre-registered validation Macro-F1:
     $$\text{Val Macro-F1} = 0.5664, \quad \text{Test Macro-F1} = 0.5474$$
   - The Decision Tree achieved a higher test Macro-F1 ($0.5802$) on the held-out test split, but had a lower validation Macro-F1 ($0.5054$). To avoid post-hoc test-set selection bias, the report explicitly documents Decision Tree's score while upholding LightGBM as the statistically pre-registered model.
2. **Dataset V2 Provenance:**
   - Identified as `HYBRID_PERTURBED`, comprising **121 genuine physical Wi-Fi 802.11ax flows** and **180 controlled statistical perturbations**, totaling **301 flows**.
   - Ethernet and Cellular LTE evaluation regimes are explicitly classified as controlled statistical perturbations, NOT claimed as physical hardware captures.
3. **Dataset V3 Attribution & Pilot Quarantine:**
   - The Windows process-attribution subsystem (sampling-density coverage calculation and boundary-aware gap enforcement) is fully documented in Chapter 5.
   - All 90 flows collected during Pilot Sessions 1 & 2 are strictly classified as `AMBIGUOUS` under ground-truth provenance rules and are properly quarantined from model training.
4. **Dominant Latency Driver (EXP-R14 & EXP-R15):**
   - Total early prediction triage latency is **84.33 ms**, of which physical network packet accumulation delay accounts for **64.21 ms (>76.1%)**.
   - Total full-flow latency is **59.73 s**, where physical duration accounts for **59.70 s (>99.9%)**.
   - Algorithm feature extraction (13.72 ms) and inference (6.40 ms) represent negligible fractions of end-to-end latency.
5. **Selective Classification Ceiling (EXP-R13):**
   - At confidence threshold $\tau = 0.90$, the classifier achieves **100.0% selective accuracy**, but coverage drops to **58.7%**, successfully abstaining on 41.3% of ambiguous flows.

---

## 8. Student and Supervisor Action Checklist

Before printing, binding, and formal department submission, the student must review and complete the following items:

- [ ] **1. Insert Official Registration Number:**
  Replace the bracketed placeholder `[INSERT OFFICIAL REGISTRATION NUMBER]` with your actual SRM University-AP student roll/registration number (e.g., `AP21110010XXX`).
  *Locations:* Title Page (p. 1), Declaration (p. 2), Certificate (p. 3), Acknowledgement (p. 4).
- [ ] **2. Insert Official Guide Name and Designation:**
  Replace `[INSERT OFFICIAL GUIDE NAME AND DESIGNATION]` with your faculty supervisor's formal title and department position (e.g., *Dr. John Doe, Associate Professor*).
  *Locations:* Title Page (p. 1), Declaration (p. 2), Certificate (p. 3), Acknowledgement (p. 4).
- [ ] **3. Insert Head of Department Name:**
  Replace `[INSERT HOD NAME]` on the Certificate page (p. 3) with the official name of the Head of the Department of Computer Science & Engineering.
- [ ] **4. Physical Signatures & Dates:**
  - Sign your name above "Gorakala Rishik" on the Declaration (p. 2) and Acknowledgement (p. 4).
  - Obtain the physical or digital signature of your faculty guide on the Certificate (p. 3).
  - Obtain the physical or digital signature of the HOD on the Certificate (p. 3).
  - Verify the submission date (default: *November, 2026*).
- [ ] **5. Institutional Plagiarism & AI Verification:**
  - Submit the final `.docx` or text extract to the official SRM University-AP Turnitin / DrillBit portal as required by departmental submission guidelines.
  - Retain the official Similarity Report alongside this QA document.

---

## 9. Conclusion

The academic project report `submission/UROP_Academic_Report.docx` and its corresponding export `submission/UROP_Academic_Report.pdf` meet all formal, typographical, and scientific criteria required for the Undergraduate Research Opportunity Program (UROP) at SRM University-AP. All claims, metrics, and experimental results are 100% faithful to the underlying research codebase.
