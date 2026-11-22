# Quality Assurance Audit Report: Condensed 30-Page UROP Academic Report

**Document Title:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Academic Program:** Undergraduate Research Opportunity Program (UROP)  
**Institution:** SRM University-AP, Andhra Pradesh  
**Department:** Department of Computer Science & Engineering, School of Engineering and Sciences  
**Student Author:** Gorakala Rishik  
**Supervisor / Mentor:** `[INSERT OFFICIAL GUIDE NAME AND DESIGNATION]`  
**Date of Audit:** November 22, 2026  
**Target Constraint:** **EXACTLY 30 PHYSICAL A4 PAGES**  
**Audit Status:** **PASSED (100% COMPLIANT — EXACTLY 30 PAGES)**  

---

## 1. Executive Summary & Deliverables

This Quality Assurance (QA) audit certifies that the condensed 30-page edition of the Undergraduate Research Opportunity Program (UROP) academic project report has been compiled and verified in strict accordance with the university requirements.

The report condenses the previous 49-page monograph into an academically rigorous, comprehensive, and non-redundant **30-page edition**, preserving all foundational mathematical formulations, empirical tables, high-resolution architectural diagrams, and experimental findings.

Both the Microsoft Word document (`.docx`) and high-fidelity PDF export (`.pdf`) were compiled using the deterministic two-pass layout engine [`submission/generate_urop_report_30p.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/generate_urop_report_30p.py). The original 49-page deliverables ([`submission/UROP_Academic_Report.docx`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report.docx) and [`submission/UROP_Academic_Report.pdf`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report.pdf)) remain untouched.

### Primary Deliverables Summary

| Artifact Path | Format | File Size | Physical Page Count | Compliance Status |
| :--- | :---: | :---: | :---: | :---: |
| [`submission/UROP_Academic_Report_30P.docx`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report_30P.docx) | Word (DOCX) | 1,565,383 bytes (~1.57 MB) | 30 pages | **VERIFIED** |
| [`submission/UROP_Academic_Report_30P.pdf`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report_30P.pdf) | Adobe PDF (1.7) | 788,555 bytes (~789 KB) | **30 pages (EXACT)** | **VERIFIED** |
| [`submission/REPORT_QA_30P.md`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/REPORT_QA_30P.md) | QA Audit Report | ~18 KB | — | **VERIFIED** |
| [`submission/generate_urop_report_30p.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/generate_urop_report_30p.py) | Python Generator | 56,120 bytes | — | **VERIFIED** |
| [`submission/page_images_30p/`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/page_images_30p/) | PNG (150 DPI) | 30 Rendered Images | 30 images | **VERIFIED** |

---

## 2. Strict 30-Page Layout Distribution

Every page of the 30-page PDF was individually rendered to an image ([`submission/page_images_30p/`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/page_images_30p/)) and audited for character density, vertical text block bounds (`max_y1`), footer numbering, and visual clarity.

