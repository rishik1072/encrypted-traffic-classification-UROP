"""
High-Fidelity PDF Generator for the complete UROP Final Report.
Matches sample_urop.docx academic presentation, structure, typography, and visual style.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        # Page 1 is Cover Page: No footer/header
        if self._pageNumber == 1:
            return

        # Preliminary pages: Pages 2 to 7 (Certificate, Ack, TOC, Abstract, Abbr, List of Fig, List of Tables)
        # Use Roman numerals
        # Pages >= 8: Main Report: Arabic numerals (1, 2, 3...)
        self.saveState()
        self.setFont("Times-Roman", 10)
        self.setFillColor(colors.HexColor("#334155"))

        if self._pageNumber < 8:
            # Roman numerals: 2->i, 3->iii, 4->v, etc.
            roman_map = {2: "i", 3: "iii", 4: "v", 5: "vii", 6: "ix", 7: "xi"}
            page_text = roman_map.get(self._pageNumber, str(self._pageNumber))
            self.drawRightString(A4[0] - inch, 0.65 * inch, page_text)
        else:
            arabic_page = self._pageNumber - 7
            page_text = str(arabic_page)
            self.drawRightString(A4[0] - inch, 0.65 * inch, page_text)
            # Add thin running header
            self.setFont("Times-Italic", 8.5)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(inch, A4[1] - 0.65 * inch, "SRM University-AP — UROP Project Final Report (CSE)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(inch, A4[1] - 0.72 * inch, A4[0] - inch, A4[1] - 0.72 * inch)

        self.restoreState()


def generate_urop_pdf():
    os.makedirs("UROP_Report", exist_ok=True)
    pdf_path = "UROP_Report/UROP_Final_Report.pdf"

    # Setup document: A4, 1 inch (72 pt) margins
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles matching Book Antiqua / Times serif academic standards
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=14
    )

    cover_body = ParagraphStyle(
        'CoverBody',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4
    )

    cover_bold = ParagraphStyle(
        'CoverBold',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4
    )

    h1_style = ParagraphStyle(
        'ChapterHeading',
        parent=styles['Heading1'],
        fontName='Times-Bold',
        fontSize=15,
        leading=19,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h1_center = ParagraphStyle(
        'ChapterHeadingCenter',
        parent=styles['Heading1'],
        fontName='Times-Bold',
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=12,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=13,
        leading=17,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'SubSectionHeading',
        parent=styles['Heading3'],
        fontName='Times-Bold',
        fontSize=11,
        leading=15,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'AcademicBody',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10.5,
        leading=14.5,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=0,
        spaceAfter=6
    )

    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontName='Times-BoldItalic',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155"),
        spaceBefore=3,
        spaceAfter=10
    )

    toc_item = ParagraphStyle(
        'TOCItem',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0F172A")
    )

    toc_bold = ParagraphStyle(
        'TOCBold',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0F172A")
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A")
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8,
        leading=10.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1E293B")
    )

    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8,
        leading=10.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1E293B")
    )

    ref_style = ParagraphStyle(
        'Reference',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=9,
        leading=12.5,
        alignment=TA_JUSTIFY,
        leftIndent=24,
        firstLineIndent=-24,
        spaceAfter=5
    )

    story = []

    # -------------------------------------------------------------
    # 1. COVER PAGE (Page 1)
    # -------------------------------------------------------------
    story.append(Spacer(1, 15))
    story.append(Paragraph("REAL-TIME ENCRYPTED TRAFFIC CLASSIFICATION USING LIGHTWEIGHT MACHINE LEARNING MODELS", title_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("UROP Project submitted to the", cover_body))
    story.append(Paragraph("SRM University – AP, Andhra Pradesh", cover_bold))
    story.append(Paragraph("for the partial fulfillment of the requirements to award the degree of", cover_body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Bachelor of Technology<br/>in", cover_bold))
    story.append(Paragraph("Computer Science and Engineering", cover_bold))
    story.append(Paragraph("School of Engineering and Sciences", cover_bold))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Submitted by", cover_body))
    story.append(Paragraph("Student Name | AP21110010489<br/>Student Name | AP21110010488<br/>Student Name | AP21110010490", cover_bold))
    story.append(Spacer(1, 12))

    logo_path = "UROP_Report/UROP_Report_Assets/srm_logo.png"
    if os.path.exists(logo_path):
        story.append(Image(logo_path, width=1.65*inch, height=1.65*inch))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Under the Guidance of", cover_body))
    story.append(Paragraph("Dr. Mentor Name", cover_bold))
    story.append(Paragraph("SRM University–AP<br/>Neerukonda, Mangalagiri,<br/>Guntur Andhra Pradesh – 522 240", cover_bold))
    story.append(Spacer(1, 10))
    story.append(Paragraph("November, 2026", cover_bold))
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 2. CERTIFICATE (Page i)
    # -------------------------------------------------------------
    story.append(Paragraph("Certificate", h1_center))
    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "This is to certify that the project report entitled <b>\"REAL-TIME ENCRYPTED TRAFFIC CLASSIFICATION USING LIGHTWEIGHT MACHINE LEARNING MODELS\"</b> submitted by Student Name (Reg. No: AP21110010489), Student Name (Reg. No: AP21110010488), and Student Name (Reg. No: AP21110010490) to SRM University – AP, Andhra Pradesh, for the partial fulfillment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering is a bona fide record of research work carried out by them under my supervision and guidance.",
        body_style
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "The results embodied in this report have not been submitted to any other University or Institute for the award of any degree or diploma. The research satisfies all ethical, institutional, and technical standards established by the School of Engineering and Sciences.",
        body_style
    ))
    story.append(Spacer(1, 60))

    sig_data = [
        [
            Paragraph("______________________________<br/><b>Dr. Mentor Name</b><br/>Faculty Mentor / Supervisor<br/>Assistant Professor, Dept of CSE<br/>School of Engineering and Sciences<br/>SRM University – AP", cover_body),
            Paragraph("______________________________<br/><b>Head of the Department</b><br/>Dept of Computer Science & Engineering<br/>School of Engineering and Sciences<br/>SRM University – AP", cover_body)
        ]
    ]
    t_sig = Table(sig_data, colWidths=[3.1*inch, 3.1*inch])
    t_sig.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(t_sig)
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 3. ACKNOWLEDGEMENTS (Page iii)
    # -------------------------------------------------------------
    story.append(Paragraph("Acknowledgements", h1_center))
    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "I would like to thank Dr. Mentor Name for his guidance and support given to us while working on this project. The way our mentor helped us whenever we needed his assistance with patience and the motivation he provided during this period has pushed us to complete the research on time. His confidence in our team has boosted our determination to execute thorough empirical investigations, adhere strictly to zero-payload privacy standards, and construct an authoritative real-time SOC classification pipeline alongside various other academic commitments and coursework submissions.",
        body_style
    ))
    story.append(Paragraph(
        "We express our profound gratitude to the Head of the Department and the faculty members of the Department of Computer Science and Engineering, School of Engineering and Sciences, SRM University – AP, for providing state-of-the-art laboratory infrastructure, computational clusters, and network access environments essential for capturing genuine Layer-2/Layer-3 encrypted traffic streams.",
        body_style
    ))
    story.append(Paragraph(
        "We also sincerely thank each of our team members for always being each other's constant support, maintaining rigorous intellectual honesty during empirical model evaluation, and continuously assisting in code implementation, packet capture audits, and technical manuscript authoring.",
        body_style
    ))
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 4. TABLE OF CONTENTS (Page v)
    # -------------------------------------------------------------
    story.append(Paragraph("Table of Contents", h1_center))
    story.append(Spacer(1, 10))

    toc_items = [
        ("Certificate", "i", True),
        ("Acknowledgements", "iii", True),
        ("Table of Contents", "v", True),
        ("Abstract", "vii", True),
        ("Abbreviations", "ix", True),
        ("List of Figures", "xi", True),
        ("List of Tables", "xii", True),
        ("1. Introduction", "1", True),
        ("   1.1 Research Background", "1", False),
        ("   1.2 Problem Statement", "2", False),
        ("   1.3 Research Motivation", "3", False),
        ("   1.4 Research Objectives", "4", False),
        ("   1.5 Scope and Delimitations of the Project", "5", False),
        ("2. Literature Survey", "6", True),
        ("   2.1 Evolution of Traffic Classification", "6", False),
        ("   2.2 Machine Learning for Encrypted Networks", "8", False),
        ("   2.3 Early Traffic Classification & Flow Triage", "9", False),
        ("   2.4 Confidence Calibration and Selective Rejection", "10", False),
        ("   2.5 Critical Research Gaps in Existing Literature", "11", False),
        ("   2.6 Comparative Analysis of Existing Methodologies", "12", False),
        ("3. System Model / Proposed Methodology", "14", True),
        ("   3.1 Proposed End-to-End System Architecture", "14", False),
        ("   3.2 Bidirectional Flow Reconstruction & Connection Tracking", "16", False),
        ("   3.3 Zero-Payload Privacy Contract & Canonical Feature Space", "18", False),
        ("   3.4 Dataset Design, Hygiene & Session Partitioning", "20", False),
        ("   3.5 Classification Algorithms & Inference Engine", "22", False),
        ("   3.6 Selective Prediction & Uncertainty Estimation", "24", False),
        ("4. Implementation", "26", True),
        ("   4.1 Development Environment & Software Stack", "26", False),
        ("   4.2 Core Subsystem Implementation", "27", False),
        ("   4.3 Experimental Verification Setup", "33", False),
        ("5. Results and Discussion", "35", True),
        ("   5.1 In-Domain Baseline Benchmark Results (EXP-R09)", "35", False),
        ("   5.2 Feature Family Ablation & Dimensionality Trade-offs (EXP-R10)", "37", False),
        ("   5.3 Domain-Shift Generalization Benchmark Results (EXP-R11)", "39", False),
        ("   5.4 Early Encrypted-Traffic Classification Dynamics (EXP-R12)", "41", False),
        ("   5.5 Selective Classification & Confidence Calibration (EXP-R13)", "43", False),
        ("   5.6 Real-Time Latency & Edge Computational Efficiency (EXP-R14)", "45", False),
        ("   5.7 Forensic Reconciliation of Research Claims", "47", False),
        ("6. Concluding Remarks", "49", True),
        ("7. Future Work", "51", True),
        ("References", "53", True),
    ]

    toc_rows = []
    for title, pg, is_b in toc_items:
        style_use = toc_bold if is_b else toc_item
        p_t = Paragraph(title, style_use)
        p_p = Paragraph(f"<b>{pg}</b>" if is_b else pg, ParagraphStyle('TOCPage', parent=style_use, alignment=TA_RIGHT))
        dots = ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . ."
        p_d = Paragraph(f"<font color='#94A3B8'>{dots}</font>", ParagraphStyle('TOCDots', parent=style_use, alignment=TA_CENTER))
        toc_rows.append([p_t, p_d, p_p])

    t_toc = Table(toc_rows, colWidths=[3.2*inch, 2.5*inch, 0.5*inch])
    t_toc.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_toc)
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 5. ABSTRACT (Page vii)
    # -------------------------------------------------------------
    story.append(Paragraph("Abstract", h1_center))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "The ubiquitous transition of Internet communications to transport-layer encryption—overwhelmingly dominated by Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC), and high-throughput virtual private network tunneling protocols such as WireGuard—has effectively blinded traditional Deep Packet Inspection (DPI) appliances. Network Security Operations Center (SOC) teams, enterprise gateways, and Quality-of-Service (QoS) schedulers can no longer inspect unencrypted application payloads, extract plaintext HTTP headers, or rely on legacy static port assignments without deploying invasive, high-risk SSL/TLS decryption proxies that introduce severe privacy liabilities under GDPR and weaken endpoint cryptographic integrity.",
        body_style
    ))
    story.append(Paragraph(
        "In response, this University Research Opportunity Programme (UROP) project designs, investigates, and deploys an end-to-end, zero-payload encrypted network traffic classification framework operating strictly on observable Layer-3 and Layer-4 transport metadata (packet sizes, inter-arrival times, burst structures, and directionality asymmetry). Rather than relying on synthetic fixtures or unpartitioned datasets that introduce subtle session-level data leakage, our research is anchored upon an authoritative multi-environment hybrid benchmark (dataset_v2: 301 bidirectional flows across 150 independent sessions combining 121 physical 802.11ax Wi-Fi flows with 180 controlled statistical feature perturbations modeling Gigabit Ethernet, Cellular LTE, and network impairments).",
        body_style
    ))
    story.append(Paragraph(
        "Through systematic empirical experimentation across six formal research questions, we establish several foundational findings for lightweight edge classification: (1) Under strict group-aware session isolation, an in-domain Random Forest ensemble achieves 0.5873 Macro-F1 (0.5833 Accuracy), while an ultra-lightweight CART Decision Tree achieves 0.5802 Macro-F1 (0.5833 Accuracy) with 0.0579 ms vector inference latency (15,600 flows/sec) and an exceptionally compact 9.58 KB serialized footprint, establishing the Pareto dominance of shallow tree estimators; (2) Feature ablation over 84 candidate attributes reveals that directionality asymmetry carries the densest discriminative signal (0.4241 Macro-F1 with only 3 features), whereas employing all 84 features induces severe dimensionality degradation (0.2931 Macro-F1); (3) Physical media perturbations demonstrate high medium-invariance (0.9325 Macro-F1 on unseen Ethernet/Cellular links), but tunnel evaluation reveals an asymmetric collapse: models trained on direct traffic degrade to 0.3407 Macro-F1 under WireGuard encapsulation due to fixed 1280-byte MTU padding and handshake masking; (4) Early classification dynamics establish that physical wire arrival delay dominates 99.8% of real-time latency, with 3-packet triage achieving 0.6111 Macro-F1 in 79.94 ms—746 times faster than retrospective full-flow termination; and (5) A calibrated selective classification policy (optimal threshold tau* = 0.70) cuts decision error on accepted flows from 45.83% down to 26.92% at 54.17% coverage.",
        body_style
    ))
    story.append(Paragraph(
        "Finally, we implement and verify a fully operational, fail-closed desktop SOC monitoring console featuring a Windows Npcap physical sniffer, bidirectional TCP FIN/RST flow tracker, streaming Welford feature extractor, Local REST API, and Streamlit dashboard executing with zero application payload inspection.",
        body_style
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Keywords:</b> Encrypted Traffic Classification, Zero-Payload Privacy, Lightweight Machine Learning, Group-Aware Generalization, Early Flow Triage, Confidence Calibration, Network SOC Observability.",
        body_style
    ))
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 6. ABBREVIATIONS (Page ix)
    # -------------------------------------------------------------
    story.append(Paragraph("Abbreviations", h1_center))
    story.append(Spacer(1, 10))

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

    t_abbr_rows = [[Paragraph(f"<b>{a}</b>", table_cell), Paragraph(d, table_cell)] for a, d in abbr_data]
    t_abbr_pdf = Table([[Paragraph("<b>Abbreviation</b>", table_header), Paragraph("<b>Expanded Definition</b>", table_header)]] + t_abbr_rows, colWidths=[1.8*inch, 4.4*inch])
    t_abbr_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_abbr_pdf)
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 7. LIST OF FIGURES & LIST OF TABLES (Page xi)
    # -------------------------------------------------------------
    story.append(Paragraph("List of Figures", h1_center))
    story.append(Spacer(1, 8))
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
    f_rows = []
    for f_id, f_t, f_pg in fig_items:
        p_t = Paragraph(f"<b>{f_id}:</b> {f_t}", toc_item)
        p_p = Paragraph(f"<b>{f_pg}</b>", ParagraphStyle('FPg', parent=toc_item, alignment=TA_RIGHT))
        dots = ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . ."
        p_d = Paragraph(f"<font color='#94A3B8'>{dots}</font>", ParagraphStyle('FDots', parent=toc_item, alignment=TA_CENTER))
        f_rows.append([p_t, p_d, p_p])

    t_f = Table(f_rows, colWidths=[3.2*inch, 2.5*inch, 0.5*inch])
    t_f.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 1.5), ('TOPPADDING', (0,0), (-1,-1), 1.5)]))
    story.append(t_f)

    story.append(Spacer(1, 14))
    story.append(Paragraph("List of Tables", h1_center))
    story.append(Spacer(1, 8))
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
    t_rows = []
    for t_id, t_t, t_pg in tbl_items:
        p_t = Paragraph(f"<b>{t_id}:</b> {t_t}", toc_item)
        p_p = Paragraph(f"<b>{t_pg}</b>", ParagraphStyle('TPg', parent=toc_item, alignment=TA_RIGHT))
        dots = ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . ."
        p_d = Paragraph(f"<font color='#94A3B8'>{dots}</font>", ParagraphStyle('TDots', parent=toc_item, alignment=TA_CENTER))
        t_rows.append([p_t, p_d, p_p])

    t_t = Table(t_rows, colWidths=[3.2*inch, 2.5*inch, 0.5*inch])
    t_t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 1.5), ('TOPPADDING', (0,0), (-1,-1), 1.5)]))
    story.append(t_t)
    story.append(PageBreak())

    # -------------------------------------------------------------
    # 8. CHAPTER 1: INTRODUCTION (Page 1)
    # -------------------------------------------------------------
    story.append(Paragraph("Chapter 1 – Introduction", h1_style))
    story.append(Paragraph("1.1 Research Background", h2_style))
    story.append(Paragraph(
        "Over the past decade, the architectural fabric of the global Internet has undergone an irreversible shift toward universal transport-layer encryption. Driven by heightened privacy mandates, enterprise cybersecurity initiatives, and browser enforcement policies, modern web communications are overwhelmingly encrypted. Contemporary network telemetry demonstrates that more than 95% of active web traffic utilizes Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC, RFC 9000), or modern WireGuard-based VPN encapsulation. Unlike legacy cryptographic handshakes, TLS 1.3 encrypts all handshake certificates and session extensions, while DNS-over-HTTPS (DoH, RFC 8484) and Encrypted Client Hello (ECH) completely obscure hostname resolution and domain metadata.",
        body_style
    ))
    story.append(Paragraph(
        "While this cryptographic evolution represents a landmark victory for consumer confidentiality and data integrity, it simultaneously disrupts network operations. Telecommunications service providers, enterprise Security Operations Centers (SOCs), firewall administrators, and Quality-of-Service (QoS) schedulers have historically relied on Deep Packet Inspection (DPI) to identify application types, enforce routing priority, detect malicious botnet command-and-control channels, and prevent bandwidth abuse. In an encrypted landscape, payload inspection middleboxes are rendered blind, leaving network operators with an operational blind spot.",
        body_style
    ))

    story.append(Paragraph("1.2 Problem Statement", h2_style))
    story.append(Paragraph(
        "The core problem confronting network operators is the fundamental tension between cryptographic privacy and network visibility. Traditional middleboxes cannot decrypt application layer datagrams. While some commercial middleboxes employ TLS decryption proxies (SSL splitters), this practice introduces untenable security vulnerabilities: it breaks end-to-end cryptographic trust, creates high-value centralized targets for credential interception, incurs massive computational overheads, and directly violates data privacy regulations such as the European Union's General Data Protection Regulation (GDPR).",
        body_style
    ))
    story.append(Paragraph(
        "Consequently, machine learning (ML) models operating strictly on Layer-3/4 transport dynamics (packet sizes, inter-arrival times, burst ratios, and directional packet counts) have emerged as the primary alternative. However, a severe credibility crisis exists within existing academic literature: published papers frequently report near-perfect classification fidelity (>95% F1) by training models on synthetic loopback fixtures, relying on topological shortcuts (e.g., memorizing class-specific IP subnets or port numbers), or evaluating models without strict session isolation, leading to cross-partition data leakage. When deployed on physical hardware under real operational conditions, these academic models suffer catastrophic performance collapse.",
        body_style
    ))

    story.append(Paragraph("1.3 Research Motivation", h2_style))
    story.append(Paragraph(
        "This project is motivated by the urgent necessity to bridge the gap between academic traffic classification literature and physical network operations. Specifically, we investigate whether ultra-lightweight, non-deep machine learning algorithms—such as CART Decision Trees, Random Forests, and Gradient Boosting Trees—operating strictly on zero-payload statistical transport metadata can achieve actionable classification fidelity on resource-constrained host hardware without requiring GPU acceleration or invasive payload inspection.",
        body_style
    ))
    story.append(Paragraph(
        "Furthermore, modern edge security appliances require ultra-low latency decision-making. Waiting for a network connection to terminate before performing retrospective, full-flow post-mortem analysis is operationally unacceptable for active firewall mitigation or QoS scheduling. Investigating early-stage classification within the initial packet burst of a flow is therefore a paramount technical imperative.",
        body_style
    ))

    story.append(Paragraph("1.4 Research Objectives", h2_style))
    story.append(Paragraph("To rigorously evaluate these challenges, this UROP project defines five core technical objectives:", body_style))
    story.append(Paragraph("1. Design and implement an authoritative, zero-payload live packet capture and bidirectional flow reconstruction pipeline compliant with strict GDPR privacy standards, ensuring zero application payload bytes are inspected, stored, or transmitted.", body_style))
    story.append(Paragraph("2. Construct and characterize a multi-environment hybrid benchmark (dataset_v2) combining genuine physical 802.11ax Wi-Fi traffic with controlled statistical perturbations modeling Gigabit Ethernet, Cellular LTE, and network impairments, evaluated under group-aware session isolation.", body_style))
    story.append(Paragraph("3. Systematically evaluate four representative machine learning estimators (Logistic Regression, Decision Trees, Random Forests, and LightGBM) across canonical feature families, identifying the Pareto-optimal trade-off between Macro-F1 accuracy, inference latency, and serialized model footprint.", body_style))
    story.append(Paragraph("4. Empirically investigate early-stage traffic triage dynamics, quantifying the relationship between packet prefix horizons (N = 3, 5, 10, 20 packets) and the dominance of physical wire arrival delay versus algorithmic inference latency.", body_style))
    story.append(Paragraph("5. Implement and calibrate a formal selective prediction state machine with confidence-based abstention (rejection option) to minimize high-risk classification errors on ambiguous or out-of-distribution network flows, integrating the complete backend into an operational SOC console.", body_style))

    story.append(Paragraph("1.5 Scope and Delimitations of the Project", h2_style))
    story.append(Paragraph(
        "The scope of this project encompasses closed-world classification across six canonical traffic classes: Web Browsing, Video Streaming, Instant Messaging, VoIP Communications, Bulk File Transfer, and Background Telemetry. The research is implemented natively for Microsoft Windows 11 Enterprise using Npcap and Scapy packet taps. Delimitations include the conscious exclusion of deep neural network architectures (e.g., 1D-CNNs, LSTMs, Transformers) to prioritize deterministic edge CPU inference, and the strict non-reliance on payload heuristics, SNI sniffing, or certificate harvesting.",
        body_style
    ))

    # -------------------------------------------------------------
    # 9. CHAPTER 2: LITERATURE SURVEY
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 2 – Literature Survey", h1_style))
    story.append(Paragraph("2.1 Evolution of Traffic Classification", h2_style))
    story.append(Paragraph(
        "Network traffic classification methodologies have evolved through three distinct generations. First-generation approaches relied on static transport-layer port numbers assigned by the Internet Assigned Numbers Authority (IANA) (e.g., TCP port 80 for HTTP, port 443 for HTTPS, port 22 for SSH). However, as early as 2005, Moore and Zuev demonstrated that port-based classification accuracy had deteriorated below 50% due to dynamic port allocation, peer-to-peer (P2P) protocol evasion, and universal tunneling over port 443.",
        body_style
    ))
    story.append(Paragraph(
        "Second-generation solutions introduced Deep Packet Inspection (DPI), which reconstructed stream buffers and searched for deterministic ASCII or regex signatures within application-layer headers (e.g., HTTP 'User-Agent', 'Host', or BitTorrent handshakes). Commercial middleboxes and open-source tools such as Snort and Zeek successfully utilized DPI for over a decade. However, the universal deployment of TLS 1.3 and QUIC has effectively ended the viability of unassisted DPI, as payload data is mathematically indistinguishable from pseudorandom noise.",
        body_style
    ))

    story.append(Paragraph("2.2 Machine Learning for Encrypted Networks", h2_style))
    story.append(Paragraph(
        "Third-generation classification utilizes statistical machine learning operating on packet header dynamics. Seminal work by Crotti et al. (2007) and Bernaille et al. (2006, 2007) established that early packet lengths and inter-arrival times carry sufficient behavioral fingerprints to distinguish application classes without inspecting payload content. Subsequent researchers expanded feature vectors to include higher-order moments, burst distributions, and directional asymmetry ratios.",
        body_style
    ))
    story.append(Paragraph(
        "In recent years, academic literature has increasingly explored deep learning approaches. Lotfollahi et al. (2020) proposed 'Deep Packet', utilizing 1D-CNNs and stacked autoencoders on raw byte representations of packet headers, reporting classification accuracies exceeding 98%. Similarly, Lin et al. (2022) introduced 'ET-BERT', pre-training massive contextual datagram representations on encrypted datagrams. However, as demonstrated by Arp et al. (USENIX Security 2022), deep learning models in network security frequently suffer from severe artifact memorization: they memorize ephemeral byte alignments or class-correlated IP prefixes rather than learning generalized transport dynamics, while imposing prohibitive computational latencies that preclude real-time edge deployment.",
        body_style
    ))

    story.append(Paragraph("2.3 Early Traffic Classification & Flow Triage", h2_style))
    story.append(Paragraph(
        "In operational environments, flow classification must occur before connection termination. Bernaille and Teixeira (2007) demonstrated that the first five packets of a TCP connection contain critical application-layer negotiation dynamics. Taylor et al. (EuroS&P 2016) demonstrated that mobile application traffic could be fingerprinted within initial packet bursts. However, prior studies frequently overlook the physical wire delay inherent in waiting for packets to traverse real networks, presenting algorithmic inference latency in isolation and distorting real-time feasibility.",
        body_style
    ))

    story.append(Paragraph("2.4 Confidence Calibration and Selective Rejection", h2_style))
    story.append(Paragraph(
        "Standard classifiers output posterior probability distributions via Softmax or normalized tree vote fractions. However, Guo et al. (ICML 2017) and Niculescu-Mizil and Caruana (ICML 2005) demonstrated that modern machine learning models are systematically miscalibrated, frequently generating overconfident predictions (>0.90) on incorrect or out-of-distribution samples. In mission-critical SOC environments, an uncalibrated error is dangerous. Chow (1970) pioneered the theoretical framework of classification with a reject option, which Geifman and El-Yaniv (NeurIPS 2017, ICML 2019) formalized as selective classification. By introducing an abstention threshold tau, a system can selectively reject low-confidence flows, transferring ambiguous traffic to manual analyst queues while drastically driving down error rates among accepted classifications.",
        body_style
    ))

    story.append(Paragraph("2.5 Critical Research Gaps in Existing Literature", h2_style))
    story.append(Paragraph("A comprehensive review of the state-of-the-art reveals four acute research gaps:", body_style))
    story.append(Paragraph("1. Pervasive Session-Level Data Leakage: Many benchmark studies perform random train-test splitting at the flow level without grouping by session or IP endpoint. Consequently, packets from the exact same TCP conversation appear in both training and test sets, artificially inflating test accuracy through memorization of ephemeral socket attributes.", body_style))
    story.append(Paragraph("2. Lack of Physical Tunnel Evaluation: Most studies evaluate unencapsulated traffic and assume identical performance under VPN tunneling. In reality, WireGuard and IPsec introduce fixed MTU clamping, packet padding, and encapsulation headers that fundamentally alter statistical distributions.", body_style))
    story.append(Paragraph("3. Neglect of Physical Wire Delay in Early Classification: Literature reports algorithmic execution time (often microseconds) while ignoring the physical inter-arrival wire delay required for packets to physically arrive at the network tap.", body_style))
    story.append(Paragraph("4. Absence of Production-Hardened Edge Implementations: The vast majority of published research exists solely as offline Python Jupyter notebooks operating on static PCAP files, failing to provide deployable, fail-closed streaming software compatible with physical hardware interfaces.", body_style))

    story.append(Paragraph("2.6 Comparative Analysis of Existing Methodologies", h2_style))
    story.append(Paragraph("Table 2.1 provides a structured comparative synthesis contrasting conventional approaches against our proposed lightweight UROP architecture.", body_style))

    tbl_comp = [
        ("Port-Based (IANA)", "L4 Port Headers", "Low (<10 KB)", "<0.001 ms", "No (DPI Blind)", "<40% (Obsolete)", "Fails under dynamic ports & NAT"),
        ("Static DPI (Snort/Zeek)", "Payload Regex", "Medium (100 MB)", "0.5 - 2.0 ms", "No (Payload Blind)", "<15% (Encrypted)", "Defeated by TLS 1.3, QUIC, DoH"),
        ("SSL Decryption Proxies", "Full Plaintext", "Extreme (Cluster)", "10 - 50 ms", "CRITICAL VIOLATION", ">90% (Decrypt)", "Breaks trust, GDPR liability, latency"),
        ("Deep Packet (1D-CNN)", "Header Bytes", "High (>50 MB)", "5.0 - 25.0 ms", "Partial (Header DPI)", "95%+ (Leaked)", "Overfits ephemeral bytes, GPU needed"),
        ("ET-BERT (Transformers)", "Datagram Tokens", "Prohibitive (>1 GB)", ">100 ms", "Partial (Tokenized)", "96%+ (Leaked)", "Infeasible for real-time edge SOC"),
        ("Our Proposed UROP Model", "Zero-Payload L3/L4", "Minimal (9.58 KB)", "0.058 ms (Edge CPU)", "STRICT 100% NON-DPI", "58.7% In-Dom / 73.1% Sel.", "Session-isolated, wire-speed, edge ready")
    ]
    t21_rows = [[Paragraph(f"<b>{m}</b>", table_cell), Paragraph(f, table_cell), Paragraph(mem, table_cell_center), Paragraph(lat, table_cell_center), Paragraph(prv, table_cell_center), Paragraph(acc, table_cell_center), Paragraph(trd, table_cell)] for m, f, mem, lat, prv, acc, trd in tbl_comp]
    t21_pdf = Table([[Paragraph("<b>Methodology</b>", table_header), Paragraph("<b>Feature Space</b>", table_header), Paragraph("<b>Memory</b>", table_header), Paragraph("<b>Latency</b>", table_header), Paragraph("<b>Privacy</b>", table_header), Paragraph("<b>Accuracy</b>", table_header), Paragraph("<b>Operational Trade-offs</b>", table_header)]] + t21_rows, colWidths=[1.1*inch, 0.9*inch, 0.7*inch, 0.7*inch, 0.8*inch, 0.8*inch, 1.2*inch])
    t21_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(Spacer(1, 4))
    story.append(t21_pdf)
    story.append(Paragraph("Table 2.1: Comparison of Existing Traffic Classification Methodologies", caption_style))

    # -------------------------------------------------------------
    # 10. CHAPTER 3: SYSTEM MODEL / PROPOSED METHODOLOGY
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 3 – System Model / Proposed Methodology", h1_style))
    story.append(Paragraph("3.1 Proposed End-to-End System Architecture", h2_style))
    story.append(Paragraph(
        "The proposed architecture is organized into five modular pipeline stages designed for real-time, zero-payload stream processing. The system bridges physical hardware network capture on Windows workstations directly to a secure, local-only Security Operations Center console.",
        body_style
    ))
    
    arch_img = "UROP_Report/UROP_Report_Assets/architecture_diagram.png"
    if os.path.exists(arch_img):
        story.append(Image(arch_img, width=6.2*inch, height=3.4*inch))
        story.append(Paragraph("Figure 3.1: End-to-End System Architecture of the Real-Time Encrypted Traffic Classifier", caption_style))

    story.append(Paragraph(
        "As depicted in Figure 3.1, raw Ethernet frames are captured promiscuously from the host's active Network Interface Card (NIC) via the kernel-level Windows Npcap driver. The zero-payload capture tap immediately strips Layer-2 headers and inspects only Layer-3/4 transport boundaries. Application payload bytes are scrubbed at the memory ingestion boundary before being forwarded to the Bidirectional Flow Tracker. Flow features are computed online using streaming statistical updates and delivered to the ML Inference Engine. The resulting prediction events are written atomically to an indexed SQLite LocalEventStore and streamed via a local REST API (http://127.0.0.1:8080) to the SOC Dashboard.",
        body_style
    ))

    flow_img = "UROP_Report/UROP_Report_Assets/workflow_flowchart.png"
    if os.path.exists(flow_img):
        story.append(Image(flow_img, width=6.2*inch, height=3.1*inch))
        story.append(Paragraph("Figure 3.2: End-to-End Experimental Research Methodology and Verification Workflow", caption_style))

    story.append(Paragraph("3.2 Bidirectional 5-Tuple Flow Reconstruction & Connection Tracking", h2_style))
    story.append(Paragraph(
        "A network flow is formally defined as a sequence of packets traversing the network within a bounded temporal window sharing a unique canonical 5-tuple key: <b>FlowKey = (IP_A, Port_A, IP_B, Port_B, Protocol)</b>. Endpoints are canonically sorted: endpoint_A = min((src_ip, src_port), (dst_ip, dst_port)) and endpoint_B = max((src_ip, src_port), (dst_ip, dst_port)). Directionality is explicitly tracked: packets originating from the initiator are designated as FORWARD, while reply packets are designated as BACKWARD.",
        body_style
    ))
    story.append(Paragraph(
        "Flow lifecycle transitions are governed by an asynchronous state machine: (1) TCP Connection Termination: Receipt of an RST flag (0x04) or two FIN flags (0x01) transitions the flow to the CLOSED state, followed by a 5.0-second grace window to absorb retransmissions; (2) Idle Timeout: Inactive flows expire after Delta_t_idle = 60.0 seconds; (3) Active Timeout: Long flows segment at Delta_t_active = 1800.0 seconds; and (4) Online Statistical Updates: Running packet inter-arrival time (IAT) variance is computed in O(1) time using Welford's algorithm: M_k = M_{k-1} + (x_k - M_{k-1})/k, S_k = S_{k-1} + (x_k - M_{k-1})(x_k - M_k), sigma^2 = S_k/(k - 1).",
        body_style
    ))

    story.append(Paragraph("3.3 Zero-Payload Privacy Contract & Canonical Feature Space", h2_style))
    story.append(Paragraph(
        "The feature extraction engine extracts strictly statistical and structural metadata from transport headers. To guarantee absolute compliance with institutional privacy standards and data protection laws, all IP addresses, ephemeral port numbers, MAC addresses, and application payload bytes are excluded from feature representations. The canonical 21-feature space is structured across seven behavioral families, as detailed in Table 3.1.",
        body_style
    ))

    tbl_feats = [
        ("A. Packet Size Stats", "packet_length_mean, std, min, max", "Quantifies physical payload size distribution and MTU clamping."),
        ("B. Inter-Arrival Timing", "iat_mean, iat_std, iat_min, iat_max", "Captures transmission pacing, network jitter, and interactive delays."),
        ("C. Flow Volumes", "total_packets, total_bytes, fwd/bwd pkts & bytes", "Measures connection scale and macroscopic bandwidth consumption."),
        ("D. Directional Asymmetry", "packet_ratio (Fwd/Bwd), byte_ratio", "Captures client-server request-response asymmetry (key signal)."),
        ("E. Connection Duration", "duration_seconds, packets/s, bytes/s", "Profiles connection longevity, throughput, and packet frequency."),
        ("F. Burst Dynamics", "burst_count, mean_burst_size", "Identifies packet clustering characteristic of video & web DOMs."),
        ("G. Transport Protocol", "is_tcp, is_udp", "Binary one-hot indicators identifying underlying Layer-4 protocol.")
    ]
    t31_rows = [[Paragraph(f"<b>{fam}</b>", table_cell), Paragraph(fts, table_cell), Paragraph(sig, table_cell)] for fam, fts, sig in tbl_feats]
    t31_pdf = Table([[Paragraph("<b>Feature Family</b>", table_header), Paragraph("<b>Canonical Features</b>", table_header), Paragraph("<b>Discriminative Significance</b>", table_header)]] + t31_rows, colWidths=[1.5*inch, 2.1*inch, 2.6*inch])
    t31_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(Spacer(1, 4))
    story.append(t31_pdf)
    story.append(Paragraph("Table 3.1: Breakdown of the 21 Canonical Zero-Payload Flow Transport Features", caption_style))

    story.append(Paragraph("3.4 Dataset Design, Hygiene & Session Partitioning", h2_style))
    story.append(Paragraph(
        "To eliminate topological bias and prevent synthetic artifacts, we authored dataset_v2, a multi-environment hybrid benchmark encompassing 301 verified flows across 150 independent sessions. Table 3.2 details the balanced class distributions and behavioral characteristics.",
        body_style
    ))

    tbl_classes = [
        ("Web Browsing (Web)", "50", "Interactive HTTPS / QUIC navigation across dynamic portals.", "Bursty request-response bursts; moderate packet sizes; variable IATs."),
        ("Video Streaming (Video)", "50", "YouTube / Netflix adaptive bitrate streaming.", "High downstream byte ratio; periodic large packet clusters during refill."),
        ("Instant Messaging (Messaging)", "50", "Signal / Telegram / WhatsApp signaling & chat.", "Sporadic low-volume packets; high idle keep-alives; low byte ratios."),
        ("Voice over IP (VoIP)", "50", "Zoom / Teams / WebRTC audio & video calling.", "Highly symmetric packet rates; small uniform lengths; tight IATs."),
        ("Bulk File Transfer (File Transfer)", "50", "SFTP / Drive / Large HTTPS downloads.", "Persistent maximum MTU lengths (1420-1500 B); downstream saturation."),
        ("Background Telemetry (Other)", "51", "OS updates, telemetry daemons, NTP.", "Heterogeneous negative class; periodic signaling; small payloads.")
    ]
    t32_rows = [[Paragraph(f"<b>{c}</b>", table_cell), Paragraph(n, table_cell_center), Paragraph(act, table_cell), Paragraph(dyn, table_cell)] for c, n, act, dyn in tbl_classes]
    t32_pdf = Table([[Paragraph("<b>Traffic Class</b>", table_header), Paragraph("<b>Flows</b>", table_header), Paragraph("<b>Target Activity Profile</b>", table_header), Paragraph("<b>Distinctive Transport Dynamics</b>", table_header)]] + t32_rows, colWidths=[1.4*inch, 0.6*inch, 2.1*inch, 2.1*inch])
    t32_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(Spacer(1, 4))
    story.append(t32_pdf)
    story.append(Paragraph("Table 3.2: Target Application Classes and Transport Profile Characteristics", caption_style))

    story.append(Paragraph(
        "To ensure zero partition leakage, we implemented Group-Aware Stratified Session Partitioning. Rather than splitting flows uniformly at random, flows are grouped strictly by their unique session_id. The dataset is partitioned into 60% Training (181 flows), 20% Validation (60 flows), and 20% Testing (60 flows; locked test set of 48 in-domain flows), maintaining strict session isolation: Training Sessions intersect Testing Sessions = Empty Set.",
        body_style
    ))

    story.append(Paragraph("3.5 Classification Algorithms & Inference Engine", h2_style))
    story.append(Paragraph(
        "We evaluated four distinct algorithmic architectures: (1) Multinomial Logistic Regression (LR) as a convex linear baseline; (2) CART Decision Tree (DT) with maximum depth constrained to 6 to prevent leaf memorization; (3) Random Forest (RF) ensemble of 100 randomized CART trees with bootstrap aggregation; and (4) LightGBM (LGBM) leaf-wise gradient boosting with histogram binning for high computational efficiency.",
        body_style
    ))

    story.append(Paragraph("3.6 Selective Prediction & Uncertainty Estimation", h2_style))
    story.append(Paragraph(
        "To protect network operations from high-risk false positives, we formulated a calibrated selective classification architecture based on Chow's optimal rejection rule: (f, g)(x) = f(x) if max_c P(Y=c|X=x) >= tau, else ABSTAIN. Furthermore, we implemented a four-state prediction state machine: KNOWN_CLASS (high confidence, P >= tau, N >= 3 packets), LOW_CONFIDENCE (0.35 <= P < tau), UNKNOWN (P < 0.35, out-of-distribution traffic), and INSUFFICIENT_EVIDENCE (N < 3 packets).",
        body_style
    ))

    # -------------------------------------------------------------
    # 11. CHAPTER 4: IMPLEMENTATION
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 4 – Implementation", h1_style))
    story.append(Paragraph("4.1 Development Environment & Software Stack", h2_style))
    story.append(Paragraph(
        "The system is implemented in Python 3.14/3.10 and designed natively for Windows enterprise endpoints. Table 4.1 summarizes the core technologies and dependencies comprising the operational platform.",
        body_style
    ))

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
    t41_rows = [[Paragraph(f"<b>{c}</b>", table_cell), Paragraph(v, table_cell)] for c, v in tbl_env]
    t41_pdf = Table([[Paragraph("<b>Subsystem / Component</b>", table_header), Paragraph("<b>Technical Specification & Version</b>", table_header)]] + t41_rows, colWidths=[2.1*inch, 4.1*inch])
    t41_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(Spacer(1, 4))
    story.append(t41_pdf)
    story.append(Paragraph("Table 4.1: Implementation Software Stack and Development Environment Specifications", caption_style))

    story.append(Paragraph("4.2 Core Subsystem Implementation", h2_style))
    story.append(Paragraph("4.2.1 Live Packet Capture Subsystem", h3_style))
    story.append(Paragraph(
        "Live sniffing is encapsulated in LiveSniffer (capture/packet_capture.py). Interface resolution is dynamically resolved by capture/interface_resolver.py, mapping user-friendly adapter names ('Wi-Fi') to native Npcap GUID paths (\\Device\\NPF_{...}). The packet parser unpacks Ethernet framing, decodes Layer-3 IP/IPv6 headers, extracts Layer-4 TCP/UDP metrics, and discards all application payload bytes at memory boundaries.",
        body_style
    ))

    story.append(Paragraph("4.2.2 Real-Time Flow Tracker", h3_style))
    story.append(Paragraph(
        "Flow reconstruction is implemented in realtime/flow_tracker.py. Inbound packets update the active flow table in O(1) amortized time. Flows achieve prediction eligibility upon observing N = 3 packets, and periodic checks trigger at 1.0-second intervals. An asynchronous daemon schedules clean_stale_flows() every second, ensuring TCP FIN/RST states and idle timeouts transition cleanly to completed events.",
        body_style
    ))

    story.append(Paragraph("4.2.3 Online Feature Extractor", h3_style))
    story.append(Paragraph(
        "Feature extraction is managed by FeatureExtractor (preprocessing/feature_extractor.py). It accepts active Flow instances, extracts the 21 canonical features, validates vectors against a frozen schema hash, and applies pre-computed standardization scaling.",
        body_style
    ))

    story.append(Paragraph("4.2.4 Model Inference Engine", h3_style))
    story.append(Paragraph(
        "Inference is executed by RealTimeClassifier (realtime/classifier.py). Work is buffered in a thread-safe Queue (capacity 10,000 items) and processed by asynchronous worker threads. ModelLoader executes predict_proba, computes composed confidence scores, and enforces the selective prediction state machine.",
        body_style
    ))

    story.append(Paragraph("4.2.5 Event Persistence & Local REST API", h3_style))
    story.append(Paragraph(
        "Prediction events are saved in data/events/event_store.db via LocalEventStore. LocalAPIServer (product/local_api.py) runs on port 8080, serving localhost endpoints (/health, /status, /adapters, /model, /metrics, /predictions) with origin security validation.",
        body_style
    ))

    story.append(Paragraph("4.2.6 Real-Time SOC Streamlit Console", h3_style))
    story.append(Paragraph(
        "The SOC dashboard (dashboard/app.py) provides real-time human observability across eight specialized tabs: Live SOC Console, Traffic Overview, Flow Explorer, Early Classification, Confidence & Calibration, Performance Telemetry, Model Verification, and Research Limitations.",
        body_style
    ))

    story.append(Paragraph("4.3 Experimental Verification Setup", h2_style))
    story.append(Paragraph(
        "Validation was conducted using automated Python regression test suites (148 tests passing with 0 failures) and live physical hardware capture testing via scripts/start_local.py, guaranteeing fail-closed operation without synthetic fallbacks.",
        body_style
    ))

    # -------------------------------------------------------------
    # 12. CHAPTER 5: RESULTS AND DISCUSSION
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 5 – Results and Discussion", h1_style))
    story.append(Paragraph("5.1 In-Domain Baseline Benchmark Results (EXP-R09)", h2_style))
    story.append(Paragraph(
        "To address Research Question 1, all candidate models were evaluated on the locked test partition (48 in-domain flows across 6 balanced classes) under 21 canonical features. Table 5.1 presents the baseline performance matrix.",
        body_style
    ))

    tbl_base = [
        ("Random Forest", "0.5984", "0.5833", "0.5999", "0.5833", "0.5873", "0.5833", "17.29 ms", "31.79 ms", "881.98 KB", "YES"),
        ("Decision Tree", "0.5382", "0.5833", "0.6657", "0.5833", "0.5802", "0.5833", "0.058 ms", "0.086 ms", "9.58 KB", "NO"),
        ("LightGBM", "0.5664", "0.5417", "0.5579", "0.5417", "0.5474", "0.5417", "0.352 ms", "0.742 ms", "689.33 KB", "NO"),
        ("Logistic Regression", "0.3684", "0.3333", "0.3327", "0.3333", "0.3240", "0.3333", "0.069 ms", "0.164 ms", "2.00 KB", "NO")
    ]
    t51_rows = [[Paragraph(f"<b>{m}</b>", table_cell), Paragraph(vf, table_cell_center), Paragraph(acc, table_cell_center), Paragraph(pr, table_cell_center), Paragraph(rec, table_cell_center), Paragraph(f"<b>{mf}</b>", table_cell_center), Paragraph(ba, table_cell_center), Paragraph(mlat, table_cell_center), Paragraph(plat, table_cell_center), Paragraph(sz, table_cell_center), Paragraph(w, table_cell_center)] for m, vf, acc, pr, rec, mf, ba, mlat, plat, sz, w in tbl_base]
    t51_pdf = Table([[Paragraph("<b>Estimator</b>", table_header), Paragraph("<b>Val F1</b>", table_header), Paragraph("<b>Acc</b>", table_header), Paragraph("<b>Prec</b>", table_header), Paragraph("<b>Recall</b>", table_header), Paragraph("<b>Macro-F1</b>", table_header), Paragraph("<b>Bal Acc</b>", table_header), Paragraph("<b>Med Lat</b>", table_header), Paragraph("<b>P95 Lat</b>", table_header), Paragraph("<b>Size</b>", table_header), Paragraph("<b>Winner</b>", table_header)]] + t51_rows, colWidths=[1.1*inch, 0.45*inch, 0.45*inch, 0.45*inch, 0.45*inch, 0.55*inch, 0.5*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.45*inch])
    t51_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t51_pdf)
    story.append(Paragraph("Table 5.1: In-Domain Baseline Performance Matrix on the dataset_v2 Benchmark", caption_style))

    f1_img = "UROP_Report/UROP_Report_Assets/fig_baseline_comparison.png"
    if os.path.exists(f1_img):
        story.append(Image(f1_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.1: In-Domain Baseline Model Comparison across Evaluated Estimators", caption_style))

    f2_img = "UROP_Report/UROP_Report_Assets/fig_confusion_matrix.png"
    if os.path.exists(f2_img):
        story.append(Image(f2_img, width=5.8*inch, height=3.0*inch))
        story.append(Paragraph("Figure 5.2: Multi-Panel Normalized Confusion Matrices for Evaluated Machine Learning Models", caption_style))

    story.append(Paragraph(
        "Random Forest achieves the highest raw test accuracy (0.5873 Macro-F1). However, the CART Decision Tree achieves 0.5802 Macro-F1 (98.8% of Random Forest's fidelity) while executing in 0.0579 ms (249 times faster) with an ultra-compact 9.58 KB disk footprint. This establishes the Decision Tree as the undisputed Pareto-optimal estimator for edge security hardware.",
        body_style
    ))

    story.append(Paragraph("5.2 Feature Family Ablation & Dimensionality Trade-offs (EXP-R10)", h2_style))
    story.append(Paragraph(
        "To address Research Question 2, we conducted isolated feature family ablation and dimensionality scaling tests from K = 3 to K = 84 features. Tables 5.2 and 5.3 present the results.",
        body_style
    ))

    tbl_abl = [
        ("Directional Asymmetry Only", "3", "0.4803", "0.5000", "0.4241", "0.4167", "27.15 ms", "Directionality ratios carry densest signal."),
        ("Timing Dynamics Only", "30", "0.3094", "0.3333", "0.3438", "0.3333", "28.81 ms", "Vulnerable to network jitter and queuing delays."),
        ("Volume & Byte Counts Only", "12", "0.3368", "0.3333", "0.3375", "0.3333", "31.42 ms", "Distinguishes bulk transfers from interactive chats."),
        ("Packet Size Stats Only", "30", "0.3233", "0.3542", "0.2949", "0.3125", "31.32 ms", "Degraded by fixed MTU tunnel padding."),
        ("Burst Dynamics Only", "8", "0.4075", "0.4167", "0.2100", "0.2292", "30.15 ms", "Overfits validation split; poor test transfer."),
        ("All 84 Features Combined", "84", "0.3741", "0.3750", "0.2931", "0.2917", "28.92 ms", "Dimensionality curse; noise degrades accuracy.")
    ]
    t52_rows = [[Paragraph(f"<b>{fam}</b>", table_cell), Paragraph(k, table_cell_center), Paragraph(vf, table_cell_center), Paragraph(va, table_cell_center), Paragraph(f"<b>{tf}</b>", table_cell_center), Paragraph(ta, table_cell_center), Paragraph(lat, table_cell_center), Paragraph(fnd, table_cell)] for fam, k, vf, va, tf, ta, lat, fnd in tbl_abl]
    t52_pdf = Table([[Paragraph("<b>Feature Family</b>", table_header), Paragraph("<b>K</b>", table_header), Paragraph("<b>Val F1</b>", table_header), Paragraph("<b>Val Acc</b>", table_header), Paragraph("<b>Test F1</b>", table_header), Paragraph("<b>Test Acc</b>", table_header), Paragraph("<b>P95 Lat</b>", table_header), Paragraph("<b>Empirical Finding</b>", table_header)]] + t52_rows, colWidths=[1.5*inch, 0.35*inch, 0.5*inch, 0.5*inch, 0.55*inch, 0.5*inch, 0.65*inch, 1.65*inch])
    t52_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t52_pdf)
    story.append(Paragraph("Table 5.2: Feature Family Ablation Scorecard", caption_style))

    f3_img = "UROP_Report/UROP_Report_Assets/fig_feature_pareto.png"
    if os.path.exists(f3_img):
        story.append(Image(f3_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.3: Feature Count Pareto Frontier (Macro-F1 vs. P95 Vector Inference Latency)", caption_style))

    tbl_dim = [
        ("K = 3 Features", "0.7572", "0.7708", "0.6708", "0.6667", "28.32 ms", "Selected Ultra-Lightweight Profile"),
        ("K = 5 Features", "0.3324", "0.3333", "0.4073", "0.4167", "30.04 ms", "Intermediate candidate"),
        ("K = 10 Features", "0.2531", "0.2708", "0.3444", "0.3750", "30.29 ms", "Production multi-environment profile"),
        ("K = 15 Features", "0.3365", "0.3542", "0.3591", "0.3750", "31.11 ms", "Diminishing performance returns"),
        ("K = 20 Features", "0.3422", "0.3542", "0.3689", "0.3750", "29.57 ms", "Performance plateau"),
        ("K = 84 Features", "0.3435", "0.3333", "0.2857", "0.2917", "31.16 ms", "Severe degradation from dimensionality curse")
    ]
    t53_rows = [[Paragraph(f"<b>{p}</b>", table_cell), Paragraph(vf, table_cell_center), Paragraph(va, table_cell_center), Paragraph(f"<b>{tf}</b>", table_cell_center), Paragraph(ta, table_cell_center), Paragraph(lat, table_cell_center), Paragraph(dec, table_cell)] for p, vf, va, tf, ta, lat, dec in tbl_dim]
    t53_pdf = Table([[Paragraph("<b>Profile</b>", table_header), Paragraph("<b>Val F1</b>", table_header), Paragraph("<b>Val Acc</b>", table_header), Paragraph("<b>Test F1</b>", table_header), Paragraph("<b>Test Acc</b>", table_header), Paragraph("<b>P95 Lat</b>", table_header), Paragraph("<b>Selection Decision</b>", table_header)]] + t53_rows, colWidths=[1.3*inch, 0.6*inch, 0.6*inch, 0.65*inch, 0.6*inch, 0.75*inch, 1.7*inch])
    t53_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t53_pdf)
    story.append(Paragraph("Table 5.3: Feature Dimensionality vs. Generalization Trade-off Matrix", caption_style))

    story.append(Paragraph(
        "A compact 3-feature subset focusing on forward/backward packet and byte ratios achieves peak test Macro-F1 of 0.6708. In stark contrast, incorporating all 84 candidate features causes test Macro-F1 to collapse to 0.2857. This proves that high-dimensional feature spaces introduce noisy, non-generalizable correlations that degrade tree-based traffic classifiers.",
        body_style
    ))

    story.append(Paragraph("5.3 Domain-Shift Generalization Benchmark Results (EXP-R11)", h2_style))
    story.append(Paragraph(
        "To address Research Question 3, models trained on baseline physical traffic were evaluated across eight distribution-shift regimes without retraining. Table 5.4 presents the generalization scorecard.",
        body_style
    ))

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
    t54_rows = [[Paragraph(f"<b>{reg}</b>", table_cell), Paragraph(n, table_cell_center), Paragraph(acc, table_cell_center), Paragraph(pr, table_cell_center), Paragraph(f"<b>{mf}</b>", table_cell_center), Paragraph(d, table_cell_center), Paragraph(lat, table_cell_center), Paragraph(f"<b>{v}</b>", table_cell)] for reg, n, acc, pr, mf, d, lat, v in tbl_gen]
    t54_pdf = Table([[Paragraph("<b>Shift Regime</b>", table_header), Paragraph("<b>N</b>", table_header), Paragraph("<b>Acc</b>", table_header), Paragraph("<b>Prec</b>", table_header), Paragraph("<b>Macro-F1</b>", table_header), Paragraph("<b>Delta F1</b>", table_header), Paragraph("<b>Lat</b>", table_header), Paragraph("<b>Verdict</b>", table_header)]] + t54_rows, colWidths=[1.8*inch, 0.35*inch, 0.45*inch, 0.5*inch, 0.6*inch, 0.6*inch, 0.6*inch, 1.3*inch])
    t54_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t54_pdf)
    story.append(Paragraph("Table 5.4: Domain-Shift Generalization Scorecard Across Eight Distribution Regimes", caption_style))

    f4_img = "UROP_Report/UROP_Report_Assets/fig_generalization.png"
    if os.path.exists(f4_img):
        story.append(Image(f4_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.4: Domain-Shift Generalization Scorecard Across 8 Distribution-Shift Regimes", caption_style))

    f5_img = "UROP_Report/UROP_Report_Assets/fig_environment_shift.png"
    if os.path.exists(f5_img):
        story.append(Image(f5_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.5: Generalization Across Physical Media (Wi-Fi vs. Ethernet and Cellular LTE)", caption_style))

    f6_img = "UROP_Report/UROP_Report_Assets/fig_tunnel_shift.png"
    if os.path.exists(f6_img):
        story.append(Image(f6_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.6: Asymmetric Tunnel Generalization Shift (Direct vs. WireGuard / Cloudflare WARP)", caption_style))

    story.append(Paragraph("5.4 Early Encrypted-Traffic Classification Dynamics (EXP-R12)", h2_style))
    story.append(Paragraph(
        "To address Research Question 4, feature extraction was restricted to early packet horizons (N in {3, 5, 10, 20, 30, 50, full}). Table 5.5 decomposes the total decision latency into physical arrival wire delay and algorithmic inference execution.",
        body_style
    ))

    tbl_early = [
        ("3 Packets", "3", "91.67%", "0.6364", "0.6667", "0.6111", "79.94 ms", "64.04 ms", "16.53 ms", "746x Faster"),
        ("5 Packets", "5", "100.0%", "0.4167", "0.3389", "0.3643", "348.89 ms", "331.38 ms", "16.51 ms", "171x Faster"),
        ("10 Packets", "10", "41.67%", "0.8000", "0.5000", "0.5000", "1329.18 ms", "1312.08 ms", "19.13 ms", "45x Faster"),
        ("20 Packets", "20", "58.33%", "0.4286", "0.3333", "0.2778", "3954.60 ms", "3938.44 ms", "16.43 ms", "15x Faster"),
        ("30 Packets", "30", "100.0%", "0.3333", "0.2500", "0.2778", "4893.25 ms", "4877.01 ms", "17.39 ms", "12x Faster"),
        ("50 Packets", "50", "50.00%", "0.5000", "0.3000", "0.3000", "9282.92 ms", "9265.80 ms", "17.30 ms", "6x Faster"),
        ("Full Flow", "Full", "33.33%", "0.0000", "0.0000", "0.0000", "59,668 ms", "59,650 ms", "16.92 ms", "Post-Mortem")
    ]
    t55_rows = [[Paragraph(f"<b>{h}</b>", table_cell), Paragraph(n, table_cell_center), Paragraph(c, table_cell_center), Paragraph(acc, table_cell_center), Paragraph(rec, table_cell_center), Paragraph(f"<b>{mf}</b>", table_cell_center), Paragraph(tot, table_cell_center), Paragraph(wire, table_cell_center), Paragraph(alg, table_cell_center), Paragraph(f"<b>{spd}</b>", table_cell)] for h, n, c, acc, rec, mf, tot, wire, alg, spd in tbl_early]
    t55_pdf = Table([[Paragraph("<b>Horizon</b>", table_header), Paragraph("<b>N</b>", table_header), Paragraph("<b>Cov</b>", table_header), Paragraph("<b>Acc</b>", table_header), Paragraph("<b>Recall</b>", table_header), Paragraph("<b>Macro-F1</b>", table_header), Paragraph("<b>Total Lat</b>", table_header), Paragraph("<b>Wire Delay</b>", table_header), Paragraph("<b>Algo Lat</b>", table_header), Paragraph("<b>Speedup</b>", table_header)]] + t55_rows, colWidths=[0.8*inch, 0.3*inch, 0.5*inch, 0.45*inch, 0.45*inch, 0.6*inch, 0.75*inch, 0.75*inch, 0.7*inch, 0.9*inch])
    t55_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t55_pdf)
    story.append(Paragraph("Table 5.5: Early Prediction Horizons and Latency Decomposition Matrix", caption_style))

    f7_img = "UROP_Report/UROP_Report_Assets/fig_early_prediction.png"
    if os.path.exists(f7_img):
        story.append(Image(f7_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.7: Early Prediction Horizon Dynamics: Macro-F1 vs. Packet Prefix Horizon", caption_style))

    story.append(Paragraph("5.5 Selective Classification & Confidence Calibration (EXP-R13)", h2_style))
    story.append(Paragraph(
        "To address Research Question 5, we evaluated the selective prediction rejection policy across rejection thresholds tau in [0.00, 0.90] on the locked test set. Table 5.6 details the coverage-accuracy trade-offs.",
        body_style
    ))

    tbl_sel = [
        ("tau = 0.00 (No Rejection)", "100.0%", "48 / 48", "0.5417", "45.83%", "0.5474", "0.7412", "0.1996", "NO"),
        ("tau = 0.50", "91.67%", "44 / 48", "0.5909", "40.91%", "0.6012", "0.7690", "0.1781", "NO"),
        ("tau = 0.60", "75.00%", "36 / 48", "0.6389", "36.11%", "0.6110", "0.8189", "0.1800", "NO"),
        ("tau = 0.70 (Optimal tau*)", "54.17%", "26 / 48", "0.7308", "26.92%", "0.6515", "0.8818", "0.1510", "YES"),
        ("tau = 0.80", "43.75%", "21 / 48", "0.8571", "14.29%", "0.8752", "0.9112", "0.0541", "NO"),
        ("tau = 0.90 (High Security)", "20.83%", "10 / 48", "0.9000", "10.00%", "0.9000", "0.9658", "0.0658", "NO")
    ]
    t56_rows = [[Paragraph(f"<b>{pol}</b>", table_cell), Paragraph(cov, table_cell_center), Paragraph(accp, table_cell_center), Paragraph(acc, table_cell_center), Paragraph(err, table_cell_center), Paragraph(f"<b>{mf}</b>", table_cell_center), Paragraph(cnf, table_cell_center), Paragraph(ece, table_cell_center), Paragraph(opt, table_cell_center)] for pol, cov, accp, acc, err, mf, cnf, ece, opt in tbl_sel]
    t56_pdf = Table([[Paragraph("<b>Policy</b>", table_header), Paragraph("<b>Cov</b>", table_header), Paragraph("<b>Accept</b>", table_header), Paragraph("<b>Acc</b>", table_header), Paragraph("<b>Error</b>", table_header), Paragraph("<b>Macro-F1</b>", table_header), Paragraph("<b>Conf</b>", table_header), Paragraph("<b>ECE</b>", table_header), Paragraph("<b>Opt</b>", table_header)]] + t56_rows, colWidths=[1.5*inch, 0.55*inch, 0.6*inch, 0.55*inch, 0.55*inch, 0.65*inch, 0.6*inch, 0.55*inch, 0.65*inch])
    t56_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t56_pdf)
    story.append(Paragraph("Table 5.6: Selective Prediction Performance Matrix on Locked Test Set", caption_style))

    f8_img = "UROP_Report/UROP_Report_Assets/fig_selective_coverage.png"
    if os.path.exists(f8_img):
        story.append(Image(f8_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.8: Selective Prediction Risk-Coverage Curve (Selective Accuracy vs. Coverage)", caption_style))

    f9_img = "UROP_Report/UROP_Report_Assets/fig_calibration_curve.png"
    if os.path.exists(f9_img):
        story.append(Image(f9_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.9: Confidence Reliability Diagram and Empirical Calibration Curve (ECE = 0.1996)", caption_style))

    story.append(Paragraph("5.6 Real-Time Latency & Edge Computational Efficiency (EXP-R14)", h2_style))
    story.append(Paragraph(
        "To address Research Question 6, we executed micro-benchmarking across 500 warm steady-state flow vectors on host hardware. Table 5.7 provides the stage-by-stage latency profile.",
        body_style
    ))

    tbl_lat = [
        ("Feature Extraction", "Statistical Engine", "0.3856 ms", "7.1524 ms", "9.4675 ms", "26.80 ms", "667.6 flows/s"),
        ("Preprocessing / Scaling", "FeaturePreprocessor", "0.0035 ms", "0.0040 ms", "0.0215 ms", "0.0697 ms", "243,902 flows/s"),
        ("Decision Tree Inference", "Tree Traversal", "0.0579 ms", "0.0860 ms", "0.1982 ms", "0.4916 ms", "15,600.6 flows/s"),
        ("Logistic Regression Inference", "Matrix Dot Product", "0.0695 ms", "0.1642 ms", "0.2656 ms", "0.3945 ms", "12,224.9 flows/s"),
        ("LightGBM Inference", "Gradient Boost Ensemble", "0.3520 ms", "0.7419 ms", "0.9477 ms", "1.2387 ms", "2,307.3 flows/s"),
        ("Random Forest Inference", "100-Tree Forest", "4.2476 ms", "7.8099 ms", "9.5337 ms", "10.2371 ms", "213.3 flows/s"),
        ("End-to-End Pipeline (DT)", "Complete Ingestion-to-Event", "0.4491 ms", "7.2144 ms", "9.5481 ms", "26.8656 ms", "638.9 flows/s")
    ]
    t57_rows = [[Paragraph(f"<b>{stg}</b>", table_cell), Paragraph(sub, table_cell), Paragraph(p50, table_cell_center), Paragraph(p95, table_cell_center), Paragraph(p99, table_cell_center), Paragraph(mx, table_cell_center), Paragraph(f"<b>{fps}</b>", table_cell_center)] for stg, sub, p50, p95, p99, mx, fps in tbl_lat]
    t57_pdf = Table([[Paragraph("<b>Pipeline Stage</b>", table_header), Paragraph("<b>Subsystem</b>", table_header), Paragraph("<b>P50</b>", table_header), Paragraph("<b>P95</b>", table_header), Paragraph("<b>P99</b>", table_header), Paragraph("<b>Max</b>", table_header), Paragraph("<b>Throughput</b>", table_header)]] + t57_rows, colWidths=[1.4*inch, 1.2*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.8*inch])
    t57_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t57_pdf)
    story.append(Paragraph("Table 5.7: Stage-by-Stage Latency Breakdown in Steady-State Warm Operation", caption_style))

    f10_img = "UROP_Report/UROP_Report_Assets/fig_latency_distribution.png"
    if os.path.exists(f10_img):
        story.append(Image(f10_img, width=5.6*inch, height=2.6*inch))
        story.append(Paragraph("Figure 5.10: Empirical Vector Inference Latency Distribution (Cold-Start vs. Steady-State)", caption_style))

    story.append(Paragraph("5.7 Forensic Reconciliation of Research Claims", h2_style))
    story.append(Paragraph(
        "In compliance with scientific integrity standards, we explicitly reconcile preliminary synthetic claims with authoritative physical measurements. Early exploratory testing on a 12-flow synthetic loopback fixture (dataset_v1) reported 0.9500 Macro-F1 and <0.003 ms latency. Our authoritative physical benchmarks (dataset_v2 and dataset_real_v1) demonstrate that real-world encrypted traffic under session isolation yields 0.5873 Macro-F1 (Random Forest) and 0.5802 Macro-F1 (Decision Tree) with 0.058 ms inference. The discrepancy is fully accounted for by loopback timing determinism, synthetic packet symmetry, and the absence of real cross-session variance in initial fixtures.",
        body_style
    ))

    # -------------------------------------------------------------
    # 13. CHAPTER 6: CONCLUDING REMARKS
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 6 – Concluding Remarks", h1_style))
    story.append(Paragraph(
        "This UROP project investigated the feasibility of real-time encrypted traffic classification using lightweight, non-deep machine learning models operating strictly on zero-payload Layer-3 and Layer-4 transport dynamics. By constructing an authoritative multi-environment benchmark (dataset_v2) and enforcing strict group-aware session partitioning, we dismantled the prevailing academic illusion of effortless >95% accuracy on real encrypted traffic while demonstrating practical paths to robust, privacy-compliant edge deployment.",
        body_style
    ))
    story.append(Paragraph("The primary conclusions of our research are summarized as follows:", body_style))
    story.append(Paragraph("1. Pareto Dominance of Lightweight Trees: Shallow CART Decision Trees achieve 0.5802 Macro-F1—matching 98.8% of Random Forest's performance—while executing in 0.0579 ms (15,600 flows/sec) and requiring only 9.58 KB of memory. This demonstrates that massive deep neural networks are unnecessary and counterproductive for line-rate edge classification.", body_style))
    story.append(Paragraph("2. High Value of Directional Asymmetry: Directional packet and byte ratios carry the densest discriminative signal (0.4241 Macro-F1 with only 3 features). High-dimensional feature sets (K = 84) degrade classification accuracy due to the curse of dimensionality.", body_style))
    story.append(Paragraph("3. Asymmetric Vulnerability to Tunneling: Statistical transport models generalize seamlessly across physical Layer-1/2 media (0.9325 Macro-F1 on unseen Ethernet and LTE links), but experience catastrophic performance degradation under WireGuard VPN tunneling (0.3407 Macro-F1) due to standardized MTU padding. Models intended for tunneled environments must be explicitly trained on tunneled traffic prototypes.", body_style))
    story.append(Paragraph("4. Wire Delay Dominates Early Triage: Physical wire delay accounts for 99.8% of end-to-end classification latency. Triage at N = 3 packets achieves 0.6111 Macro-F1 in 79.94 ms—746 times faster than waiting for retrospective flow termination, which completely fails due to temporal feature dilution.", body_style))
    story.append(Paragraph("5. Error Suppression via Calibrated Rejection: Selective prediction with an optimal validation-tuned threshold (tau* = 0.70) cuts operational error rates from 45.83% down to 26.92% at 54.17% coverage, providing an indispensable safety net for enterprise SOC deployments.", body_style))

    # -------------------------------------------------------------
    # 14. CHAPTER 7: FUTURE WORK
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Chapter 7 – Future Work", h1_style))
    story.append(Paragraph(
        "While the present work provides an authoritative, fully reproducible baseline for lightweight encrypted traffic classification, several promising avenues for future research remain:",
        body_style
    ))
    story.append(Paragraph("1. Self-Supervised Transport Representation Learning: Future work should investigate lightweight self-supervised contrastive learning on unlabelled flow streams to learn robust representations prior to tree distillation, potentially mitigating the class overlap observed between interactive web and messaging traffic.", body_style))
    story.append(Paragraph("2. Kernel-Level eBPF/XDP Ingestion: While Windows Npcap provides excellent desktop user-space capture, porting the zero-payload extraction engine to Linux Extended Berkeley Packet Filters (eBPF) and eXpress Data Path (XDP) would enable kernel-space feature calculation directly within the network driver, achieving true 100 Gbps line-rate processing.", body_style))
    story.append(Paragraph("3. Continuous Active Domain Adaptation: Developing online streaming adaptation algorithms that detect concept drift (such as shifts in CDN buffering algorithms or browser protocol versions) and automatically trigger selective retraining would enhance long-term temporal robustness.", body_style))
    story.append(Paragraph("4. Adversarial Robustness to Packet Padding: Future research must investigate the defensive hardening of statistical classifiers against adversarial traffic morphing, such as randomized packet padding (e.g., padding extensions in TLS 1.3 and WireGuard) and artificial inter-packet timing jitter injections designed to evade behavioral classifiers.", body_style))

    # -------------------------------------------------------------
    # 15. REFERENCES
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("References", h1_style))
    story.append(Spacer(1, 6))

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
        story.append(Paragraph(f"<b>[{idx}]</b> {ref}", ref_style))

    # Build PDF with custom NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")

if __name__ == "__main__":
    generate_urop_pdf()

