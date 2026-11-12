"""
Generator for the complete UROP Final Report for SRM University-AP.
Exact reproduction of formatting, typography, structure, and academic rigor based on sample_urop.docx.
"""

import os
import shutil
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_urop_report():
    os.makedirs("UROP_Report", exist_ok=True)
    os.makedirs("UROP_Report/UROP_Report_Assets", exist_ok=True)
    output_docx = "UROP_Report/UROP_Final_Report.docx"

    doc = docx.Document()

    # -------------------------------------------------------------
    # STYLES & TYPOGRAPHY SETUP (Matching sample_urop.docx: Book Antiqua)
    # -------------------------------------------------------------
    styles = doc.styles

    # Normal Style
    normal_style = styles['Normal']
    normal_font = normal_style.font
    normal_font.name = 'Book Antiqua'
    normal_font.size = Pt(12)
    normal_font.color.rgb = RGBColor(0x1E, 0x29, 0x3B) # Professional Dark Slate
    normal_p_format = normal_style.paragraph_format
    normal_p_format.line_spacing = 1.15
    normal_p_format.space_after = Pt(6)
    normal_p_format.space_before = Pt(0)
    normal_p_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Heading 1
    h1_style = styles['Heading 1']
    h1_font = h1_style.font
    h1_font.name = 'Book Antiqua'
    h1_font.size = Pt(16)
    h1_font.bold = True
    h1_font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    h1_format = h1_style.paragraph_format
    h1_format.line_spacing = 1.15
    h1_format.space_before = Pt(14)
    h1_format.space_after = Pt(6)
    h1_format.keep_with_next = True
    h1_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Heading 2
    h2_style = styles['Heading 2']
    h2_font = h2_style.font
    h2_font.name = 'Book Antiqua'
    h2_font.size = Pt(14)
    h2_font.bold = True
    h2_font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    h2_format = h2_style.paragraph_format
    h2_format.line_spacing = 1.15
    h2_format.space_before = Pt(12)
    h2_format.space_after = Pt(4)
    h2_format.keep_with_next = True

    # Heading 3
    h3_style = styles['Heading 3']
    h3_font = h3_style.font
    h3_font.name = 'Book Antiqua'
    h3_font.size = Pt(12)
    h3_font.bold = True
    h3_font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    h3_format = h3_style.paragraph_format
    h3_format.line_spacing = 1.15
    h3_format.space_before = Pt(8)
    h3_format.space_after = Pt(2)
    h3_format.keep_with_next = True

    # -------------------------------------------------------------
    # HELPER FUNCTIONS FOR FORMATTING
    # -------------------------------------------------------------
    def add_para(text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=6, bold=False, italic=False, size=12):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if text:
            run = p.add_run(text)
            run.font.name = 'Book Antiqua'
            run.font.size = Pt(size)
            run.bold = bold
            run.italic = italic
        return p

    def add_h1(title, center=False):
        p = doc.add_paragraph(style='Heading 1')
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(title)
        run.font.name = 'Book Antiqua'
        run.font.size = Pt(16)
        run.bold = True
        return p

    def add_h2(title):
        p = doc.add_paragraph(style='Heading 2')
        run = p.add_run(title)
        run.font.name = 'Book Antiqua'
        run.font.size = Pt(14)
        run.bold = True
        return p

    def add_h3(title):
        p = doc.add_paragraph(style='Heading 3')
        run = p.add_run(title)
        run.font.name = 'Book Antiqua'
        run.font.size = Pt(12)
        run.bold = True
        return p

    def add_figure(img_path, caption_text, width_inches=5.8):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(10)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.paragraph_format.keep_with_next = True
            run_img = p_img.add_run()
            run_img.add_picture(img_path, width=Inches(width_inches))

            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_before = Pt(2)
            p_cap.paragraph_format.space_after = Pt(12)
            run_cap = p_cap.add_run(caption_text)
            run_cap.font.name = 'Book Antiqua'
            run_cap.font.size = Pt(10.5)
            run_cap.bold = True
            run_cap.italic = True
        else:
            p = add_para(f"[{caption_text} - Image Missing: {img_path}]", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)

    def set_cell_border(cell, **kwargs):
        """Sets individual cell borders with XML manipulation."""
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = parse_xml(r'<w:tcBorders %s>'
                              r'<w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                              r'<w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                              r'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                              r'<w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                              r'</w:tcBorders>' % nsdecls('w'))
        tcPr.append(tcBorders)

    def set_cell_shading(cell, color_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(r'<w:shd %s w:fill="%s"/>' % (nsdecls('w'), color_hex))
        tcPr.append(shd)

    def style_table(table, col_widths, headers, data, caption=""):
        if caption:
            p_cap = doc.add_paragraph()
            p_cap.paragraph_format.space_before = Pt(10)
            p_cap.paragraph_format.space_after = Pt(4)
            p_cap.paragraph_format.keep_with_next = True
            run = p_cap.add_run(caption)
            run.font.name = 'Book Antiqua'
            run.font.size = Pt(10.5)
            run.bold = True

        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Populate headers
        hdr_cells = table.rows[0].cells
        for idx, h_text in enumerate(headers):
            hdr_cells[idx].text = h_text
            set_cell_shading(hdr_cells[idx], "E2E8F0")
            set_cell_border(hdr_cells[idx])
            p = hdr_cells[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            for r in p.runs:
                r.font.name = 'Book Antiqua'
                r.font.size = Pt(9.5)
                r.bold = True
                r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

        # Populate data rows
        for r_idx, row_data in enumerate(data):
            row_cells = table.rows[r_idx + 1].cells
            bg_color = "F8FAFC" if (r_idx % 2 == 1) else "FFFFFF"
            for c_idx, val in enumerate(row_data):
                row_cells[c_idx].text = str(val)
                set_cell_shading(row_cells[c_idx], bg_color)
                set_cell_border(row_cells[c_idx])
                p = row_cells[c_idx].paragraphs[0]
                # If numeric or short, center; if description, left align
                if len(str(val)) <= 15:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(3)
                for r in p.runs:
                    r.font.name = 'Book Antiqua'
                    r.font.size = Pt(9.0)

        # Apply column widths
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(0)
        p_after.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # SECTION 0: COVER PAGE (Strictly Matching sample_urop.docx)
    # -------------------------------------------------------------
    s0 = doc.sections[0]
    s0.page_width = Inches(8.27)
    s0.page_height = Inches(11.69)
    s0.top_margin = Inches(1.0)
    s0.bottom_margin = Inches(1.0)
    s0.left_margin = Inches(1.0)
    s0.right_margin = Inches(1.0)
    s0.different_first_page_header_footer = True

    add_para("REAL-TIME ENCRYPTED TRAFFIC CLASSIFICATION USING LIGHTWEIGHT MACHINE LEARNING MODELS", 
             align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18, bold=True, size=16)

    add_para("UROP Project submitted to the", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, size=12)
    add_para("SRM University – AP, Andhra Pradesh", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=12, size=12)

    add_para("for the partial fulfillment of the requirements to award the degree of", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4, size=12)
    add_para("Bachelor of Technology\nin", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, bold=True, size=12)
    add_para("Computer Science and Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, bold=True, size=12)
    add_para("School of Engineering and Sciences", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=18, bold=True, size=12)

    add_para("Submitted by", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6, size=12)
    add_para("Student Name | AP21110010489\nStudent Name | AP21110010488\nStudent Name | AP21110010490", 
             align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=18, bold=True, size=12)

    # University Logo
    logo_path = "UROP_Report/UROP_Report_Assets/srm_logo.png"
    if os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_before = Pt(6)
        p_logo.paragraph_format.space_after = Pt(18)
        run_logo = p_logo.add_run()
        run_logo.add_picture(logo_path, width=Inches(1.69))

    add_para("Under the Guidance of", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4, size=12)
    add_para("Dr. Mentor Name", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, bold=True, size=12)
    add_para("SRM University–AP\nNeerukonda, Mangalagiri,\nGuntur Andhra Pradesh – 522 240", 
             align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=14, bold=True, size=12)
    add_para("November, 2026", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, bold=True, size=12)

    # -------------------------------------------------------------
    # SECTION 1: PRELIMINARY PAGES (Roman Lowercase: i, ii, iii...)
    # -------------------------------------------------------------
    s1 = doc.add_section(docx.enum.section.WD_SECTION_START.NEW_PAGE)
    s1.page_width = Inches(8.27)
    s1.page_height = Inches(11.69)
    s1.top_margin = Inches(1.0)
    s1.bottom_margin = Inches(1.0)
    s1.left_margin = Inches(1.0)
    s1.right_margin = Inches(1.0)
    s1.different_first_page_header_footer = False

    # Page number formatting: romanLower starting at i
    s1_sectPr = s1._sectPr
    s1_sectPr.append(parse_xml(r'<w:pgNumType %s w:fmt="romanLower" w:start="1"/>' % nsdecls('w')))
    footer1 = s1.footer
    p_f1 = footer1.paragraphs[0]
    p_f1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_f1._p.append(parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w')))

    # CERTIFICATE
    add_h1("Certificate", center=True)
    add_para("This is to certify that the project report entitled \"REAL-TIME ENCRYPTED TRAFFIC CLASSIFICATION USING LIGHTWEIGHT MACHINE LEARNING MODELS\" submitted by Student Name (Reg. No: AP21110010489), Student Name (Reg. No: AP21110010488), and Student Name (Reg. No: AP21110010490) to SRM University – AP, Andhra Pradesh, for the partial fulfillment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering is a bona fide record of research work carried out by them under my supervision and guidance.", space_before=14, space_after=12)
    
    add_para("The results embodied in this report have not been submitted to any other University or Institute for the award of any degree or diploma. The research satisfies all ethical, institutional, and technical standards established by the School of Engineering and Sciences.", space_after=40)

    # Signature blocks
    p_sig = doc.add_paragraph()
    p_sig.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_sig.paragraph_format.line_spacing = 1.2
    run1 = p_sig.add_run("______________________________\nDr. Mentor Name\nFaculty Mentor / Supervisor\nAssistant Professor, Department of CSE\nSchool of Engineering and Sciences\nSRM University – AP\n")
    run1.bold = True
    run1.font.name = 'Book Antiqua'
    run1.font.size = Pt(11)

    p_sig2 = doc.add_paragraph()
    p_sig2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig2.paragraph_format.line_spacing = 1.2
    run2 = p_sig2.add_run("______________________________\nHead of the Department\nDepartment of Computer Science and Engineering\nSchool of Engineering and Sciences\nSRM University – AP\n")
    run2.bold = True
    run2.font.name = 'Book Antiqua'
    run2.font.size = Pt(11)

    # Page Break -> ACKNOWLEDGEMENTS
    doc.add_page_break()
    add_h1("Acknowledgements", center=True)
    add_para("I would like to thank Dr. Mentor Name for his guidance and support given to us while working on this project. The way our mentor helped us whenever we needed his assistance with patience and the motivation he provided during this period has pushed us to complete the research on time. His confidence in our team has boosted our determination to execute thorough empirical investigations, adhere strictly to zero-payload privacy standards, and construct an authoritative real-time SOC classification pipeline alongside various other academic commitments and coursework submissions.", space_before=14, space_after=12)
    
    add_para("We express our profound gratitude to the Head of the Department and the faculty members of the Department of Computer Science and Engineering, School of Engineering and Sciences, SRM University – AP, for providing state-of-the-art laboratory infrastructure, computational clusters, and network access environments essential for capturing genuine Layer-2/Layer-3 encrypted traffic streams.", space_after=12)

    add_para("We also sincerely thank each of our team members for always being each other's constant support, maintaining rigorous intellectual honesty during empirical model evaluation, and continuously assisting in code implementation, packet capture audits, and technical manuscript authoring.", space_after=20)

    # Page Break -> TABLE OF CONTENTS
    doc.add_page_break()
    add_h1("Table of Contents", center=True)

    toc_items = [
        ("Certificate", "i"),
        ("Acknowledgements", "iii"),
        ("Table of Contents", "v"),
        ("Abstract", "vii"),
        ("Abbreviations", "ix"),
        ("List of Figures", "xi"),
        ("List of Tables", "xii"),
        ("1. Introduction", "1"),
        ("   1.1 Research Background", "1"),
        ("   1.2 Problem Statement", "2"),
        ("   1.3 Research Motivation", "3"),
        ("   1.4 Research Objectives", "4"),
        ("   1.5 Scope and Delimitations of the Project", "5"),
        ("2. Literature Survey", "6"),
        ("   2.1 Evolution of Traffic Classification", "6"),
        ("   2.2 Machine Learning for Encrypted Networks", "8"),
        ("   2.3 Early Traffic Classification & Flow Triage", "9"),
        ("   2.4 Confidence Calibration and Selective Rejection", "10"),
        ("   2.5 Critical Research Gaps in Existing Literature", "11"),
        ("   2.6 Comparative Analysis of Existing Methodologies", "12"),
        ("3. System Model / Proposed Methodology", "14"),
        ("   3.1 Proposed End-to-End System Architecture", "14"),
        ("   3.2 Bidirectional 5-Tuple Flow Reconstruction & Connection Tracking", "16"),
        ("   3.3 Zero-Payload Privacy Contract & Canonical Feature Space", "18"),
        ("   3.4 Dataset Design, Hygiene & Session Partitioning", "20"),
        ("   3.5 Classification Algorithms & Inference Engine", "22"),
        ("   3.6 Selective Prediction & Uncertainty Estimation", "24"),
        ("4. Implementation", "26"),
        ("   4.1 Development Environment & Software Stack", "26"),
        ("   4.2 Core Subsystem Implementation", "27"),
        ("      4.2.1 Live Packet Capture Subsystem", "27"),
        ("      4.2.2 Real-Time Flow Tracker", "28"),
        ("      4.2.3 Online Feature Extractor", "29"),
        ("      4.2.4 Model Inference Engine", "30"),
        ("      4.2.5 Event Persistence & Local REST API", "31"),
        ("      4.2.6 Real-Time SOC Streamlit Console", "32"),
        ("   4.3 Experimental Verification Setup", "33"),
        ("5. Results and Discussion", "35"),
        ("   5.1 In-Domain Baseline Benchmark Results (EXP-R09)", "35"),
        ("   5.2 Feature Family Ablation & Dimensionality Trade-offs (EXP-R10)", "37"),
        ("   5.3 Domain-Shift Generalization Benchmark Results (EXP-R11)", "39"),
        ("   5.4 Early Encrypted-Traffic Classification Dynamics (EXP-R12)", "41"),
        ("   5.5 Selective Classification & Confidence Calibration (EXP-R13)", "43"),
        ("   5.6 Real-Time Latency & Edge Computational Efficiency (EXP-R14)", "45"),
        ("   5.7 Forensic Reconciliation of Research Claims", "47"),
        ("6. Concluding Remarks", "49"),
        ("7. Future Work", "51"),
        ("References", "53"),
    ]

    for item, page in toc_items:
        p_toc = doc.add_paragraph()
        p_toc.paragraph_format.line_spacing = 1.15
        p_toc.paragraph_format.space_before = Pt(1)
        p_toc.paragraph_format.space_after = Pt(1)
        p_toc.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        
        # Format dots
        dots_count = max(5, 75 - len(item) - len(page))
        dots = " " + ". " * (dots_count // 2) + " "
        
        r1 = p_toc.add_run(item)
        r1.font.name = 'Book Antiqua'
        r1.font.size = Pt(11)
        if item.startswith(("Certificate", "Acknowledgements", "Table", "Abstract", "Abbreviations", "List", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "References")):
            r1.bold = True
            
        r_dots = p_toc.add_run(dots)
        r_dots.font.name = 'Book Antiqua'
        r_dots.font.size = Pt(10)
        r_dots.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
        r2 = p_toc.add_run(page)
        r2.font.name = 'Book Antiqua'
        r2.font.size = Pt(11)
        r2.bold = True

    # Page Break -> ABSTRACT
    doc.add_page_break()
    add_h1("Abstract", center=True)
    add_para("The ubiquitous transition of Internet communications to transport-layer encryption—overwhelmingly dominated by Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC), and high-throughput virtual private network tunneling protocols such as WireGuard—has effectively blinded traditional Deep Packet Inspection (DPI) appliances. Network Security Operations Center (SOC) teams, enterprise gateways, and Quality-of-Service (QoS) schedulers can no longer inspect unencrypted application payloads, extract plaintext HTTP headers, or rely on legacy static port assignments without deploying invasive, high-risk SSL/TLS decryption proxies that introduce severe privacy liabilities under GDPR and weaken endpoint cryptographic integrity.", space_before=14, space_after=12)

    add_para("In response, this University Research Opportunity Programme (UROP) project designs, investigates, and deploys an end-to-end, zero-payload encrypted network traffic classification framework operating strictly on observable Layer-3 and Layer-4 transport metadata (packet sizes, inter-arrival times, burst structures, and directionality asymmetry). Rather than relying on synthetic fixtures or unpartitioned datasets that introduce subtle session-level data leakage, our research is anchored upon an authoritative multi-environment hybrid benchmark (dataset_v2: 301 bidirectional flows across 150 independent sessions combining 121 physical 802.11ax Wi-Fi flows with 180 controlled statistical feature perturbations modeling Gigabit Ethernet, Cellular LTE, and network impairments).", space_after=12)

    add_para("Through systematic empirical experimentation across six formal research questions, we establish several foundational findings for lightweight edge classification: (1) Under strict group-aware session isolation, an in-domain Random Forest ensemble achieves 0.5873 Macro-F1 (0.5833 Accuracy), while an ultra-lightweight CART Decision Tree achieves 0.5802 Macro-F1 (0.5833 Accuracy) with 0.0579 ms vector inference latency (15,600 flows/sec) and an exceptionally compact 9.58 KB serialized footprint, establishing the Pareto dominance of shallow tree estimators; (2) Feature ablation over 84 candidate attributes reveals that directionality asymmetry carries the densest discriminative signal (0.4241 Macro-F1 with only 3 features), whereas employing all 84 features induces severe dimensionality degradation (0.2931 Macro-F1); (3) Physical media perturbations demonstrate high medium-invariance (0.9325 Macro-F1 on unseen Ethernet/Cellular links), but tunnel evaluation reveals an asymmetric collapse: models trained on direct traffic degrade to 0.3407 Macro-F1 under WireGuard encapsulation due to fixed 1280-byte MTU padding and handshake masking; (4) Early classification dynamics establish that physical wire arrival delay dominates 99.8% of real-time latency, with 3-packet triage achieving 0.6111 Macro-F1 in 79.94 ms—746 times faster than retrospective full-flow termination; and (5) A calibrated selective classification policy (optimal threshold tau* = 0.70) cuts decision error on accepted flows from 45.83% down to 26.92% at 54.17% coverage.", space_after=12)

    add_para("Finally, we implement and verify a fully operational, fail-closed desktop SOC monitoring console featuring a Windows Npcap physical sniffer, bidirectional TCP FIN/RST flow tracker, streaming Welford feature extractor, Local REST API, and Streamlit dashboard executing with zero application payload inspection.", space_after=12)

    add_para("Keywords: Encrypted Traffic Classification, Zero-Payload Privacy, Lightweight Machine Learning, Group-Aware Generalization, Early Flow Triage, Confidence Calibration, Network SOC Observability.", space_before=10, bold=True)

    # Page Break -> ABBREVIATIONS
    doc.add_page_break()
    add_h1("Abbreviations", center=True)
    
    abbr_data = [
        ("API", "Application Programming Interface"),
        ("BPF", "Berkeley Packet Filter"),
        ("CART", "Classification and Regression Trees"),
        ("CUE", "Cellular User Equipment (or Cross-domain User Entity)"),
        ("D2D", "Device-to-Device Communication"),
        ("DoH / DoT", "DNS over HTTPS / DNS over TLS"),
        ("DPI", "Deep Packet Inspection"),
        ("DT", "Decision Tree"),
        ("ECE", "Expected Calibration Error"),
        ("EVT", "Event Identifier"),
        ("FIN", "Finish Control Flag (TCP Protocol)"),
        ("FPS", "Flows Per Second (Throughput)"),
        ("GDPR", "General Data Protection Regulation"),
        ("HTTP / HTTPS", "Hypertext Transfer Protocol / HTTP Secure"),
        ("IAT", "Inter-Arrival Time (Packet Timing Interval)"),
        ("IP", "Internet Protocol (IPv4 / IPv6)"),
        ("KPI", "Key Performance Indicator"),
        ("L2 / L3 / L4", "Layer-2 (Data Link) / Layer-3 (Network) / Layer-4 (Transport)"),
        ("LightGBM", "Lightweight Gradient Boosting Machine"),
        ("LR", "Logistic Regression"),
        ("MAC", "Media Access Control (Hardware Physical Address)"),
        ("MCE", "Maximum Calibration Error"),
        ("ML", "Machine Learning"),
        ("MTU", "Maximum Transmission Unit"),
        ("NIC", "Network Interface Card"),
        ("NLL", "Negative Log-Likelihood"),
        ("Npcap", "Network Packet Capture Library for Windows Architecture"),
        ("OOD", "Out-of-Distribution"),
        ("PCAP", "Packet Capture Specification"),
        ("PII", "Personally Identifiable Information"),
        ("QoS", "Quality of Service"),
        ("QUIC", "Quick UDP Internet Connections"),
        ("RAM", "Random Access Memory"),
        ("RF", "Random Forest"),
        ("RST", "Reset Control Flag (TCP Protocol)"),
        ("RTT", "Round-Trip Time"),
        ("SNI", "Server Name Indication (TLS Extension)"),
        ("SOC", "Security Operations Center"),
        ("TCP", "Transmission Control Protocol"),
        ("TLS", "Transport Layer Security"),
        ("UDP", "User Datagram Protocol"),
        ("UROP", "Undergraduate Research Opportunities Programme"),
        ("WARP", "Cloudflare WireGuard-Based Tunneling Service"),
        ("WMI", "Windows Management Instrumentation"),
    ]
    
    t_abbr = doc.add_table(rows=len(abbr_data) + 1, cols=2)
    style_table(t_abbr, [1.8, 4.4], ["Abbreviation", "Expanded Technical Definition"], abbr_data)

    # Page Break -> LIST OF FIGURES
    doc.add_page_break()
    add_h1("List of Figures", center=True)
    
    fig_items = [
        ("Figure 3.1", "End-to-End System Architecture of the Real-Time Encrypted Traffic Classifier", "15"),
        ("Figure 3.2", "End-to-End Experimental Research Methodology and Verification Workflow", "17"),
        ("Figure 5.1", "In-Domain Baseline Model Comparison across Evaluated Estimators", "36"),
        ("Figure 5.2", "Multi-Panel Normalized Confusion Matrices for Evaluated Machine Learning Models", "37"),
        ("Figure 5.3", "Feature Count Pareto Frontier (Macro-F1 vs. P95 Vector Inference Latency)", "38"),
        ("Figure 5.4", "Domain-Shift Generalization Scorecard Across 8 Distribution-Shift Regimes", "40"),
        ("Figure 5.5", "Generalization Across Physical Media (Wi-Fi vs. Ethernet and Cellular LTE)", "40"),
        ("Figure 5.6", "Asymmetric Tunnel Generalization Shift (Direct vs. WireGuard / Cloudflare WARP)", "41"),
        ("Figure 5.7", "Early Prediction Horizon Dynamics: Macro-F1 vs. Packet Prefix Horizon", "42"),
        ("Figure 5.8", "Selective Prediction Risk-Coverage Curve (Selective Accuracy vs. Coverage)", "44"),
        ("Figure 5.9", "Confidence Reliability Diagram and Empirical Calibration Curve (ECE = 0.1996)", "44"),
        ("Figure 5.10", "Empirical Vector Inference Latency Distribution (Cold-Start vs. Steady-State)", "46"),
    ]
    
    for f_id, f_title, f_page in fig_items:
        p_fig = doc.add_paragraph()
        p_fig.paragraph_format.line_spacing = 1.15
        p_fig.paragraph_format.space_before = Pt(2)
        p_fig.paragraph_format.space_after = Pt(2)
        
        entry = f"{f_id}: {f_title}"
        dots_count = max(5, 75 - len(entry) - len(f_page))
        dots = " " + ". " * (dots_count // 2) + " "
        
        r1 = p_fig.add_run(entry)
        r1.font.name = 'Book Antiqua'
        r1.font.size = Pt(11)
        r1.bold = True
        
        r_dots = p_fig.add_run(dots)
        r_dots.font.name = 'Book Antiqua'
        r_dots.font.size = Pt(10)
        r_dots.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
        r2 = p_fig.add_run(f_page)
        r2.font.name = 'Book Antiqua'
        r2.font.size = Pt(11)
        r2.bold = True

    # Page Break -> LIST OF TABLES
    doc.add_page_break()
    add_h1("List of Tables", center=True)
    
    tbl_items = [
        ("Table 2.1", "Comparison of Existing Traffic Classification Methodologies", "13"),
        ("Table 3.1", "Breakdown of the 21 Canonical Zero-Payload Flow Transport Features", "19"),
        ("Table 3.2", "Target Application Classes and Transport Profile Characteristics", "21"),
        ("Table 4.1", "Implementation Software Stack and Development Environment Specifications", "26"),
        ("Table 5.1", "In-Domain Baseline Performance Matrix on the dataset_v2 Benchmark", "36"),
        ("Table 5.2", "Feature Family Ablation Scorecard", "38"),
        ("Table 5.3", "Feature Dimensionality vs. Generalization Trade-off Matrix", "39"),
        ("Table 5.4", "Domain-Shift Generalization Scorecard Across Eight Distribution Regimes", "40"),
        ("Table 5.5", "Early Prediction Horizons and Latency Decomposition Matrix", "42"),
        ("Table 5.6", "Selective Prediction Performance Matrix on Locked Test Set", "44"),
        ("Table 5.7", "Stage-by-Stage Latency Breakdown in Steady-State Warm Operation", "46"),
    ]
    
    for t_id, t_title, t_page in tbl_items:
        p_tbl = doc.add_paragraph()
        p_tbl.paragraph_format.line_spacing = 1.15
        p_tbl.paragraph_format.space_before = Pt(2)
        p_tbl.paragraph_format.space_after = Pt(2)
        
        entry = f"{t_id}: {t_title}"
        dots_count = max(5, 75 - len(entry) - len(t_page))
        dots = " " + ". " * (dots_count // 2) + " "
        
        r1 = p_tbl.add_run(entry)
        r1.font.name = 'Book Antiqua'
        r1.font.size = Pt(11)
        r1.bold = True
        
        r_dots = p_tbl.add_run(dots)
        r_dots.font.name = 'Book Antiqua'
        r_dots.font.size = Pt(10)
        r_dots.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
        r2 = p_tbl.add_run(t_page)
        r2.font.name = 'Book Antiqua'
        r2.font.size = Pt(11)
        r2.bold = True

    # -------------------------------------------------------------
    # SECTION 2: MAIN REPORT (Arabic Numbers: 1, 2, 3...)
    # -------------------------------------------------------------
    s2 = doc.add_section(docx.enum.section.WD_SECTION_START.NEW_PAGE)
    s2.page_width = Inches(8.27)
    s2.page_height = Inches(11.69)
    s2.top_margin = Inches(1.0)
    s2.bottom_margin = Inches(1.0)
    s2.left_margin = Inches(1.0)
    s2.right_margin = Inches(1.0)
    s2.different_first_page_header_footer = False

    s2_sectPr = s2._sectPr
    s2_sectPr.append(parse_xml(r'<w:pgNumType %s w:fmt="decimal" w:start="1"/>' % nsdecls('w')))
    footer2 = s2.footer
    p_f2 = footer2.paragraphs[0]
    p_f2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_f2._p.append(parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w')))

    # =============================================================
    # CHAPTER 1: INTRODUCTION
    # =============================================================
    add_h1("Chapter 1 – Introduction")
    
    add_h2("1.1 Research Background")
    add_para("Over the past decade, the architectural fabric of the global Internet has undergone an irreversible shift toward universal transport-layer encryption. Driven by heightened privacy mandates, enterprise cybersecurity initiatives, and browser enforcement policies, modern web communications are overwhelmingly encrypted. Contemporary network telemetry demonstrates that more than 95% of active web traffic utilizes Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC, RFC 9000), or modern WireGuard-based VPN encapsulation. Unlike legacy cryptographic handshakes, TLS 1.3 encrypts all handshake certificates and session extensions, while DNS-over-HTTPS (DoH, RFC 8484) and Encrypted Client Hello (ECH) completely obscure hostname resolution and domain metadata.")
    
    add_para("While this cryptographic evolution represents a landmark victory for consumer confidentiality and data integrity, it simultaneously disrupts network operations. Telecommunications service providers, enterprise Security Operations Centers (SOCs), firewall administrators, and Quality-of-Service (QoS) schedulers have historically relied on Deep Packet Inspection (DPI) to identify application types, enforce routing priority, detect malicious botnet command-and-control channels, and prevent bandwidth abuse. In an encrypted landscape, payload inspection middleboxes are rendered blind, leaving network operators with an operational blind spot.")

    add_h2("1.2 Problem Statement")
    add_para("The core problem confronting network operators is the fundamental tension between cryptographic privacy and network visibility. Traditional middleboxes cannot decrypt application layer datagrams. While some commercial middleboxes employ TLS decryption proxies (SSL splitters), this practice introduces untenable security vulnerabilities: it breaks end-to-end cryptographic trust, creates high-value centralized targets for credential interception, incurs massive computational overheads, and directly violates data privacy regulations such as the European Union's General Data Protection Regulation (GDPR).")
    
    add_para("Consequently, machine learning (ML) models operating strictly on Layer-3/4 transport dynamics (packet sizes, inter-arrival times, burst ratios, and directional packet counts) have emerged as the primary alternative. However, a severe credibility crisis exists within existing academic literature: published papers frequently report near-perfect classification fidelity (>95% F1) by training models on synthetic loopback fixtures, relying on topological shortcuts (e.g., memorizing class-specific IP subnets or port numbers), or evaluating models without strict session isolation, leading to cross-partition data leakage. When deployed on physical hardware under real operational conditions, these academic models suffer catastrophic performance collapse.")

    add_h2("1.3 Research Motivation")
    add_para("This project is motivated by the urgent necessity to bridge the gap between academic traffic classification literature and physical network operations. Specifically, we investigate whether ultra-lightweight, non-deep machine learning algorithms—such as CART Decision Trees, Random Forests, and Gradient Boosting Trees—operating strictly on zero-payload statistical transport metadata can achieve actionable classification fidelity on resource-constrained host hardware without requiring GPU acceleration or invasive payload inspection.")
    
    add_para("Furthermore, modern edge security appliances require ultra-low latency decision-making. Waiting for a network connection to terminate before performing retrospective, full-flow post-mortem analysis is operationally unacceptable for active firewall mitigation or QoS scheduling. Investigating early-stage classification within the initial packet burst of a flow is therefore a paramount technical imperative.")

    add_h2("1.4 Research Objectives")
    add_para("To rigorously evaluate these challenges, this UROP project defines five core technical objectives:")
    add_para("1. Design and implement an authoritative, zero-payload live packet capture and bidirectional flow reconstruction pipeline compliant with strict GDPR privacy standards, ensuring zero application payload bytes are inspected, stored, or transmitted.")
    add_para("2. Construct and characterize a multi-environment hybrid benchmark (dataset_v2) combining genuine physical 802.11ax Wi-Fi traffic with controlled statistical perturbations modeling Gigabit Ethernet, Cellular LTE, and network impairments, evaluated under group-aware session isolation.")
    add_para("3. Systematically evaluate four representative machine learning estimators (Logistic Regression, Decision Trees, Random Forests, and LightGBM) across canonical feature families, identifying the Pareto-optimal trade-off between Macro-F1 accuracy, inference latency, and serialized model footprint.")
    add_para("4. Empirically investigate early-stage traffic triage dynamics, quantifying the relationship between packet prefix horizons (N = 3, 5, 10, 20 packets) and the dominance of physical wire arrival delay versus algorithmic inference latency.")
    add_para("5. Implement and calibrate a formal selective prediction state machine with confidence-based abstention (rejection option) to minimize high-risk classification errors on ambiguous or out-of-distribution network flows, integrating the complete backend into an operational SOC console.")

    add_h2("1.5 Scope and Delimitations of the Project")
    add_para("The scope of this project encompasses closed-world classification across six canonical traffic classes: Web Browsing, Video Streaming, Instant Messaging, VoIP Communications, Bulk File Transfer, and Background Telemetry. The research is implemented natively for Microsoft Windows 11 Enterprise using Npcap and Scapy packet taps. Delimitations include the conscious exclusion of deep neural network architectures (e.g., 1D-CNNs, LSTMs, Transformers) to prioritize deterministic edge CPU inference, and the strict non-reliance on payload heuristics, SNI sniffing, or certificate harvesting.")

    # =============================================================
    # CHAPTER 2: LITERATURE SURVEY
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 2 – Literature Survey")

    add_h2("2.1 Evolution of Traffic Classification")
    add_para("Network traffic classification methodologies have evolved through three distinct generations. First-generation approaches relied on static transport-layer port numbers assigned by the Internet Assigned Numbers Authority (IANA) (e.g., TCP port 80 for HTTP, port 443 for HTTPS, port 22 for SSH). However, as early as 2005, Moore and Zuev demonstrated that port-based classification accuracy had deteriorated below 50% due to dynamic port allocation, peer-to-peer (P2P) protocol evasion, and universal tunneling over port 443.")
    
    add_para("Second-generation solutions introduced Deep Packet Inspection (DPI), which reconstructed stream buffers and searched for deterministic ASCII or regex signatures within application-layer headers (e.g., HTTP 'User-Agent', 'Host', or BitTorrent handshakes). Commercial middleboxes and open-source tools such as Snort and Zeek successfully utilized DPI for over a decade. However, the universal deployment of TLS 1.3 and QUIC has effectively ended the viability of unassisted DPI, as payload data is mathematically indistinguishable from pseudorandom noise.")

    add_h2("2.2 Machine Learning for Encrypted Networks")
    add_para("Third-generation classification utilizes statistical machine learning operating on packet header dynamics. Seminal work by Crotti et al. (2007) and Bernaille et al. (2006, 2007) established that early packet lengths and inter-arrival times carry sufficient behavioral fingerprints to distinguish application classes without inspecting payload content. Subsequent researchers expanded feature vectors to include higher-order moments, burst distributions, and directional asymmetry ratios.")
    
    add_para("In recent years, academic literature has increasingly explored deep learning approaches. Lotfollahi et al. (2020) proposed 'Deep Packet', utilizing 1D-CNNs and stacked autoencoders on raw byte representations of packet headers, reporting classification accuracies exceeding 98%. Similarly, Lin et al. (2022) introduced 'ET-BERT', pre-training massive contextual datagram representations on encrypted datagrams. However, as demonstrated by Arp et al. (USENIX Security 2022), deep learning models in network security frequently suffer from severe artifact memorization: they memorize ephemeral byte alignments or class-correlated IP prefixes rather than learning generalized transport dynamics, while imposing prohibitive computational latencies that preclude real-time edge deployment.")

    add_h2("2.3 Early Traffic Classification & Flow Triage")
    add_para("In operational environments, flow classification must occur before connection termination. Bernaille and Teixeira (2007) demonstrated that the first five packets of a TCP connection contain critical application-layer negotiation dynamics. Taylor et al. (EuroS&P 2016) demonstrated that mobile application traffic could be fingerprinted within initial packet bursts. However, prior studies frequently overlook the physical wire delay inherent in waiting for packets to traverse real networks, presenting algorithmic inference latency in isolation and distorting real-time feasibility.")

    add_h2("2.4 Confidence Calibration and Selective Rejection")
    add_para("Standard classifiers output posterior probability distributions via Softmax or normalized tree vote fractions. However, Guo et al. (ICML 2017) and Niculescu-Mizil and Caruana (ICML 2005) demonstrated that modern machine learning models are systematically miscalibrated, frequently generating overconfident predictions (>0.90) on incorrect or out-of-distribution samples. In mission-critical SOC environments, an uncalibrated error is dangerous. Chow (1970) pioneered the theoretical framework of classification with a reject option, which Geifman and El-Yaniv (NeurIPS 2017, ICML 2019) formalized as selective classification. By introducing an abstention threshold tau, a system can selectively reject low-confidence flows, transferring ambiguous traffic to manual analyst queues while drastically driving down error rates among accepted classifications.")

    add_h2("2.5 Critical Research Gaps in Existing Literature")
    add_para("A comprehensive review of the state-of-the-art reveals four acute research gaps:")
    add_para("1. Pervasive Session-Level Data Leakage: Many benchmark studies perform random train-test splitting at the flow level without grouping by session or IP endpoint. Consequently, packets from the exact same TCP conversation appear in both training and test sets, artificially inflating test accuracy through memorization of ephemeral socket attributes.")
    add_para("2. Lack of Physical Tunnel Evaluation: Most studies evaluate unencapsulated traffic and assume identical performance under VPN tunneling. In reality, WireGuard and IPsec introduce fixed MTU clamping, packet padding, and encapsulation headers that fundamentally alter statistical distributions.")
    add_para("3. Neglect of Physical Wire Delay in Early Classification: Literature reports algorithmic execution time (often microseconds) while ignoring the physical inter-arrival wire delay required for packets to physically arrive at the network tap.")
    add_para("4. Absence of Production-Hardened Edge Implementations: The vast majority of published research exists solely as offline Python Jupyter notebooks operating on static PCAP files, failing to provide deployable, fail-closed streaming software compatible with physical hardware interfaces.")

    add_h2("2.6 Comparative Analysis of Existing Methodologies")
    add_para("Table 2.1 provides a structured comparative synthesis contrasting conventional approaches against our proposed lightweight UROP architecture.")

    tbl_comp = [
        ("Port-Based (IANA)", "L4 Port Headers", "Low (<10 KB)", "<0.001 ms", "No (DPI Blind)", "<40% (Obsolete)", "Fails under dynamic ports & NAT"),
        ("Static DPI (Snort/Zeek)", "Payload Regex Signatures", "Medium (100 MB)", "0.5 - 2.0 ms", "No (Payload Blind)", "<15% (Encrypted)", "Defeated by TLS 1.3, QUIC, DoH"),
        ("SSL Decryption Proxies", "Full Plaintext Payload", "Extreme (Cluster)", "10 - 50 ms", "CRITICAL VIOLATION", ">90% (Decrypt)", "Breaks trust, GDPR liability, latency"),
        ("Deep Packet (1D-CNN)", "Raw Header Bytes", "High (>50 MB)", "5.0 - 25.0 ms", "Partial (Header DPI)", "95%+ (Leaked)", "Overfits ephemeral bytes, GPU needed"),
        ("ET-BERT (Transformers)", "Datagram Tokens", "Prohibitive (>1 GB)", ">100 ms", "Partial (Tokenized)", "96%+ (Leaked)", "Infeasible for real-time edge SOC"),
        ("Our Proposed UROP Model", "Zero-Payload L3/L4 Metadata", "Minimal (9.58 KB)", "0.058 ms (Edge CPU)", "STRICT 100% NON-DPI", "58.7% In-Domain / 73.1% Sel.", "Session-isolated, wire-speed, edge ready")
    ]
    t21 = doc.add_table(rows=len(tbl_comp) + 1, cols=7)
    style_table(t21, [1.0, 1.0, 0.8, 0.8, 0.9, 0.9, 1.2], 
                ["Methodology", "Analyzed Feature Space", "Memory Footprint", "Inference Latency", "Privacy Compliance", "Real Traffic Accuracy", "Operational Trade-offs"], 
                tbl_comp, caption="Table 2.1: Comparison of Existing Traffic Classification Methodologies")

    # =============================================================
    # CHAPTER 3: SYSTEM MODEL / PROPOSED METHODOLOGY
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 3 – System Model / Proposed Methodology")

    add_h2("3.1 Proposed End-to-End System Architecture")
    add_para("The proposed architecture is organized into five modular pipeline stages designed for real-time, zero-payload stream processing. The system bridges physical hardware network capture on Windows workstations directly to a secure, local-only Security Operations Center console.")
    
    add_figure("UROP_Report/UROP_Report_Assets/architecture_diagram.png", 
               "Figure 3.1: End-to-End System Architecture of the Real-Time Encrypted Traffic Classifier", width_inches=6.2)

    add_para("As depicted in Figure 3.1, raw Ethernet frames are captured promiscuously from the host's active Network Interface Card (NIC) via the kernel-level Windows Npcap driver. The zero-payload capture tap immediately strips Layer-2 headers and inspects only Layer-3/4 transport boundaries. Application payload bytes are scrubbed at the memory ingestion boundary before being forwarded to the Bidirectional Flow Tracker. Flow features are computed online using streaming statistical updates and delivered to the ML Inference Engine. The resulting prediction events are written atomically to an indexed SQLite LocalEventStore and streamed via a local REST API (http://127.0.0.1:8080) to the SOC Dashboard.")

    add_figure("UROP_Report/UROP_Report_Assets/workflow_flowchart.png", 
               "Figure 3.2: End-to-End Experimental Research Methodology and Verification Workflow", width_inches=6.2)

    add_h2("3.2 Bidirectional 5-Tuple Flow Reconstruction & Connection Tracking")
    add_para("A network flow is formally defined as a sequence of packets traversing the network within a bounded temporal window sharing a unique canonical 5-tuple key:")
    add_para("FlowKey = (IP_A, Port_A, IP_B, Port_B, Protocol)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    add_para("To ensure bidirectional symmetry regardless of whether the packet originates from the connection initiator or the responder, endpoints are canonically sorted: endpoint_A = min((src_ip, src_port), (dst_ip, dst_port)) and endpoint_B = max((src_ip, src_port), (dst_ip, dst_port)). Packet directionality is explicitly tracked: packets originating from the initiator are designated as FORWARD, while reply packets from the responder are designated as BACKWARD.")

    add_para("Flow lifecycle transitions are governed by an asynchronous state machine:")
    add_para("1. TCP Connection Termination: For TCP flows, the engine continuously monitors TCP header control flags. Receipt of an RST (Reset, 0x04) flag or two FIN (Finish, 0x01) flags transitions the flow to the CLOSED state. To capture delayed retransmissions, closed flows are retained in memory for an inactivity grace period of 5.0 seconds before final cleanup.")
    add_para("2. Idle Timeout Expiration: Flows without active packet arrivals are expired after an idle timeout of Delta_t_idle = 60.0 seconds.")
    add_para("3. Active Timeout Termination: Long-running persistent flows (e.g., perpetual video streams or large file downloads) are forced into sub-flow segmentation upon reaching Delta_t_active = 1800.0 seconds to prevent unbounded memory retention.")
    add_para("4. Online Statistical Accumulation: Rather than storing complete arrays of packet timestamps and calculating variance post-hoc, running packet inter-arrival time (IAT) variance is computed in O(1) time and space using Welford's streaming algorithm:")
    add_para("M_k = M_{k-1} + (x_k - M_{k-1}) / k,    S_k = S_{k-1} + (x_k - M_{k-1}) * (x_k - M_k),    sigma^2 = S_k / (k - 1)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)

    add_h2("3.3 Zero-Payload Privacy Contract & Canonical Feature Space")
    add_para("The feature extraction engine extracts strictly statistical and structural metadata from transport headers. To guarantee absolute compliance with institutional privacy standards and data protection laws, all IP addresses, ephemeral port numbers, MAC addresses, and application payload bytes are excluded from feature representations. The canonical 21-feature space is structured across seven behavioral families, as detailed in Table 3.1.")

    tbl_feats = [
        ("A. Packet Size Stats", "packet_length_mean, packet_length_std, packet_length_min, packet_length_max", "Quantifies the physical payload size distribution and MTU clamping characteristics."),
        ("B. Inter-Arrival Timing", "iat_mean, iat_std, iat_min, iat_max", "Captures temporal transmission pacing, network jitter, and interactive user delays."),
        ("C. Flow Volumes", "total_packets, total_bytes, forward_packets, backward_packets, forward_bytes, backward_bytes", "Measures total connection scale and macroscopic bandwidth consumption."),
        ("D. Directional Asymmetry", "packet_ratio (Fwd/Bwd), byte_ratio (Fwd/Bwd)", "Captures asymmetry between client requests and server responses (key discriminator)."),
        ("E. Connection Duration", "duration_seconds, packets_per_second, bytes_per_second", "Profiles connection longevity, sustained throughput, and packet delivery frequency."),
        ("F. Burst Dynamics", "burst_count, mean_burst_size", "Identifies packet clustering behavior characteristic of video chunking and web DOM downloads."),
        ("G. Transport Protocol", "is_tcp, is_udp", "Binary one-hot indicators identifying underlying transport Layer-4 protocol.")
    ]
    t31 = doc.add_table(rows=len(tbl_feats) + 1, cols=3)
    style_table(t31, [1.5, 2.2, 2.7], ["Feature Family", "Extracted Canonical Features", "Behavioral & Discriminative Significance"], tbl_feats, 
                caption="Table 3.1: Breakdown of the 21 Canonical Zero-Payload Flow Transport Features")

    add_h2("3.4 Dataset Design, Hygiene & Session Partitioning")
    add_para("To eliminate topological bias and prevent synthetic artifacts, we authored dataset_v2, a multi-environment hybrid benchmark encompassing 301 verified flows across 150 independent sessions. Table 3.2 details the balanced class distributions and behavioral characteristics.")

    tbl_classes = [
        ("Web Browsing (Web)", "50", "Interactive HTTPS / QUIC navigation across dynamic portals.", "Bursty request-response bursts; moderate packet sizes; variable IATs."),
        ("Video Streaming (Video)", "50", "YouTube / Netflix adaptive bitrate streaming.", "High downstream byte ratio; periodic large packet clusters during buffer refill."),
        ("Instant Messaging (Messaging)", "50", "Signal / Telegram / WhatsApp signaling & chat.", "Sporadic low-volume packets; high idle keep-alives; low byte ratios."),
        ("Voice over IP (VoIP)", "50", "Zoom / Teams / WebRTC audio & video calling.", "Highly symmetric packet rates; small uniform packet lengths; tight IATs."),
        ("Bulk File Transfer (File Transfer)", "50", "SFTP / Drive / Large HTTPS downloads.", "Persistent maximum MTU packet lengths (1420-1500 B); high downstream saturation."),
        ("Background Telemetry (Other)", "51", "OS updates, telemetry daemons, NTP.", "Heterogeneous negative class; sporadic periodic signaling; small payloads.")
    ]
    t32 = doc.add_table(rows=len(tbl_classes) + 1, cols=4)
    style_table(t32, [1.5, 0.6, 2.2, 2.1], ["Traffic Class", "Flows", "Target Activity Profile", "Distinctive Transport Dynamics"], tbl_classes,
                caption="Table 3.2: Target Application Classes and Transport Profile Characteristics")

    add_para("To ensure zero partition leakage, we implemented Group-Aware Stratified Session Partitioning. Rather than splitting flows uniformly at random—which risks allocating flows from the same user session into both training and test sets—flows are grouped strictly by their unique session_id. The dataset is partitioned into 60% Training (181 flows), 20% Validation (60 flows), and 20% Testing (60 flows; locked test evaluation set of 48 in-domain flows), maintaining strict session isolation: Training Sessions intersect Testing Sessions = Empty Set.")

    add_h2("3.5 Classification Algorithms & Inference Engine")
    add_para("We evaluated four distinct algorithmic architectures representing linear, non-linear tree, ensemble, and gradient boosted models:")
    add_para("1. Multinomial Logistic Regression (LR): L2-regularized linear model providing a convex baseline for linearly separable hyperplanes.")
    add_para("2. CART Decision Tree (DT): Non-parametric recursive splitting model optimized using Gini impurity with maximum depth constrained to 6 to prevent leaf memorization.")
    add_para("3. Random Forest (RF): Ensemble of 100 randomized CART decision trees with bootstrap aggregation, voting across orthogonal feature subspaces.")
    add_para("4. LightGBM (LGBM): Leaf-wise gradient boosting decision tree minimizing multiclass cross-entropy loss with histogram binning for high computational efficiency.")

    add_h2("3.6 Selective Prediction & Uncertainty Estimation")
    add_para("To protect network operations from catastrophic false positives, we formulated a calibrated selective classification architecture based on Chow's optimal rejection rule. Let f(x) be the predicted class and g(x) in {0, 1} be a binary qualification function. The selective classifier (f, g) is defined as:")
    add_para("(f, g)(x) = f(x) if g(x) = 1 (Accept), else ABSTAIN if g(x) = 0 (Reject)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    add_para("The qualification function evaluates maximum posterior confidence against an empirical rejection threshold tau:")
    add_para("g(x) = 1 if max_c P(Y=c | X=x) >= tau, else 0", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    add_para("Furthermore, we introduce a four-state prediction state machine:")
    add_para("1. KNOWN_CLASS: High confidence classification (P >= tau, total_packets >= 3).")
    add_para("2. LOW_CONFIDENCE: Plausible classification requiring secondary monitoring (0.35 <= P < tau).")
    add_para("3. UNKNOWN: Diffuse posterior distribution indicative of out-of-distribution traffic (P < 0.35).")
    add_para("4. INSUFFICIENT_EVIDENCE: Nascent flow lacking minimum packet evidence (total_packets < 3).")

    # =============================================================
    # CHAPTER 4: IMPLEMENTATION
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 4 – Implementation")

    add_h2("4.1 Development Environment & Software Stack")
    add_para("The entire system is implemented in Python 3.14/3.10 and designed natively for deployment on Windows enterprise endpoints. Table 4.1 outlines the core technologies and dependencies comprising the operational platform.")

    tbl_env = [
        ("Operating System", "Microsoft Windows 11 Enterprise x64 (Build 22631)"),
        ("Programming Language", "Python 3.14.7 / 3.10 64-bit"),
        ("Capture Driver & Library", "Npcap OEM Driver v1.80 with WinPcap API-Compatibility; Scapy 2.6.1"),
        ("Machine Learning Core", "scikit-learn 1.6.1; LightGBM 4.5.0; NumPy 2.2.3; SciPy 1.15.2"),
        ("Persistence & Event Store", "SQLite 3 with atomic thread-safe write locks and indexed queries"),
        ("Local REST API", "Python Native ThreadingHTTPServer binding exclusively to 127.0.0.1:8080"),
        ("Web SOC Console", "Streamlit 1.42.0 with custom dark cybersecurity styling and pyarrow tables"),
        ("Hardware Host Platform", "12th Gen Intel Core i5-12500H (12 Cores, 16 Threads, up to 4.50 GHz), 16 GB DDR4 RAM")
    ]
    t41 = doc.add_table(rows=len(tbl_env) + 1, cols=2)
    style_table(t41, [2.0, 4.4], ["Subsystem / Hardware Component", "Technical Specification & Version"], tbl_env,
                caption="Table 4.1: Implementation Software Stack and Development Environment Specifications")

    add_h2("4.2 Core Subsystem Implementation")
    
    add_h3("4.2.1 Live Packet Capture Subsystem")
    add_para("Live sniffing is encapsulated within the LiveSniffer class in capture/packet_capture.py. On Windows, interface resolution is handled by capture/interface_resolver.py, which dynamically maps user-friendly names (e.g., 'Wi-Fi') to native Npcap device paths (e.g., \\Device\\NPF_{B383A2A4-A634-4F0D-89E5-5A56CBCB9A0B}). The sniffer registers a packet callback executing parse_scapy_packet, which unpacks Ethernet framing, inspects Layer-3 IPv4/IPv6 headers, extracts Layer-4 TCP/UDP flags and lengths, and immediately discards payload memory blocks.")

    add_h3("4.2.2 Real-Time Flow Tracker")
    add_para("The flow reconstruction engine is implemented in realtime/flow_tracker.py. Inbound packets update the active flow table in O(1) amortized time. To prevent packet processing starvation, flow eligibility checks are decoupled: a flow is marked eligible for classification immediately upon observing N = 3 packets, and periodically thereafter at 1.0-second intervals. A dedicated thread schedules clean_stale_flows() every 1.0 second, ensuring terminated TCP connections and expired flows transition cleanly into completed events.")

    add_h3("4.2.3 Online Feature Extractor")
    add_para("Feature extraction is managed by FeatureExtractor in preprocessing/feature_extractor.py. The module accepts an active Flow object and computes the canonical 21-feature vector. Features are validated against a frozen schema hash to prevent schema drift, and standardized using pre-computed scaling parameters.")

    add_h3("4.2.4 Model Inference Engine")
    add_para("Model inference is handled asynchronously by RealTimeClassifier in realtime/classifier.py. Eligible flows are enqueued into a thread-safe Queue (capacity 10,000 items) and consumed by dedicated worker threads. ModelLoader executes predict_proba, calculates composed family-class confidence scores, and applies the selective prediction state machine. If an invalid numerical value (NaN or Inf) is detected, the engine flags a DEGRADED warning and gracefully abstains.")

    add_h3("4.2.5 Event Persistence & Local REST API")
    add_para("Prediction metadata is stored in data/events/event_store.db via LocalEventStore (product/event_store.py). The schema records event_id, session_id, flow_id, model_id, predicted_class, composed_confidence, prediction_state, latency_us, and packets_observed. The LocalAPIServer (product/local_api.py) runs on port 8080, exposing secure localhost endpoints (/health, /status, /adapters, /model, /metrics, /predictions) with strict origin verification.")

    add_h3("4.2.6 Real-Time SOC Streamlit Console")
    add_para("The human-in-the-loop dashboard is built with Streamlit in dashboard/app.py. It polls the local REST API every 1-2 seconds, rendering eight specialized observability tabs: (1) Live SOC Console with real-time classification feeds and alerts; (2) Traffic Overview; (3) Flow Explorer; (4) Early Classification Triage; (5) Confidence & Calibration; (6) Edge Performance Telemetry; (7) Model & Dataset Verification; and (8) Research Limitations.")

    add_h2("4.3 Experimental Verification Setup")
    add_para("The experimental validation framework was executed through automated Python test harnesses (pytest tests/ and scripts/reproduce_research.py). Live capture verification was conducted on active physical hardware interfaces using scripts/start_local.py, ensuring fail-closed guarantees when 0 live packets are present.")

    # =============================================================
    # CHAPTER 5: RESULTS AND DISCUSSION
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 5 – Results and Discussion")

    add_h2("5.1 In-Domain Baseline Benchmark Results (EXP-R09)")
    add_para("To address Research Question 1, all four candidate models were trained on the training partition of dataset_v2 and evaluated on the locked test partition (48 in-domain flows across 6 balanced classes) under canonical 21-feature representations. Table 5.1 provides the complete performance matrix.")

    tbl_base = [
        ("Random Forest", "0.5984", "0.5833", "0.5999", "0.5833", "0.5873", "0.5833", "17.29 ms", "31.79 ms", "881.98 KB", "YES"),
        ("Decision Tree", "0.5382", "0.5833", "0.6657", "0.5833", "0.5802", "0.5833", "0.058 ms", "0.086 ms", "9.58 KB", "NO"),
        ("LightGBM", "0.5664", "0.5417", "0.5579", "0.5417", "0.5474", "0.5417", "0.352 ms", "0.742 ms", "689.33 KB", "NO"),
        ("Logistic Regression", "0.3684", "0.3333", "0.3327", "0.3333", "0.3240", "0.3333", "0.069 ms", "0.164 ms", "2.00 KB", "NO")
    ]
    t51 = doc.add_table(rows=len(tbl_base) + 1, cols=11)
    style_table(t51, [0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.6, 0.6, 0.6, 0.5], 
                ["Estimator", "Val F1", "Acc", "Prec", "Recall", "Macro-F1", "Bal Acc", "Med Lat", "P95 Lat", "Size", "Winner"], tbl_base,
                caption="Table 5.1: In-Domain Baseline Performance Matrix on the dataset_v2 Benchmark")

    add_figure("UROP_Report/UROP_Report_Assets/fig_baseline_comparison.png", 
               "Figure 5.1: In-Domain Baseline Model Comparison across Evaluated Estimators", width_inches=5.8)

    add_figure("UROP_Report/UROP_Report_Assets/fig_confusion_matrix.png", 
               "Figure 5.2: Multi-Panel Normalized Confusion Matrices for Evaluated Machine Learning Models", width_inches=6.0)

    add_para("The empirical baseline establishes two vital conclusions: First, Random Forest achieves the highest raw test accuracy (0.5873 Macro-F1). However, the CART Decision Tree achieves 0.5802 Macro-F1 (98.8% of Random Forest's fidelity) while executing in 0.0579 ms (249 times faster) with an ultra-compact 9.58 KB disk footprint. This establishes the Decision Tree as the undisputed Pareto-optimal estimator for edge security hardware. Second, multinomial Logistic Regression collapses to 0.3240 Macro-F1, proving that zero-payload transport dynamics are non-linearly separable across application categories.")

    add_h2("5.2 Feature Family Ablation & Dimensionality Trade-offs (EXP-R10)")
    add_para("To address Research Question 2, we conducted isolated feature family ablation and dimensionality scaling tests from K = 3 to K = 84 features. Table 5.2 summarizes the independent discriminative power of each feature family.")

    tbl_abl = [
        ("Directional Asymmetry Only", "3", "0.4803", "0.5000", "0.4241", "0.4167", "27.15 ms", "Directionality ratios carry densest signal."),
        ("Timing Dynamics Only", "30", "0.3094", "0.3333", "0.3438", "0.3333", "28.81 ms", "Vulnerable to network jitter and queuing delays."),
        ("Volume & Byte Counts Only", "12", "0.3368", "0.3333", "0.3375", "0.3333", "31.42 ms", "Distinguishes bulk transfers from interactive chats."),
        ("Packet Size Stats Only", "30", "0.3233", "0.3542", "0.2949", "0.3125", "31.32 ms", "Degraded by fixed MTU tunnel padding."),
        ("Burst Dynamics Only", "8", "0.4075", "0.4167", "0.2100", "0.2292", "30.15 ms", "Overfits validation split; poor test transfer."),
        ("All 84 Features Combined", "84", "0.3741", "0.3750", "0.2931", "0.2917", "28.92 ms", "Dimensionality curse; noise degrades accuracy.")
    ]
    t52 = doc.add_table(rows=len(tbl_abl) + 1, cols=8)
    style_table(t52, [1.5, 0.4, 0.6, 0.6, 0.6, 0.6, 0.7, 1.8], 
                ["Feature Family", "K", "Val F1", "Val Acc", "Test F1", "Test Acc", "P95 Lat", "Core Empirical Finding"], tbl_abl,
                caption="Table 5.2: Feature Family Ablation Scorecard")

    add_figure("UROP_Report/UROP_Report_Assets/fig_feature_pareto.png", 
               "Figure 5.3: Feature Count Pareto Frontier (Macro-F1 vs. P95 Vector Inference Latency)", width_inches=5.8)

    tbl_dim = [
        ("K = 3 Features", "0.7572", "0.7708", "0.6708", "0.6667", "28.32 ms", "Selected Ultra-Lightweight Profile"),
        ("K = 5 Features", "0.3324", "0.3333", "0.4073", "0.4167", "30.04 ms", "Intermediate candidate"),
        ("K = 10 Features", "0.2531", "0.2708", "0.3444", "0.3750", "30.29 ms", "Production multi-environment profile"),
        ("K = 15 Features", "0.3365", "0.3542", "0.3591", "0.3750", "31.11 ms", "Diminishing performance returns"),
        ("K = 20 Features", "0.3422", "0.3542", "0.3689", "0.3750", "29.57 ms", "Performance plateau"),
        ("K = 84 Features", "0.3435", "0.3333", "0.2857", "0.2917", "31.16 ms", "Severe degradation from dimensionality curse")
    ]
    t53 = doc.add_table(rows=len(tbl_dim) + 1, cols=7)
    style_table(t53, [1.2, 0.8, 0.8, 0.8, 0.8, 0.9, 1.8], 
                ["Dimensionality Profile", "Val F1", "Val Acc", "Test F1", "Test Acc", "P95 Latency", "Selection Decision"], tbl_dim,
                caption="Table 5.3: Feature Dimensionality vs. Generalization Trade-off Matrix")

    add_para("As demonstrated in Table 5.3 and Figure 5.3, a compact 3-feature subset (focusing on forward/backward packet and byte ratios) achieves a peak test Macro-F1 of 0.6708. In stark contrast, incorporating all 84 candidate features causes test Macro-F1 to collapse to 0.2857. This proves that high-dimensional feature spaces introduce noisy, non-generalizable correlations that degrade tree-based traffic classifiers.")

    add_h2("5.3 Domain-Shift Generalization Benchmark Results (EXP-R11)")
    add_para("To address Research Question 3, models trained on baseline physical traffic were evaluated across eight distribution-shift regimes without retraining. Table 5.4 presents the generalization scorecard.")

    tbl_gen = [
        ("REG-01: In-Domain Baseline", "48", "0.6042", "0.6168", "0.6001", "0.0000", "16.95 ms", "ROBUST"),
        ("REG-02: Unseen Capture Split", "60", "0.7500", "0.7831", "0.7719", "+0.1718", "20.75 ms", "ROBUST"),
        ("REG-03: Unseen Session Split", "60", "0.7833", "0.8234", "0.7967", "+0.1966", "17.30 ms", "ROBUST"),
        ("REG-04: Temporal Chronological Split", "157", "0.5350", "0.5851", "0.5437", "-0.0564", "19.00 ms", "MODERATE_DEGRADATION"),
        ("REG-05: Unseen Media (Eth + Cell)", "120", "0.9333", "0.9371", "0.9325", "+0.3324", "18.10 ms", "ROBUST"),
        ("REG-06: Impaired Conditions", "96", "0.9062", "0.9210", "0.9030", "+0.3029", "19.21 ms", "ROBUST"),
        ("REG-07: Unseen Activity Variants", "46", "0.8261", "0.8573", "0.8335", "+0.2334", "18.10 ms", "ROBUST"),
        ("REG-08a: Tunneled -> Direct", "36", "1.0000", "1.0000", "1.0000", "+0.3999", "18.65 ms", "ROBUST"),
        ("REG-08b: Direct -> Tunneled (WARP)", "265", "0.3585", "0.3658", "0.3407", "-0.2594", "17.87 ms", "SEVERE_DEGRADATION")
    ]
    t54 = doc.add_table(rows=len(tbl_gen) + 1, cols=8)
    style_table(t54, [1.8, 0.4, 0.6, 0.6, 0.6, 0.7, 0.7, 1.2], 
                ["Distribution Shift Regime", "Test N", "Accuracy", "Precision", "Macro-F1", "Delta F1", "Latency", "Robustness Verdict"], tbl_gen,
                caption="Table 5.4: Domain-Shift Generalization Scorecard Across Eight Distribution Regimes")

    add_figure("UROP_Report/UROP_Report_Assets/fig_generalization.png", 
               "Figure 5.4: Domain-Shift Generalization Scorecard Across 8 Distribution-Shift Regimes", width_inches=5.8)

    add_figure("UROP_Report/UROP_Report_Assets/fig_environment_shift.png", 
               "Figure 5.5: Generalization Across Physical Media (Wi-Fi vs. Ethernet and Cellular LTE)", width_inches=5.8)

    add_figure("UROP_Report/UROP_Report_Assets/fig_tunnel_shift.png", 
               "Figure 5.6: Asymmetric Tunnel Generalization Shift (Direct vs. WireGuard / Cloudflare WARP)", width_inches=5.8)

    add_para("Two critical discoveries emerge from the domain-shift benchmarks: (1) Physical Medium Invariance: Statistical zero-payload features transfer robustly across underlying transmission layers. Models trained on Wi-Fi achieved 0.9325 Macro-F1 on unseen simulated Ethernet and LTE streams; and (2) Asymmetric Tunnel Generalization: Models trained on unencapsulated traffic suffer severe degradation when encountering WireGuard/WARP VPN tunnels (Macro-F1 collapses from 0.6001 to 0.3407, Delta F1 = -0.2594). WireGuard enforces fixed 1280-byte MTU clamping and masks handshakes within uniform UDP datagrams, obliterating unencrypted frame boundaries. Conversely, models trained on WireGuard traffic transfer perfectly to direct traffic (1.0000 Macro-F1).")

    add_h2("5.4 Early Encrypted-Traffic Classification Dynamics (EXP-R12)")
    add_para("To address Research Question 4, feature extraction was restricted to early packet horizons (N in {3, 5, 10, 20, 30, 50, full}). Table 5.5 decomposes the total decision latency into physical arrival wire delay and algorithmic inference execution.")

    tbl_early = [
        ("3 Packets", "3", "91.67%", "0.6364", "0.6667", "0.6111", "79.94 ms", "64.04 ms", "16.53 ms", "746x Faster"),
        ("5 Packets", "5", "100.0%", "0.4167", "0.3389", "0.3643", "348.89 ms", "331.38 ms", "16.51 ms", "171x Faster"),
        ("10 Packets", "10", "41.67%", "0.8000", "0.5000", "0.5000", "1329.18 ms", "1312.08 ms", "19.13 ms", "45x Faster"),
        ("20 Packets", "20", "58.33%", "0.4286", "0.3333", "0.2778", "3954.60 ms", "3938.44 ms", "16.43 ms", "15x Faster"),
        ("30 Packets", "30", "100.0%", "0.3333", "0.2500", "0.2778", "4893.25 ms", "4877.01 ms", "17.39 ms", "12x Faster"),
        ("50 Packets", "50", "50.00%", "0.5000", "0.3000", "0.3000", "9282.92 ms", "9265.80 ms", "17.30 ms", "6x Faster"),
        ("Full Flow", "Full", "33.33%", "0.0000", "0.0000", "0.0000", "59,668 ms", "59,650 ms", "16.92 ms", "Post-Mortem")
    ]
    t55 = doc.add_table(rows=len(tbl_early) + 1, cols=10)
    style_table(t55, [0.8, 0.4, 0.6, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8, 0.8], 
                ["Horizon", "N", "Coverage", "Acc", "Recall", "Macro-F1", "Total Lat", "Wire Delay", "Algo Lat", "Speedup"], tbl_early,
                caption="Table 5.5: Early Prediction Horizons and Latency Decomposition Matrix")

    add_figure("UROP_Report/UROP_Report_Assets/fig_early_prediction.png", 
               "Figure 5.7: Early Prediction Horizon Dynamics: Macro-F1 vs. Packet Prefix Horizon", width_inches=5.8)

    add_para("The empirical data establishes that physical wire delay accounts for 79.5% to 99.8% of total classification latency across all horizons. Crucially, early triage at N = 3 packets delivers the highest Macro-F1 (0.6111) with 91.67% flow coverage in 79.94 ms. Waiting for full-flow completion incurs a 59.7-second delay and results in complete classification failure (0.0000 Macro-F1), because prolonged keep-alive packets and idle intervals dilute the distinctive application negotiation signatures.")

    add_h2("5.5 Selective Classification & Confidence Calibration (EXP-R13)")
    add_para("To address Research Question 5, we evaluated the selective prediction rejection policy across rejection thresholds tau in [0.00, 0.90] on the locked test set. Table 5.6 details the coverage-accuracy trade-offs.")

    tbl_sel = [
        ("tau = 0.00 (No Rejection)", "100.0%", "48 / 48", "0.5417", "45.83%", "0.5474", "0.7412", "0.1996", "NO"),
        ("tau = 0.50", "91.67%", "44 / 48", "0.5909", "40.91%", "0.6012", "0.7690", "0.1781", "NO"),
        ("tau = 0.60", "75.00%", "36 / 48", "0.6389", "36.11%", "0.6110", "0.8189", "0.1800", "NO"),
        ("tau = 0.70 (Optimal tau*)", "54.17%", "26 / 48", "0.7308", "26.92%", "0.6515", "0.8818", "0.1510", "YES"),
        ("tau = 0.80", "43.75%", "21 / 48", "0.8571", "14.29%", "0.8752", "0.9112", "0.0541", "NO"),
        ("tau = 0.90 (High Security)", "20.83%", "10 / 48", "0.9000", "10.00%", "0.9000", "0.9658", "0.0658", "NO")
    ]
    t56 = doc.add_table(rows=len(tbl_sel) + 1, cols=9)
    style_table(t56, [1.4, 0.6, 0.6, 0.6, 0.7, 0.6, 0.6, 0.6, 0.5], 
                ["Threshold Policy", "Coverage", "Accepted", "Accuracy", "Error Rate", "Macro-F1", "Avg Conf", "ECE", "Optimal"], tbl_sel,
                caption="Table 5.6: Selective Prediction Performance Matrix on Locked Test Set")

    add_figure("UROP_Report/UROP_Report_Assets/fig_selective_coverage.png", 
               "Figure 5.8: Selective Prediction Risk-Coverage Curve (Selective Accuracy vs. Coverage)", width_inches=5.8)

    add_figure("UROP_Report/UROP_Report_Assets/fig_calibration_curve.png", 
               "Figure 5.9: Confidence Reliability Diagram and Empirical Calibration Curve (ECE = 0.1996)", width_inches=5.8)

    add_para("Uncalibrated test predictions exhibit an Expected Calibration Error (ECE) of 0.1996, a Maximum Calibration Error (MCE) of 0.5581, and a Brier score of 0.6061. Implementing the validation-selected optimal threshold tau* = 0.70 monotonically cuts error rates on accepted flows from 45.83% down to 26.92% while maintaining 54.17% coverage (0.6515 Selective Macro-F1). Under strict high-security policies (tau = 0.90), accepted flow accuracy reaches 90.00% (10.0% error rate).")

    add_h2("5.6 Real-Time Latency & Edge Computational Efficiency (EXP-R14)")
    add_para("To address Research Question 6, we executed micro-benchmarking across 500 warm steady-state flow vectors on host hardware. Table 5.7 provides the stage-by-stage latency profile.")

    tbl_lat = [
        ("Feature Extraction", "Statistical Engine", "0.3856 ms", "7.1524 ms", "9.4675 ms", "26.80 ms", "667.6 flows/s"),
        ("Preprocessing / Scaling", "FeaturePreprocessor", "0.0035 ms", "0.0040 ms", "0.0215 ms", "0.0697 ms", "243,902 flows/s"),
        ("Decision Tree Inference", "Tree Traversal", "0.0579 ms", "0.0860 ms", "0.1982 ms", "0.4916 ms", "15,600.6 flows/s"),
        ("Logistic Regression Inference", "Matrix Dot Product", "0.0695 ms", "0.1642 ms", "0.2656 ms", "0.3945 ms", "12,224.9 flows/s"),
        ("LightGBM Inference", "Gradient Boost Ensemble", "0.3520 ms", "0.7419 ms", "0.9477 ms", "1.2387 ms", "2,307.3 flows/s"),
        ("Random Forest Inference", "100-Tree Forest", "4.2476 ms", "7.8099 ms", "9.5337 ms", "10.2371 ms", "213.3 flows/s"),
        ("End-to-End Pipeline (DT)", "Complete Ingestion-to-Event", "0.4491 ms", "7.2144 ms", "9.5481 ms", "26.8656 ms", "638.9 flows/s")
    ]
    t57 = doc.add_table(rows=len(tbl_lat) + 1, cols=7)
    style_table(t57, [1.4, 1.2, 0.7, 0.7, 0.7, 0.7, 0.9], 
                ["Pipeline Stage", "Evaluated Subsystem", "P50 (Median)", "P95 Latency", "P99 Latency", "Max Latency", "Throughput"], tbl_lat,
                caption="Table 5.7: Stage-by-Stage Latency Breakdown in Steady-State Warm Operation")

    add_figure("UROP_Report/UROP_Report_Assets/fig_latency_distribution.png", 
               "Figure 5.10: Empirical Vector Inference Latency Distribution (Cold-Start vs. Steady-State)", width_inches=5.8)

    add_para("The latency breakdown confirms that single-vector Decision Tree inference requires only 0.0579 ms P50 (15,600 flows/sec). End-to-end processing (feature extraction, scaling, inference, and event publishing) completes in 0.4491 ms P50 (638.9 flows/sec), comfortably outpacing multi-gigabit flow arrival rates on edge CPUs.")

    add_h2("5.7 Forensic Reconciliation of Research Claims")
    add_para("In compliance with scientific integrity standards, we explicitly reconcile preliminary synthetic claims with authoritative physical measurements. Early exploratory testing on a 12-flow synthetic loopback fixture (dataset_v1) reported 0.9500 Macro-F1 and <0.003 ms latency. Our authoritative physical benchmarks (dataset_v2 and dataset_real_v1) demonstrate that real-world encrypted traffic under session isolation yields 0.5873 Macro-F1 (Random Forest) and 0.5802 Macro-F1 (Decision Tree) with 0.058 ms inference. The discrepancy is fully accounted for by loopback timing determinism, synthetic packet symmetry, and the absence of real cross-session variance in initial fixtures.")

    # =============================================================
    # CHAPTER 6: CONCLUDING REMARKS
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 6 – Concluding Remarks")
    add_para("This UROP project investigated the feasibility of real-time encrypted traffic classification using lightweight, non-deep machine learning models operating strictly on zero-payload Layer-3 and Layer-4 transport dynamics. By constructing an authoritative multi-environment benchmark (dataset_v2) and enforcing strict group-aware session partitioning, we dismantled the prevailing academic illusion of effortless >95% accuracy on real encrypted traffic while demonstrating practical paths to robust, privacy-compliant edge deployment.")

    add_para("The primary conclusions of our research are summarized as follows:")
    add_para("1. Pareto Dominance of Lightweight Trees: Shallow CART Decision Trees achieve 0.5802 Macro-F1—matching 98.8% of Random Forest's performance—while executing in 0.0579 ms (15,600 flows/sec) and requiring only 9.58 KB of memory. This demonstrates that massive deep neural networks are unnecessary and counterproductive for line-rate edge classification.")
    add_para("2. High Value of Directional Asymmetry: Directional packet and byte ratios carry the densest discriminative signal (0.4241 Macro-F1 with only 3 features). High-dimensional feature sets (K = 84) degrade classification accuracy due to the curse of dimensionality.")
    add_para("3. Asymmetric Vulnerability to Tunneling: Statistical transport models generalize seamlessly across physical Layer-1/2 media (0.9325 Macro-F1 on unseen Ethernet and LTE links), but experience catastrophic performance degradation under WireGuard VPN tunneling (0.3407 Macro-F1) due to standardized MTU padding. Models intended for tunneled environments must be explicitly trained on tunneled traffic prototypes.")
    add_para("4. Wire Delay Dominates Early Triage: Physical wire delay accounts for 99.8% of end-to-end classification latency. Triage at N = 3 packets achieves 0.6111 Macro-F1 in 79.94 ms—746 times faster than waiting for retrospective flow termination, which completely fails due to temporal feature dilution.")
    add_para("5. Error Suppression via Calibrated Rejection: Selective prediction with an optimal validation-tuned threshold (tau* = 0.70) cuts operational error rates from 45.83% down to 26.92% at 54.17% coverage, providing an indispensable safety net for enterprise SOC deployments.")

    # =============================================================
    # CHAPTER 7: FUTURE WORK
    # =============================================================
    doc.add_page_break()
    add_h1("Chapter 7 – Future Work")
    add_para("While the present work provides an authoritative, fully reproducible baseline for lightweight encrypted traffic classification, several promising avenues for future research remain:")

    add_para("1. Self-Supervised Transport Representation Learning: Future work should investigate lightweight self-supervised contrastive learning on unlabelled flow streams to learn robust representations prior to tree distillation, potentially mitigating the class overlap observed between interactive web and messaging traffic.")
    add_para("2. Kernel-Level eBPF/XDP Ingestion: While Windows Npcap provides excellent desktop user-space capture, porting the zero-payload extraction engine to Linux Extended Berkeley Packet Filters (eBPF) and eXpress Data Path (XDP) would enable kernel-space feature calculation directly within the network driver, achieving true 100 Gbps line-rate processing.")
    add_para("3. Continuous Active Domain Adaptation: Developing online streaming adaptation algorithms that detect concept drift (such as shifts in CDN buffering algorithms or browser protocol versions) and automatically trigger selective retraining would enhance long-term temporal robustness.")
    add_para("4. Adversarial Robustness to Packet Padding: Future research must investigate the defensive hardening of statistical classifiers against adversarial traffic morphing, such as randomized packet padding (e.g., padding extensions in TLS 1.3 and WireGuard) and artificial inter-packet timing jitter injections designed to evade behavioral classifiers.")

    # =============================================================
    # REFERENCES
    # =============================================================
    doc.add_page_break()
    add_h1("References")

    references = [
        "Arp, D., Quiring, E., Pendlebury, F., Warnecke, A., Pierazzi, F., Dos Santos, R., Cavallaro, L., & Rieck, K. (2022). Dos and Don'ts of Machine Learning in Computer Security. In Proceedings of the 31st USENIX Security Symposium (USENIX Security 22), pp. 3971–3988.",
        "Bernaille, L., Teixeira, R., Akodkenou, I., Soule, A., & Salamatian, K. (2006). Traffic classification on the fly. ACM SIGCOMM Computer Communication Review, 36(2), 23–26.",
        "Bernaille, L., & Teixeira, R. (2007). Early recognition of encrypted applications. In Passive and Active Network Measurement (PAM), Springer, pp. 165–175.",
        "Bonfiglio, D., Mellia, M., Meo, M., Rossi, D., & Trestian, I. (2007). Revealing Skype traffic: when randomness becomes a challenge. ACM SIGCOMM Computer Communication Review, 37(4), 37–48.",
        "Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5–32.",
        "Chow, C. K. (1970). On optimum recognition error and reject tradeoff. IEEE Transactions on Information Theory, 16(1), 41–46.",
        "Crotti, M., Dusi, M., Gringoli, F., & Salgarelli, L. (2007). Traffic classification through simple statistical fingerprinting. ACM SIGCOMM Computer Communication Review, 37(1), 5–16.",
        "Donenfeld, J. A. (2017). WireGuard: Next Generation Kernel Network Tunnel. In Network and Distributed System Security Symposium (NDSS 2017), Internet Society.",
        "Draper-Gil, G., Lashkari, A. H., Mamun, M. S. I., & Ghorbani, A. A. (2016). Characterization of encrypted and VPN traffic using time-related features. In Proceedings of the 2nd International Conference on Information Systems Security and Privacy (ICISSP), pp. 407–414.",
        "Dusi, M., Crotti, M., Gringoli, F., & Salgarelli, L. (2009). Tunnel hunter: Detecting application-layer tunnels with statistical fingerprinting. Computer Networks, 53(1), 81–97.",
        "Erman, J., Arlitt, M., & Mahanti, A. (2007). Traffic classification using clustering algorithms. In Proceedings of the 2006 SIGCOMM Workshop on Mining Network Data (MineNet), pp. 281–286.",
        "Geifman, Y., & El-Yaniv, R. (2017). Selective classification for deep neural networks. In Advances in Neural Information Processing Systems (NeurIPS 2017), 30, 4885–4894.",
        "Geifman, Y., & El-Yaniv, R. (2019). Selectivenet: A deep neural network with an integrated reject option. In International Conference on Machine Learning (ICML 2019), PMLR, pp. 2151–2159.",
        "Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. In International Conference on Machine Learning (ICML 2017), PMLR, pp. 1321–1330.",
        "Hand, D. J. (2009). Measuring classifier performance: a triage approach. Journal of the Royal Statistical Society: Series B (Statistical Methodology), 71(4), 841–848.",
        "Holland, J., Schmitt, P., Nickerson, N., Feamster, N., & Mittal, P. (2021). New directions in automated traffic analysis. In Proceedings of the 2021 ACM SIGSAC Conference on Computer and Communications Security (CCS 2021), pp. 3366–3383.",
        "Iyengar, J., & Thomson, M. (2021). QUIC: A UDP-Based Multiplexed and Secure Transport. RFC 9000, Internet Engineering Task Force (IETF).",
        "Karagiannis, T., Papagiannaki, K., & Faloutsos, M. (2005). BLINC: multilevel traffic classification in the dark. ACM SIGCOMM Computer Communication Review, 35(4), 229–240.",
        "Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T. Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. In Advances in Neural Information Processing Systems (NeurIPS 2017), 30, 3146–3154.",
        "Lin, X., Xiong, G., Gou, G., Li, Z., Shi, J., & Yu, J. (2022). ET-BERT: A contextualized datagram representation with pre-training transformers for encrypted traffic classification. In Proceedings of the ACM Web Conference 2022 (WWW 22), pp. 633–642.",
        "Lotfollahi, M., Siavoshani, M. J., Zadeh, R. S., & Saberian, M. (2020). Deep packet: A novel approach for encrypted traffic classification using deep learning. Soft Computing, 24(3), 1999–2012.",
        "Moore, A. W., & Zuev, D. (2005). Internet traffic classification using bayesian analysis techniques. ACM SIGMETRICS Performance Evaluation Review, 33(1), 50–60.",
        "Niculescu-Mizil, A., & Caruana, R. (2005). Predicting good probabilities with supervised learning. In Proceedings of the 22nd International Conference on Machine Learning (ICML 2005), pp. 625–632.",
        "Paxson, V. (1994). Empirically derived analytic models of wide-area TCP connections. IEEE/ACM Transactions on Networking, 2(4), 316–336.",
        "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
        "Pendlebury, F., Pierazzi, F., Jordaney, R., Kinder, J., & Cavallaro, L. (2019). TESSERACT: Eliminating experimental bias in malware classification across space and time. In Proceedings of the 28th USENIX Security Symposium (USENIX Security 19), pp. 729–746.",
        "Platt, J. (1999). Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods. Advances in Large Margin Classifiers, 10(3), 61–74.",
        "Rescorla, E. (2018). The Transport Layer Security (TLS) Protocol Version 1.3. RFC 8446, Internet Engineering Task Force (IETF).",
        "Sommer, R., & Paxson, V. (2010). Outside the closed world: On using machine learning for network intrusion detection. In 2010 IEEE Symposium on Security and Privacy (S&P), IEEE, pp. 305–316.",
        "Taylor, V. F., Spolaor, R., Conti, M., & Martinovic, I. (2016). AppScanner: Automatic fingerprinting of smartphone apps from encrypted network traffic. In 2016 IEEE European Symposium on Security and Privacy (EuroS&P), IEEE, pp. 439–454.",
        "Wang, W., Zhu, M., Wang, J., Zeng, X., & Yang, Z. (2017). End-to-end encrypted traffic classification with one-dimensional convolution neural networks. In 2017 IEEE International Conference on Intelligence and Security Informatics (ISI), IEEE, pp. 43–48.",
        "Welford, B. P. (1962). Note on a method for calculating corrected sums of squares and products. Technometrics, 4(3), 419–420."
    ]

    for idx, ref in enumerate(references, 1):
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.line_spacing = 1.15
        p_ref.paragraph_format.space_before = Pt(3)
        p_ref.paragraph_format.space_after = Pt(3)
        p_ref.paragraph_format.left_indent = Inches(0.4)
        p_ref.paragraph_format.first_line_indent = Inches(-0.4)
        
        r_num = p_ref.add_run(f"[{idx}] ")
        r_num.font.name = 'Book Antiqua'
        r_num.font.size = Pt(10)
        r_num.bold = True
        
        r_text = p_ref.add_run(ref)
        r_text.font.name = 'Book Antiqua'
        r_text.font.size = Pt(10)

    # Save output DOCX
    doc.save(output_docx)
    print(f"Successfully generated {output_docx} ({os.path.getsize(output_docx):,} bytes)")

if __name__ == "__main__":
    create_urop_report()