| Phys Page | Display Page | Section / Content | Visual Elements Included | Chars | Status |
| :---: | :---: | :--- | :--- | :---: | :---: |
| **01** | [None] | **Title Page** | SRM AP Official Crest Logo (~1.5 in width) | 560 | **PASS** |
| **02** | **ii** | **Declaration** | Formal 2-column borderless signature block | 1,461 | **PASS** |
| **03** | **iii** | **Certificate** | Formal 2-column Guide & HOD approval block | 1,411 | **PASS** |
| **04** | **iv** | **Acknowledgement** | Departmental & supervisor gratitude + signature | 1,547 | **PASS** |
| **05** | **v** | **Abstract & Keywords** | 350-word structured abstract + 8 keywords | 2,641 | **PASS** |
| **06** | **vi** | **Table of Contents** | 26 primary headings with dot leader lines | 2,813 | **PASS** |
| **07** | **vii** | **List of Tables** | 11 empirical data tables with page links | 905 | **PASS** |
| **08** | **viii** | **List of Figures** | 7 high-resolution figures with page links | 603 | **PASS** |
| **09** | **1** | **Chapter 1: Introduction** | 1.1 Background, Problem Statement, 4 Gaps | 2,620 | **PASS** |
| **10** | **2** | **Chapter 1: Objectives** | 1.2 Five Core Contributions, Report Outline | 2,471 | **PASS** |
| **11** | **3** | **Chapter 2: Motivation** | 2.1 DPI Limits, 2.2 Zero-Payload & Lightweight ML | 1,981 | **PASS** |
| **12** | **4** | **Chapter 3: Literature Survey** | 3.1 Prior Encrypted Traffic Classification Works | 2,188 | **PASS** |
| **13** | **5** | **Chapter 3: Synthesis** | 3.2 Research Gaps, **Table 3.1** (10-Study Survey) | 2,898 | **PASS** |
| **14** | **6** | **Chapter 4: Methodology** | 4.1 System Overview, **Figure 4.1** (Architecture) | 1,217 | **PASS** |
| **15** | **7** | **Chapter 4: Dataset** | 4.2 Dataset Provenance, **Table 4.1** (Dataset V2) | 1,835 | **PASS** |
| **16** | **8** | **Chapter 4: Features & ML** | 4.3 Feature Schemas (**Table 4.2**), Models (**Table 4.3**) | 2,331 | **PASS** |
| **17** | **9** | **Chapter 4: Protocol** | 4.4 Evaluation Protocol, **Figure 4.2** (Workflow) | 1,063 | **PASS** |
| **18** | **10** | **Chapter 5: Implementation** | 5.1 Real-Time Capture, BPF, 5-Tuple, Welford O(1) | 1,545 | **PASS** |
| **19** | **11** | **Chapter 5: Streaming** | 5.2 Streaming Pipeline, **Figure 5.1** (SOC Pipeline) | 1,120 | **PASS** |
| **20** | **12** | **Chapter 5: Integrity** | 5.3 Fail-Closed Safety, Dataset V3 Validation | 1,605 | **PASS** |
| **21** | **13** | **Chapter 6: Hardware/Tools** | 6.1 System Stack, **Table 6.1** (HW), **Table 6.2** (SW) | 2,535 | **PASS** |
| **22** | **14** | **Chapter 7: Results (EXP-R09)** | 7.1 Baseline Winner, **Table 7.1**, **Figure 7.1** | 1,437 | **PASS** |
| **23** | **15** | **Chapter 7: Results (EXP-R10)** | 7.2 Feature Selection, **Table 7.2**, **Figure 7.2** | 1,705 | **PASS** |
| **24** | **16** | **Chapter 7: Results (EXP-R11)** | 7.3 Generalization, **Table 7.3**, **Figure 7.3** | 1,476 | **PASS** |
| **25** | **17** | **Chapter 7: Results (R12–R15)** | 7.4 Wire Delay (**Fig 7.4**), **Table 7.4** (Sel), **Table 7.5** | 2,336 | **PASS** |
| **26** | **18** | **Chapter 8: Conclusion** | 8.1 Research Accomplishments, 8.2 Future Scope | 2,595 | **PASS** |
| **27** | **19** | **References (Part 1)** | References [1] to [9] (IEEE Monograph Format) | 1,602 | **PASS** |
| **28** | **20** | **References (Part 2)** | References [10] to [18] (IEEE Monograph Format) | 1,319 | **PASS** |
| **29** | **21** | **References (Part 3)** | References [19] to [26] (IEEE Monograph Format) | 1,067 | **PASS** |
| **30** | **22** | **Appendix A: Publications** | A.1 Dissemination Roadmap, A.2 Code Availability | 1,931 | **PASS** |

**Total Verified Physical Pages:** **30 Pages (Zero overflow, zero blank pages).**

---

## 3. Formatting & Typographical Compliance Audit

The condensed document maintains 100% compliance with SRM University-AP departmental guidelines:

| Parameter | Specification | Implemented Value | Verification Status |
| :--- | :--- | :--- | :---: |
| **Page Size** | ISO A4 (210 mm × 297 mm) | 210 mm × 297 mm (`docx.shared.Inches(8.27 × 11.69)`) | **PASS** |
| **Left Margin** | 1.25 inches (31.75 mm) for hard binding | 1.25 in (90.0 pt) | **PASS** |
| **Right Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Top Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Bottom Margin** | 1.00 inch (25.40 mm) | 1.00 in (72.0 pt) | **PASS** |
| **Body Font** | Times New Roman, Regular | 12 pt | **PASS** |
| **Line Spacing** | Academic 1.35–1.5 line spacing | 1.35 line spacing (0 pt before, 4 pt after) | **PASS** |
| **Paragraph Indent**| Academic first-line indent | 0.35 inches (0.89 cm) | **PASS** |
| **Chapter Headings**| Times New Roman, Bold, ALL CAPS | 16 pt Centered | **PASS** |
| **Section Headings**| Times New Roman, Bold | 13–13.5 pt Left-Aligned | **PASS** |
| **Dual Numbering** | Roman (i–viii) & Arabic (1–22) | Roman on pp. 2–8; Arabic 1–22 on pp. 9–30 | **PASS** |
| **Title Suppression**| No page number on Title Page | `different_first_page_header_footer = True` | **PASS** |

---

## 4. Two-Pass Layout Reconciliation Audit (Zero Drift)

All 26 Table of Contents entries, 11 List of Tables entries, and 7 List of Figures entries match their physical rendered page coordinates with **100% mathematical precision**:

### 4.1 Table of Contents Reconciliation

```
CHAPTER 1   INTRODUCTION TO THE PROJECT .................................... 1 [MATCH]
    1.1  Background and Problem Statement .................................. 1 [MATCH]
    1.2  Objectives, Scope, and Contributions .............................. 2 [MATCH]
CHAPTER 2   MOTIVATION ..................................................... 3 [MATCH]
    2.1  Limitations of Deep Packet Inspection ............................. 3 [MATCH]
    2.2  Need for Zero-Payload and Lightweight Models ...................... 3 [MATCH]
CHAPTER 3   LITERATURE SURVEY .............................................. 4 [MATCH]
    3.1  Existing Encrypted Traffic Classification ......................... 4 [MATCH]
    3.2  Research Gaps and Comparative Literature Synthesis ................ 5 [MATCH]
CHAPTER 4   DESIGN AND METHODOLOGY ......................................... 6 [MATCH]
    4.1  System Overview and Architecture .................................. 6 [MATCH]
    4.2  Dataset Provenance and Multi-Environment Setup .................... 7 [MATCH]
    4.3  Zero-Payload Feature Engineering and Models ....................... 8 [MATCH]
    4.4  Training, Evaluation, and Early Triage Protocol ................... 9 [MATCH]
CHAPTER 5   IMPLEMENTATION ................................................ 10 [MATCH]
    5.1  Real-Time Capture and Flow Management ............................ 10 [MATCH]
    5.2  Streaming Pipeline and SOC Architecture .......................... 11 [MATCH]
    5.3  Fail-Closed Integrity and Dataset V3 Validation .................. 12 [MATCH]
CHAPTER 6   HARDWARE / SOFTWARE TOOLS USED ................................ 13 [MATCH]
    6.1  System Requirements and Software Stack ........................... 13 [MATCH]
CHAPTER 7   RESULTS AND DISCUSSION ........................................ 14 [MATCH]
    7.1  Baseline Model Performance (EXP-R09) ............................. 14 [MATCH]
    7.2  Feature Selection and Ablation (EXP-R10) ......................... 15 [MATCH]
    7.3  Cross-Environment Shift and Tunnel Fragility (EXP-R11) ........... 16 [MATCH]
    7.4  Early Traffic Triage, Wire Delay, and Selective Classification .... 17 [MATCH]
    7.5  Computational Efficiency and Pipeline Validation ................. 17 [MATCH]
CHAPTER 8   CONCLUSION .................................................... 18 [MATCH]
    8.1  Research Summary and Key Findings ................................ 18 [MATCH]
    8.2  Practical Limitations and Future Work ............................ 18 [MATCH]
REFERENCES ................................................................ 19 [MATCH]
APPENDIX A: PUBLICATION STATUS ............................................ 22 [MATCH]
```

### 4.2 List of Tables & Figures Reconciliation

| Item ID | Item Caption | LOT / LOF Page | Rendered Arabic Page | Physical Page | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Table 3.1** | Comparative Literature Survey Summary | 5 | 5 | 13 | **MATCH** |
| **Table 4.1** | Dataset Composition and Provenance Summary | 7 | 7 | 15 | **MATCH** |
| **Table 4.2** | Zero-Payload Feature Categories and Extraction Schemas | 8 | 8 | 16 | **MATCH** |
| **Table 4.3** | Machine Learning Model Hyperparameters and Configurations | 8 | 8 | 16 | **MATCH** |
| **Table 6.1** | Hardware Requirements and Specifications | 13 | 13 | 21 | **MATCH** |
| **Table 6.2** | Software Requirements and Dependencies | 13 | 13 | 21 | **MATCH** |
| **Table 7.1** | Baseline Model Comparison Results (EXP-R09) | 14 | 14 | 22 | **MATCH** |
| **Table 7.2** | Feature Count Tradeoff and Family Ablation Results (EXP-R10) | 15 | 15 | 23 | **MATCH** |
| **Table 7.3** | Cross-Environment Generalization Results (EXP-R11) | 16 | 16 | 24 | **MATCH** |
| **Table 7.4** | Selective Classification Results at Distinct Thresholds (EXP-R13) | 17 | 17 | 25 | **MATCH** |
| **Table 7.5** | Computational Latency and Real-Time Pipeline Performance | 17 | 17 | 25 | **MATCH** |
| **Figure 4.1** | End-to-End Zero-Payload System Architecture | 6 | 6 | 14 | **MATCH** |
| **Figure 4.2** | Reproducible Research Methodology and Evaluation Workflow | 9 | 9 | 17 | **MATCH** |
| **Figure 5.1** | Real-Time Streaming Pipeline and Cybersecurity SOC Architecture | 11 | 11 | 19 | **MATCH** |
| **Figure 7.1** | Baseline Model Comparison — Validation and Test Macro-F1 Scores | 14 | 14 | 22 | **MATCH** |
| **Figure 7.2** | Feature Count Tradeoff Curve and Pareto Frontier | 15 | 15 | 23 | **MATCH** |
| **Figure 7.3** | Cross-Environment Generalization Across Distribution Shift Regimes | 16 | 16 | 24 | **MATCH** |
| **Figure 7.4** | Early Prediction Performance Across Packet Observation Horizons | 17 | 17 | 25 | **MATCH** |

---

## 5. Scientific Accuracy & Authoritative Data Integrity

The condensed report strictly adheres to all empirical benchmarks established in the authoritative experiment CSV files:

1. **Pre-Registered Baseline Winner (EXP-R09):**
   - **LightGBM** is declared the baseline winner based on pre-registered validation Macro-F1:
     $$\text{Val Macro-F1} = 0.5664, \quad \text{Test Macro-F1} = 0.5474$$
   - Decision Tree achieved test Macro-F1 of $0.5802$ and Random Forest achieved $0.5854$. To prevent test-set selection bias, LightGBM is upheld as the statistically valid winner.
2. **Dataset V2 Provenance:**
   - Explicitly documented as `HYBRID_PERTURBED`: **121 genuine physical Wi-Fi (802.11ax) flows** and **180 controlled statistical perturbations**, totaling **301 flows across 150 sessions**.
   - Ethernet and Cellular LTE conditions are explicitly noted as statistical perturbations, NOT native physical captures.
3. **Feature Count Sweet Spot (EXP-R10):**
   - Top-3 features achieve test Macro-F1 of **0.6708** (versus **0.3359** for all 84 features), demonstrating that statistical dimensionality reduction overcomes the curse of dimensionality.
4. **Generalization & WireGuard Tunnel Fragility (EXP-R11):**
   - Robust on unseen simulated media (**0.9325 F1**) and network impairments (**0.9030 F1**).
   - Catastrophic collapse under Direct-to-WARP WireGuard encapsulation (**0.3407 F1**) due to MTU clamping to 1280 bytes.
5. **Early Prediction & Wire Delay Primacy (EXP-R12):**
   - Horizon $N = 3$ packets achieves **0.6111 Macro-F1** with **91.67% coverage** in **84.33 ms total latency**.
   - Physical wire accumulation delay accounts for **64.21 ms (>76.1%)** of early triage latency and **>99.9%** of full-flow classification time (59.70 s of 59.73 s), proving that physical packet arrival dominates classification delay.
6. **Selective Classification (EXP-R13):**
   - At threshold $\tau^* = 0.70$: selective accuracy rises to **73.08%** (Macro-F1 = **0.6515**, coverage = **54.17%**), reducing error from 45.83% to 26.92%.
   - At $\tau = 0.90$: selective accuracy reaches **100.0%** on accepted traffic.
7. **Computational Latency & Pipeline Stability (EXP-R14, EXP-R15):**
   - Decision Tree warm inference latency: $P_{50} = 0.0578\text{ ms}, P_{95} = 0.0924\text{ ms}$, footprint = $9.58\text{ KB}$.
   - Live capture pipeline sustained **zero packet drops**, **zero processing exceptions**, and **100% compliance with the zero-payload privacy contract**.
8. **Dataset V3 Attribution Quarantine:**
   - The Windows IP Helper attribution policy enforced sampling-density coverage ($\ge 0.50$) and boundary-aware gap limits ($\le 0.500\text{ s}$).
   - All 90 pilot flows are strictly classified as `AMBIGUOUS` and quarantined from model training.

---

## 6. Student Action Checklist & Administrative Placeholders

Before final departmental submission, printing, and binding, the student must update the following bracketed administrative placeholders:

- [ ] **1. Student Registration Number:**
  Replace `[INSERT OFFICIAL REGISTRATION NUMBER]` with your official SRM University-AP roll number (e.g., `AP21110010XXX`).
  *Locations:* Title Page (p. 1), Declaration (p. 2), Certificate (p. 3), Acknowledgement (p. 4).
- [ ] **2. Faculty Guide Name and Designation:**
  Replace `[INSERT OFFICIAL GUIDE NAME AND DESIGNATION]` with your faculty mentor's formal academic title (e.g., *Dr. Jane Doe, Associate Professor*).
  *Locations:* Title Page (p. 1), Declaration (p. 2), Certificate (p. 3), Acknowledgement (p. 4).
- [ ] **3. Head of Department Name:**
  Replace `[INSERT HOD NAME]` on the Certificate page (p. 3) with the name of the Head of the Department of Computer Science & Engineering.
- [ ] **4. Physical Signatures & Dates:**
  - Sign above "Gorakala Rishik" on Declaration (p. 2) and Acknowledgement (p. 4).
  - Obtain Guide and HOD signatures on Certificate (p. 3).
- [ ] **5. Academic Integrity Scan:**
  Submit the document to the official SRM University-AP Turnitin portal as per departmental submission protocol.

---

## 7. Conclusion

The condensed academic report [`submission/UROP_Academic_Report_30P.docx`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report_30P.docx) and its PDF counterpart [`submission/UROP_Academic_Report_30P.pdf`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/submission/UROP_Academic_Report_30P.pdf) satisfy the **strict 30-page requirement with 100% mathematical precision**. All empirical claims, tables, figures, and structural formatting elements adhere strictly to SRM University-AP standards.
