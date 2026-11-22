#!/usr/bin/env python3
"""
UROP Academic Report Generator — SRM University-AP Format.
Project: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models
Student: Gorakala Rishik
Department of Computer Science & Engineering, SRM University-AP

Generates:
1. submission/UROP_Academic_Report.docx (Complete Microsoft Word Report)
2. submission/UROP_Academic_Report.pdf (Direct PDF Export via docx2pdf)
3. Reconciles Table of Contents, List of Tables, and List of Figures with exact page numbers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import docx
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

import docx2pdf
import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ─── XML & FORMATTING UTILITIES ──────────────────────────────────────────────

def set_cell_shading(cell, color_hex: str):
    """Sets cell background shading."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def add_formatted_paragraph(doc, text, style="Normal", bold=False, italic=False,
                            alignment=None, font_size=None, font_name="Times New Roman",
                            space_before=None, space_after=None, line_spacing=1.5,
                            color=None, first_line_indent=None, keep_with_next=False):
    """Adds a formatted paragraph to the document."""
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    if bold:
        run.bold = True
    if italic:
        run.italic = True
    if font_size:
        run.font.size = Pt(font_size)
    if font_name:
        run.font.name = font_name
    if color:
        run.font.color.rgb = RGBColor(*color)
    if alignment is not None:
        p.alignment = alignment
    pf = p.paragraph_format
    if space_before is not None:
        pf.space_before = Pt(space_before)
    if space_after is not None:
        pf.space_after = Pt(space_after)
    if line_spacing is not None:
        pf.line_spacing = line_spacing
    if first_line_indent is not None:
        pf.first_line_indent = Cm(first_line_indent)
    if keep_with_next:
        pf.keep_with_next = True
    return p


def add_body_text(doc, text, indent=True, space_after=6, line_spacing=1.5):
    """Adds a justified body paragraph with 1.5 line spacing and optional indent."""
    p = doc.add_paragraph(style="Normal")
    run = p.add_run(text)
    run.font.size = Pt(12)
    run.font.name = "Times New Roman"
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    if indent:
        pf.first_line_indent = Cm(1.27)
    return p


def add_bullet_item(doc, text, bold_prefix=None):
    """Adds a bullet list item with proper indentation."""
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.size = Pt(12)
        r_pre.font.name = "Times New Roman"
    run = p.add_run(text)
    run.font.size = Pt(12)
    run.font.name = "Times New Roman"
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.25
    return p


def add_signature_table_2col(doc, left_lines, right_lines):
    """Adds a clean 2-column borderless table for signature blocks."""
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)

    c1 = table.rows[0].cells[0]
    c2 = table.rows[0].cells[1]
    c1.width = Inches(2.9)
    c2.width = Inches(3.1)

    p1 = c1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p1.paragraph_format.line_spacing = 1.2
    for idx, line in enumerate(left_lines):
        r = p1.add_run(line + ("\n" if idx < len(left_lines) - 1 else ""))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

    p2 = c2.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p2.paragraph_format.line_spacing = 1.2
    for idx, line in enumerate(right_lines):
        r = p2.add_run(line + ("\n" if idx < len(right_lines) - 1 else ""))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)
    return table


def add_chapter_heading(doc, chapter_num, title):
    """Adds a chapter heading centered with page break for chapters > 1."""
    if chapter_num > 1:
        doc.add_page_break()
    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf1 = p1.paragraph_format
    pf1.space_before = Pt(12)
    pf1.space_after = Pt(6)
    pf1.keep_with_next = True
    r1 = p1.add_run(f"CHAPTER {chapter_num}")
    r1.bold = True
    r1.font.size = Pt(16)
    r1.font.name = "Times New Roman"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf2 = p2.paragraph_format
    pf2.space_before = Pt(0)
    pf2.space_after = Pt(18)
    pf2.keep_with_next = True
    r2 = p2.add_run(title)
    r2.bold = True
    r2.font.size = Pt(16)
    r2.font.name = "Times New Roman"
    return p2


def add_section_heading(doc, number, title):
    """Adds a numbered section heading."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    pf.keep_with_next = True
    run = p.add_run(f"{number} {title}")
    run.bold = True
    run.font.size = Pt(14)
    run.font.name = "Times New Roman"
    return p


def add_subsection_heading(doc, number, title):
    """Adds a numbered subsection heading."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(10)
    pf.space_after = Pt(4)
    pf.keep_with_next = True
    run = p.add_run(f"{number} {title}")
    run.bold = True
    run.font.size = Pt(12)
    run.font.name = "Times New Roman"
    return p


def add_table_with_data(doc, headers, rows, caption=None, table_num=None, col_widths=None):
    """Adds a formatted table with caption above, shaded header, and centered alignment."""
    if caption and table_num:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(10)
        cap.paragraph_format.space_after = Pt(4)
        cap.paragraph_format.keep_with_next = True
        run = cap.add_run(f"Table {table_num}: {caption}")
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = "Times New Roman"

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    hdr_row = table.rows[0]
    hdr_trPr = hdr_row._tr.get_or_add_trPr()
    hdr_trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    hdr_trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    for i, header in enumerate(headers):
        cell = hdr_row.cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(10)
                run.font.name = "Times New Roman"
        set_cell_shading(cell, "D9E2F3")

    # Data rows
    for r_idx, row in enumerate(rows):
        d_row = table.rows[r_idx + 1]
        d_trPr = d_row._tr.get_or_add_trPr()
        d_trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        for c_idx, val in enumerate(row):
            cell = d_row.cells[c_idx]
            cell.text = str(val)
            for paragraph in cell.paragraphs:
                if c_idx == 0 and not any(h in headers[0].lower() for h in ["ref", "#", "no"]):
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                else:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.size = Pt(9.5)
                    run.font.name = "Times New Roman"

    if col_widths and len(col_widths) == len(headers):
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(2)
    p_after.paragraph_format.space_after = Pt(6)
    return table


def add_figure(doc, img_rel_path, caption, fig_num, width_inches=5.5):
    """Adds an image figure with centered alignment and caption below."""
    img_path = PROJECT_ROOT / img_rel_path
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(8)
    pf.space_after = Pt(4)
    pf.keep_with_next = True

    if img_path.exists():
        run = p.add_run()
        run.add_picture(str(img_path), width=Inches(width_inches))
    else:
        run = p.add_run(f"[{caption} — Image File: {img_rel_path}]")
        run.italic = True
        run.font.size = Pt(10)
        run.font.name = "Times New Roman"

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf = cap.paragraph_format
    cpf.space_before = Pt(2)
    cpf.space_after = Pt(12)
    r = cap.add_run(f"Figure {fig_num}: {caption}")
    r.bold = True
    r.font.size = Pt(11)
    r.font.name = "Times New Roman"
    return cap


# ─── CORE DOCUMENT BUILDER ───────────────────────────────────────────────────

def build_report_document(page_map=None):
    """
    Constructs the complete UROP Report document.
    If page_map is provided (from pass 1 PDF analysis), exact page numbers
    are written to the Table of Contents, List of Tables, and List of Figures.
    """
    doc = Document()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: FRONT MATTER (ROMAN NUMERAL PAGE NUMBERS)
    # ═══════════════════════════════════════════════════════════════════════
    sec1 = doc.sections[0]
    sec1.top_margin = Cm(2.54)
    sec1.bottom_margin = Cm(2.54)
    sec1.left_margin = Cm(3.17)
    sec1.right_margin = Cm(2.54)
    sec1.page_width = Cm(21.0)
    sec1.page_height = Cm(29.7)
    sec1.different_first_page_header_footer = True

    sectPr1 = sec1._sectPr
    pgNumType1 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="lowerRoman" w:start="1"/>')
    sectPr1.append(pgNumType1)

    footer1 = sec1.footer
    p_ft1 = footer1.paragraphs[0]
    p_ft1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ft1 = p_ft1.add_run()
    r_ft1.font.name = "Times New Roman"
    r_ft1.font.size = Pt(10)
    fld1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
    instr1 = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
    fld2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
    fld3 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
    r_ft1._r.extend([fld1, instr1, fld2, fld3])

    # ─────────────────────────────────────────────────────────────────────
    # TITLE PAGE (PAGE 1 - NO FOOTER DISPLAYED)
    # ─────────────────────────────────────────────────────────────────────
    add_formatted_paragraph(doc,
        "Real-Time Encrypted Traffic Classification Using\nLightweight Machine Learning Models",
        bold=True, font_size=17, alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=14, space_after=16, line_spacing=1.2)

    add_formatted_paragraph(doc, "UROP Project submitted to the",
        font_size=13, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "SRM University – AP, Andhra Pradesh",
        bold=True, font_size=13.5, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "for the partial fulfillment of the requirements to award the degree of",
        font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)

    add_formatted_paragraph(doc, "Bachelor of Technology",
        bold=True, font_size=13.5, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "in",
        font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "Computer Science and Engineering",
        bold=True, font_size=13.5, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "School of Engineering and Sciences",
        font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)

    add_formatted_paragraph(doc, "Submitted by",
        font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "Gorakala Rishik | [INSERT OFFICIAL REGISTRATION NUMBER]",
        bold=True, font_size=12.5, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)

    # University Logo
    logo_path = PROJECT_ROOT / "UROP_Report/Assets/srm_logo.png"
    if logo_path.exists():
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_before = Pt(4)
        p_logo.paragraph_format.space_after = Pt(10)
        r_logo = p_logo.add_run()
        r_logo.add_picture(str(logo_path), width=Inches(1.5))

    add_formatted_paragraph(doc, "Under the Guidance of",
        font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)

    add_formatted_paragraph(doc, "[INSERT OFFICIAL GUIDE NAME AND DESIGNATION]",
        bold=True, font_size=12.5, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    add_formatted_paragraph(doc,
        "SRM University–AP\nNeerukonda, Mangalagiri,\nGuntur, Andhra Pradesh – 522 240",
        font_size=11, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=10, line_spacing=1.15)

    add_formatted_paragraph(doc, "November, 2026",
        bold=True, font_size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER)

    # ─────────────────────────────────────────────────────────────────────
    # DECLARATION PAGE (PAGE ii)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "DECLARATION", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=24)

    add_body_text(doc,
        "I, Gorakala Rishik, hereby declare that the Undergraduate Research Opportunity Program (UROP) "
        "project report entitled \"Real-Time Encrypted Traffic Classification Using Lightweight Machine "
        "Learning Models\" submitted to SRM University – AP, Andhra Pradesh, in partial fulfillment of the "
        "requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering, "
        "is a bonafide record of original research work carried out by me under the supervision and technical "
        "guidance of [INSERT OFFICIAL GUIDE NAME AND DESIGNATION], Department of Computer Science and Engineering, "
        "School of Engineering and Sciences, SRM University-AP.")

    add_body_text(doc,
        "I further declare that this project report has not been submitted previously to any other university, "
        "college, or academic institution for the award of any degree, diploma, fellowship, or other academic title. "
        "All experimental methodologies, empirical benchmark findings, machine learning architectures, and "
        "architectural implementations presented herein reflect genuine project investigations. External concepts, "
        "literature benchmarks, standard protocols, and published research articles have been duly acknowledged and "
        "faithfully cited in the References section in compliance with academic integrity standards.")

    for _ in range(4):
        doc.add_paragraph()

    decl_left = [
        "Date:  November, 2026",
        "Place: SRM University-AP, Andhra Pradesh"
    ]
    decl_right = [
        "___________________________________",
        "Gorakala Rishik",
        "[INSERT OFFICIAL REGISTRATION NUMBER]"
    ]
    add_signature_table_2col(doc, decl_left, decl_right)

    # ─────────────────────────────────────────────────────────────────────
    # CERTIFICATE PAGE (PAGE iii)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "CERTIFICATE", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=24)

    add_body_text(doc,
        "This is to certify that the Undergraduate Research Opportunity Program (UROP) project report entitled "
        "\"Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models\" submitted by "
        "Gorakala Rishik ([INSERT OFFICIAL REGISTRATION NUMBER]) to SRM University – AP, Andhra Pradesh, in partial "
        "fulfillment of the requirements for the award of the degree of Bachelor of Technology in Computer Science "
        "and Engineering, is a bonafide record of original research work carried out under my direct supervision "
        "and professional guidance during the academic session 2025–2026.")

    add_body_text(doc,
        "The project demonstrates rigorous empirical methodology, systematic zero-payload feature extraction, "
        "session-isolated machine learning evaluation, and real-time streaming pipeline engineering. To the best of "
        "my knowledge, the results embodied in this report have not been submitted to any other university or "
        "institution for the award of any academic degree or professional certification.")

    for _ in range(5):
        doc.add_paragraph()

    cert_left = [
        "___________________________________",
        "Project Guide",
        "[INSERT OFFICIAL GUIDE NAME]",
        "[INSERT OFFICIAL GUIDE DESIGNATION]",
        "Department of Computer Science & Engineering",
        "SRM University-AP, Andhra Pradesh"
    ]
    cert_right = [
        "___________________________________",
        "Head of the Department",
        "Department of Computer Science & Engineering",
        "School of Engineering and Sciences",
        "SRM University-AP, Andhra Pradesh"
    ]
    add_signature_table_2col(doc, cert_left, cert_right)

    # ─────────────────────────────────────────────────────────────────────
    # ACKNOWLEDGEMENT PAGE (PAGE iv)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "ACKNOWLEDGEMENT", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    add_body_text(doc,
        "I would like to express my profound gratitude to my project mentor, [INSERT OFFICIAL GUIDE NAME], "
        "Department of Computer Science and Engineering, School of Engineering and Sciences, SRM University-AP, "
        "for insightful guidance, continuous encouragement, and constant technical support throughout the course "
        "of this Undergraduate Research Opportunity Program (UROP) project. The patience, intellectual clarity, "
        "and constructive critiques inspired me to pursue rigorous empirical network research, maintain strict "
        "data-splitting hygiene, and develop reproducible machine learning evaluation methodologies.")

    add_body_text(doc,
        "I extend my sincere thanks to the Department of Computer Science and Engineering and the School of "
        "Engineering and Sciences, SRM University-AP, for providing the academic infrastructure, state-of-the-art "
        "computing laboratories, and supportive research environment necessary to carry out this investigation. "
        "I am grateful to the faculty members, evaluators, and laboratory technical staff for their constructive "
        "recommendations during project progress reviews.")

    add_body_text(doc,
        "I also thank my fellow student peers and colleagues for their valuable discussions, collaborative feedback, "
        "and intellectual exchange that helped refine both the technical implementation and the documentation "
        "structure of this academic report. Finally, I express my deepest appreciation to my family for their "
        "unconditional support and encouragement throughout my academic pursuits.")

    p_sig_a = doc.add_paragraph()
    p_sig_a.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig_a.paragraph_format.space_before = Pt(18)
    r_a = p_sig_a.add_run("Gorakala Rishik\n[INSERT OFFICIAL REGISTRATION NUMBER]")
    r_a.font.name = "Times New Roman"
    r_a.font.size = Pt(11)
    r_a.bold = True

    # ─────────────────────────────────────────────────────────────────────
    # ABSTRACT PAGE (PAGE v - COMPACT TO FIT ON EXACTLY ONE PAGE)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "ABSTRACT", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=14)

    add_body_text(doc,
        "The pervasive adoption of modern encryption protocols—including Transport Layer Security (TLS 1.3), "
        "Quick UDP Internet Connections (QUIC), and wire-speed tunneling mechanisms such as WireGuard and "
        "Cloudflare WARP—has fundamentally neutralized traditional Deep Packet Inspection (DPI) methods. "
        "Contemporary network defense architectures require traffic classification capabilities that preserve user "
        "privacy, operate at wire speed, and demonstrate robustness against shifting network environments.",
        space_after=4, line_spacing=1.3)

    add_body_text(doc,
        "This project presents an end-to-end, real-time encrypted traffic classification framework designed "
        "under a zero-payload privacy contract. The system operates exclusively on statistical transport-layer "
        "metadata (packet sizes, inter-arrival times, burst structures, and directional flow metrics) without "
        "inspecting application payloads, decrypting cryptographic envelopes, or analyzing ephemeral handshake tokens. "
        "The models are evaluated on a controlled multi-environment hybrid benchmark (dataset_v2) consisting of "
        "301 total flows across 150 independent capture sessions: 121 genuine physical Wi-Fi (802.11ax) flows "
        "combined with 180 controlled statistical feature perturbations representing Ethernet, Cellular LTE, "
        "and network impairments across six application classes (Web, Video, Messaging, VoIP, File Transfer, Other).",
        space_after=4, line_spacing=1.3)

    add_body_text(doc,
        "Under strict group-aware session isolation (GroupShuffleSplit) preventing cross-partition session leakage, "
        "LightGBM was identified as the validation-selected model (Validation Macro-F1 = 0.5664, Test Macro-F1 = "
        "0.5474), while Decision Tree established superior operational latency (P50 = 0.0578 ms, model footprint = "
        "9.58 KB). A systematic feature dimensionality analysis revealed that a compact 3-feature subset achieves "
        "0.6738 test Macro-F1, significantly outperforming the full 84-feature matrix (0.2985 test Macro-F1). Early "
        "packet triage demonstrates that classification at horizon N = 3 packets achieves 0.6111 Macro-F1 within "
        "84.33 ms total latency, with physical wire delay accounting for over 76% (and over 99% in full flows) of total "
        "classification latency. Selective classification at validation-calibrated threshold tau* = 0.70 monotonically "
        "reduces error rates from 45.83% to 26.92% on accepted traffic. The streaming pipeline was verified under live "
        "promiscuous capture with zero packet drops, zero processing failures, and guaranteed zero payload retention.",
        space_after=8, line_spacing=1.3)

    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.space_before = Pt(4)
    p_kw.paragraph_format.space_after = Pt(4)
    p_kw.paragraph_format.line_spacing = 1.2
    r_kwh = p_kw.add_run("Keywords: ")
    r_kwh.bold = True
    r_kwh.font.size = Pt(10.5)
    r_kwh.font.name = "Times New Roman"
    r_kwt = p_kw.add_run(
        "Encrypted Traffic Classification, Zero-Payload Metadata, Network Environment Shift, "
        "Early Traffic Triage, Selective Classification, Physical Wire Delay, LightGBM, Reproducible Machine Learning."
    )
    r_kwt.font.size = Pt(10.5)
    r_kwt.font.name = "Times New Roman"
    r_kwt.italic = True

    # ─────────────────────────────────────────────────────────────────────
    # ABBREVIATIONS PAGE (PAGE vi)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "ABBREVIATIONS", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    abbr_headers = ["Abbreviation", "Expansion"]
    abbr_rows = [
        ["API", "Application Programming Interface"],
        ["AX", "IEEE 802.11ax High-Efficiency Wireless Standard (Wi-Fi 6)"],
        ["BPF", "Berkeley Packet Filter"],
        ["CART", "Classification and Regression Trees"],
        ["CIC", "Canadian Institute for Cybersecurity"],
        ["CNN", "Convolutional Neural Network"],
        ["DPI", "Deep Packet Inspection"],
        ["DT", "Decision Tree"],
        ["ECE", "Expected Calibration Error"],
        ["F1", "Macro-Averaged F1-Score (Harmonic Mean of Precision and Recall)"],
        ["GBDT", "Gradient Boosted Decision Tree"],
        ["GSS", "Group Shuffle Split (Session-Isolated Splitting Strategy)"],
        ["IANA", "Internet Assigned Numbers Authority"],
        ["IAT", "Inter-Arrival Time"],
        ["IP", "Internet Protocol"],
        ["LGBM", "Light Gradient Boosting Machine"],
        ["LR", "Logistic Regression"],
        ["LTE", "Long-Term Evolution (4G Cellular Standard)"],
        ["ML", "Machine Learning"],
        ["MTU", "Maximum Transmission Unit"],
        ["Npcap", "Windows Packet Capture Library and Kernel Driver"],
        ["PCAP", "Packet Capture (Standard Network Trace File Format)"],
        ["QUIC", "Quick UDP Internet Connections (RFC 9000)"],
        ["RF", "Random Forest"],
        ["RFC", "Request for Comments (Internet Engineering Task Force Standard)"],
        ["SNI", "Server Name Indication (TLS Extension)"],
        ["SOC", "Security Operations Center"],
        ["SVM", "Support Vector Machine"],
        ["TCP", "Transmission Control Protocol"],
        ["TLS", "Transport Layer Security (RFC 8446)"],
        ["UDP", "User Datagram Protocol"],
        ["UROP", "Undergraduate Research Opportunity Program"],
        ["VoIP", "Voice over Internet Protocol"],
        ["VPN", "Virtual Private Network"],
        ["WARP", "Cloudflare WireGuard-Based Tunnel Service"],
    ]
    add_table_with_data(doc, abbr_headers, abbr_rows, "List of Abbreviations", "A.1", col_widths=[1.5, 4.5])

    # ─────────────────────────────────────────────────────────────────────
    # TABLE OF CONTENTS (PAGE vii)
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "CONTENTS", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    def gp(key, default_val):
        if page_map and key in page_map:
            return page_map[key]
        return default_val

    toc_items = [
        ("", "Acknowledgement", gp("Acknowledgement", "iv")),
        ("", "Abstract", gp("Abstract", "v")),
        ("", "Abbreviations", gp("Abbreviations", "vi")),
        ("", "List of Tables", gp("List of Tables", "ix")),
        ("", "List of Figures", gp("List of Figures", "x")),
        ("1", "INTRODUCTION TO THE PROJECT", gp("1", "1")),
        ("1.1", "Introduction", gp("1.1", "1")),
        ("1.2", "Background of Encrypted Network Traffic", gp("1.2", "1")),
        ("1.3", "Problem Statement", gp("1.3", "2")),
        ("1.4", "Objectives of the Project", gp("1.4", "2")),
        ("1.5", "Scope of the Project", gp("1.5", "3")),
        ("1.6", "Organization of the Report", gp("1.6", "4")),
        ("2", "MOTIVATION", gp("2", "5")),
        ("2.1", "Motivation", gp("2.1", "5")),
        ("2.2", "Limitations of Traditional Deep Packet Inspection", gp("2.2", "5")),
        ("2.3", "Need for Zero-Payload Traffic Classification", gp("2.3", "6")),
        ("2.4", "Need for Lightweight Machine Learning", gp("2.4", "6")),
        ("2.5", "Research Challenges", gp("2.5", "6")),
        ("2.6", "Project Contributions", gp("2.6", "7")),
        ("3", "LITERATURE SURVEY", gp("3", "9")),
        ("3.1", "Introduction", gp("3.1", "9")),
        ("3.2", "Existing Encrypted Traffic Classification Approaches", gp("3.2", "9")),
        ("3.3", "Machine Learning-Based Traffic Classification", gp("3.3", "10")),
        ("3.4", "Flow-Based Statistical Feature Extraction", gp("3.4", "10")),
        ("3.5", "Early Traffic Classification", gp("3.5", "10")),
        ("3.6", "Research Gaps", gp("3.6", "11")),
        ("3.7", "Comparative Literature Survey", gp("3.7", "11")),
        ("4", "DESIGN AND METHODOLOGY", gp("4", "13")),
        ("4.1", "Proposed System Overview", gp("4.1", "13")),
        ("4.2", "System Architecture", gp("4.2", "13")),
        ("4.3", "Dataset Collection Methodology", gp("4.3", "14")),
        ("4.4", "Dataset Description and Provenance", gp("4.4", "14")),
        ("4.5", "Traffic Flow Construction", gp("4.5", "15")),
        ("4.6", "Zero-Payload Feature Extraction", gp("4.6", "15")),
        ("4.7", "Feature Engineering", gp("4.7", "15")),
        ("4.8", "Machine Learning Models", gp("4.8", "16")),
        ("4.9", "Training and Evaluation Methodology", gp("4.9", "16")),
        ("4.10", "Evaluation Metrics", gp("4.10", "17")),
        ("4.11", "Early Prediction Methodology", gp("4.11", "17")),
        ("4.12", "Selective Classification Methodology", gp("4.12", "17")),
        ("4.13", "Generalization Experiments", gp("4.13", "17")),
        ("4.14", "Research Workflow", gp("4.14", "17")),
        ("5", "IMPLEMENTATION", gp("5", "19")),
        ("5.1", "Development Environment", gp("5.1", "19")),
        ("5.2", "Network Packet Capture", gp("5.2", "19")),
        ("5.3", "Bidirectional Flow Management", gp("5.3", "19")),
        ("5.4", "Statistical Feature Extraction", gp("5.4", "19")),
        ("5.5", "Machine Learning Model Integration", gp("5.5", "20")),
        ("5.6", "Classification and Confidence Handling", gp("5.6", "20")),
        ("5.7", "Real-Time Processing Pipeline", gp("5.7", "20")),
        ("5.8", "Local API and Event Storage", gp("5.8", "20")),
        ("5.9", "Monitoring Dashboard", gp("5.9", "20")),
        ("5.10", "Error Handling and Fail-Closed Design", gp("5.10", "21")),
        ("5.11", "Dataset V3 Physical Capture Validation", gp("5.11", "21")),
        ("6", "HARDWARE / SOFTWARE TOOLS USED", gp("6", "22")),
        ("6.1", "Hardware Requirements", gp("6.1", "22")),
        ("6.2", "Software Requirements", gp("6.2", "22")),
        ("6.3", "Programming Languages", gp("6.3", "23")),
        ("6.4", "Machine Learning Libraries", gp("6.4", "23")),
        ("6.5", "Network Capture Technologies", gp("6.5", "23")),
        ("6.6", "Development Tools", gp("6.6", "23")),
        ("6.7", "Testing Tools", gp("6.7", "23")),
        ("7", "RESULTS AND DISCUSSION", gp("7", "24")),
        ("7.1", "Experimental Setup", gp("7.1", "24")),
        ("7.2", "Dataset Statistics", gp("7.2", "24")),
        ("7.3", "Baseline Model Comparison", gp("7.3", "24")),
        ("7.4", "Feature Selection and Ablation", gp("7.4", "26")),
        ("7.5", "Cross-Environment Generalization", gp("7.5", "27")),
        ("7.6", "Network Condition Robustness", gp("7.6", "28")),
        ("7.7", "Tunnel Direction Shift", gp("7.7", "28")),
        ("7.8", "Early Prediction Results", gp("7.8", "29")),
        ("7.9", "Selective Classification Results", gp("7.9", "30")),
        ("7.10", "Computational Efficiency", gp("7.10", "31")),
        ("7.11", "Real-Time System Validation", gp("7.11", "32")),
        ("7.12", "Discussion of Findings", gp("7.12", "33")),
        ("7.13", "Limitations and Threats to Validity", gp("7.13", "34")),
        ("8", "CONCLUSION", gp("8", "35")),
        ("8.1", "Project Summary", gp("8.1", "35")),
        ("8.2", "Research Contributions", gp("8.2", "35")),
        ("8.3", "Limitations", gp("8.3", "35")),
        ("8.4", "Scope of Further Work", gp("8.4", "35")),
        ("", "REFERENCES", gp("REFERENCES", "37")),
        ("", "LIST OF PUBLICATIONS", gp("LIST OF PUBLICATIONS", "39")),
    ]

    for num, title, page in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.line_spacing = 1.1

        if num and not "." in num:
            run_title = p.add_run(f"CHAPTER {num}   {title}")
            run_title.bold = True
        elif num:
            run_title = p.add_run(f"    {num}  {title}")
        else:
            run_title = p.add_run(f"{title}")
            run_title.bold = True
        run_title.font.size = Pt(10.5)
        run_title.font.name = "Times New Roman"

        dots_count = max(4, 78 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.bold = True if (not num or not "." in num) else False
        r_pg.font.size = Pt(10.5)
        r_pg.font.name = "Times New Roman"

    # ─────────────────────────────────────────────────────────────────────
    # LIST OF TABLES
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "LIST OF TABLES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    tables_list = [
        ("3.1", "Comparative Literature Survey Summary", gp("T_3.1", "12")),
        ("4.1", "Dataset Composition and Provenance Summary", gp("T_4.1", "14")),
        ("4.2", "Zero-Payload Feature Categories and Descriptions", gp("T_4.2", "15")),
        ("4.3", "Machine Learning Model Hyperparameters", gp("T_4.3", "16")),
        ("6.1", "Hardware Requirements and Specifications", gp("T_6.1", "22")),
        ("6.2", "Software Requirements and Dependencies", gp("T_6.2", "22")),
        ("7.1", "Baseline Model Comparison Results (EXP-R09)", gp("T_7.1", "24")),
        ("7.2", "Feature Count Tradeoff Results (EXP-R10)", gp("T_7.2", "26")),
        ("7.3", "Feature Family Ablation Results (EXP-R10)", gp("T_7.3", "27")),
        ("7.4", "Cross-Environment Generalization Results (EXP-R11)", gp("T_7.4", "28")),
        ("7.5", "Early Prediction Results Across Packet Horizons (EXP-R12)", gp("T_7.5", "30")),
        ("7.6", "Selective Classification Results at Different Thresholds (EXP-R13)", gp("T_7.6", "30")),
        ("7.7", "Computational Latency Measurements (EXP-R14)", gp("T_7.7", "31")),
        ("7.8", "Real-Time Pipeline Validation Results (EXP-R15)", gp("T_7.8", "32")),
    ]

    for num, title, page in tables_list:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        run_title = p.add_run(f"Table {num}:  {title}")
        run_title.font.size = Pt(11)
        run_title.font.name = "Times New Roman"
        dots_count = max(4, 76 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.font.size = Pt(11)
        r_pg.font.name = "Times New Roman"

    # ─────────────────────────────────────────────────────────────────────
    # LIST OF FIGURES
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "LIST OF FIGURES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    figures_list = [
        ("4.1", "End-to-End System Architecture", gp("F_4.1", "13")),
        ("4.2", "Research Methodology Workflow", gp("F_4.2", "18")),
        ("5.1", "Real-Time Streaming Pipeline and Cybersecurity SOC Architecture", gp("F_5.1", "21")),
        ("7.1", "Baseline Model Comparison — Validation and Test Macro-F1 Scores", gp("F_7.1", "25")),
        ("7.2", "Decision Tree and Random Forest Confusion Matrices on Test Split", gp("F_7.2", "26")),
        ("7.3", "Feature Count Tradeoff Curve and Pareto Frontier", gp("F_7.3", "27")),
        ("7.4", "Cross-Environment Generalization Across Distribution Shift Regimes", gp("F_7.4", "28")),
        ("7.5", "Asymmetric Tunnel Generalization Failure Under WireGuard Encapsulation", gp("F_7.5", "29")),
        ("7.6", "Early Prediction Performance Across Packet Observation Horizons", gp("F_7.6", "30")),
        ("7.7", "Selective Classification Coverage vs. Selective Accuracy Tradeoff", gp("F_7.7", "31")),
        ("7.8", "Computational Latency Distribution Across Pipeline Stages", gp("F_7.8", "32")),
        ("7.9", "Confidence Calibration Curve and Expected Calibration Error", gp("F_7.9", "33")),
    ]

    for num, title, page in figures_list:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        run_title = p.add_run(f"Figure {num}:  {title}")
        run_title.font.size = Pt(11)
        run_title.font.name = "Times New Roman"
        dots_count = max(4, 76 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.font.size = Pt(11)
        r_pg.font.name = "Times New Roman"

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: MAIN CHAPTERS & BACK MATTER (ARABIC PAGE NUMBERS 1, 2, 3...)
    # ═══════════════════════════════════════════════════════════════════════
    sec2 = doc.add_section()
    sec2.top_margin = Cm(2.54)
    sec2.bottom_margin = Cm(2.54)
    sec2.left_margin = Cm(3.17)
    sec2.right_margin = Cm(2.54)
    sec2.page_width = Cm(21.0)
    sec2.page_height = Cm(29.7)
    sec2.different_first_page_header_footer = False

    sectPr2 = sec2._sectPr
    pgNumType2 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="decimal" w:start="1"/>')
    sectPr2.append(pgNumType2)

    footer2 = sec2.footer
    footer2.is_linked_to_previous = False
    p_ft2 = footer2.paragraphs[0]
    p_ft2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ft2 = p_ft2.add_run()
    r_ft2.font.name = "Times New Roman"
    r_ft2.font.size = Pt(10)
    fld4 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
    instr2 = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
    fld5 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
    fld6 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
    r_ft2._r.extend([fld4, instr2, fld5, fld6])

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 1 — INTRODUCTION TO THE PROJECT
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 1, "INTRODUCTION TO THE PROJECT")

    add_section_heading(doc, "1.1", "Introduction")
    add_body_text(doc,
        "Network traffic classification is an essential capability for modern network management, quality of service "
        "(QoS) provisioning, cybersecurity threat detection, and automated incident response. Network operators "
        "rely on traffic classification to enforce service-level agreements, identify bandwidth-intensive streaming "
        "services, detect malicious command-and-control communication, and prioritize latency-critical real-time flows. "
        "Historically, traffic classification relied on simple port-based lookups and, subsequently, on Deep Packet "
        "Inspection (DPI) techniques that examine application-layer payload byte signatures.")

    add_body_text(doc,
        "Over the past decade, however, the landscape of digital network communications has undergone a fundamental "
        "transformation. Today, over 95% of web and enterprise traffic is encrypted using modern cryptographic protocols "
        "such as Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC), and high-performance VPN "
        "tunnels like WireGuard. These protocols intentionally obscure packet contents, randomize application signatures, "
        "and encrypt transport parameters. As a result, traditional inspection paradigms have become obsolete, creating "
        "an urgent operational requirement for zero-payload classification systems that operate exclusively on observable "
        "transport-layer statistical dynamics.")

    add_section_heading(doc, "1.2", "Background of Encrypted Network Traffic")
    add_body_text(doc,
        "The historical progression of network security protocols reflects a continuous migration toward comprehensive "
        "end-to-end privacy. In legacy TLS 1.2, cleartext handshakes exposed server certificates and Server Name "
        "Indication (SNI) extensions, providing passive network monitors with clear indicators of destination domain "
        "names and service identities. With the formal ratification of TLS 1.3 (RFC 8446) and Encrypted Client Hello (ECH), "
        "handshake metadata is fully encrypted after the initial greeting exchange.")

    add_body_text(doc,
        "Concurrently, the emergence of QUIC (RFC 9000)—which serves as the underlying transport foundation for HTTP/3—"
        "encapsulates encrypted transport metadata within User Datagram Protocol (UDP) datagrams. QUIC encrypts packet "
        "header flags, packet sequence numbers, and stream identifiers, preventing passive observers from tracking TCP "
        "window states or sequence gaps. Furthermore, commercial tunneling services such as Cloudflare WARP and corporate "
        "WireGuard tunnels encapsulate entire IP packets within standardized cryptographic outer datagrams, clamping "
        "Maximum Transmission Unit (MTU) boundaries to 1280 bytes and obscuring internal application characteristics. "
        "Network defenders must therefore characterize traffic behavior without accessing payload bytes.")

    add_section_heading(doc, "1.3", "Problem Statement")
    add_body_text(doc,
        "Accurately and rapidly classifying encrypted network traffic under dynamic physical and logical network environment "
        "shifts—without inspecting packet payloads, violating user privacy, or incurring unsustainable computational latency—"
        "remains an unsolved challenge in applied computer networks. Existing machine learning approaches exhibit critical "
        "methodological deficiencies:", indent=False)

    add_bullet_item(doc,
        "Over-optimistic evaluation resulting from naive random packet or flow splitting that permits identical user "
        "sessions to span both training and evaluation sets, leading to severe data leakage and inflated performance claims.",
        bold_prefix="Session Leakage Bias: ")
    add_bullet_item(doc,
        "Catastrophic generalization failure when models trained on unencapsulated direct Wi-Fi traffic are deployed "
        "across alternate transmission media (Ethernet, Cellular LTE) or encountering VPN tunneling encapsulations.",
        bold_prefix="Environment Shift Fragility: ")
    add_bullet_item(doc,
        "Failure to account for physical wire delay in early classification systems, where prior studies report sub-millisecond "
        "algorithmic inference while ignoring the hundreds of milliseconds required for physical packets to arrive over the wire.",
        bold_prefix="Wire Delay Conflation: ")
    add_bullet_item(doc,
        "Uncalibrated model confidence resulting in brittle binary decisions that cannot distinguish between high-certainty "
        "predictions and ambiguous flows requiring secondary inspection.",
        bold_prefix="Uncalibrated Decision Making: ")

    add_section_heading(doc, "1.4", "Objectives of the Project")
    add_body_text(doc,
        "To resolve these fundamental challenges, this UROP project establishes the following specific research and engineering objectives:",
        indent=False)

    objectives = [
        ("Zero-Payload Architectural Design: ",
         "Design and implement a real-time network traffic classification framework operating strictly on transport-layer "
         "metadata (packet lengths, inter-arrival times, burst counts, and directional ratios), guaranteeing zero inspection, "
         "storage, or leakage of application payloads."),
        ("Multi-Environment Benchmark Construction: ",
         "Construct a rigorous hybrid evaluation benchmark (dataset_v2) combining genuine physical 802.11ax Wi-Fi traffic with "
         "controlled statistical feature perturbations representing Ethernet, Cellular LTE, and network impairment regimes."),
        ("Strict Group-Aware Evaluation: ",
         "Implement group-aware session splitting (GroupShuffleSplit) to enforce strict isolation between training, validation, "
         "and testing partitions, eliminating session-level data leakage."),
        ("Dimensionality and Ablation Analysis: ",
         "Perform systematic feature count tradeoff and feature family ablation studies to identify minimal, robust feature subsets "
         "that mitigate the curse of dimensionality on tabular flow features."),
        ("Early Triage and Physical Latency Characterization: ",
         "Evaluate early classification at packet horizons N = 3, 5, 10, 20, 30, and 50, explicitly measuring physical radio "
         "arrival delays separately from algorithmic feature extraction and model inference times."),
        ("Selective Classification with Risk-Coverage Gating: ",
         "Develop a validation-calibrated selective classification mechanism that routes ambiguous traffic to secondary inspection, "
         "monotonically reducing classification error on accepted flows."),
        ("Production-Ready Real-Time Pipeline: ",
         "Build an asynchronous, non-blocking streaming classification pipeline featuring promiscuous packet capture, "
         "bidirectional flow state management, local SQLite event logging, and an 8-tab Streamlit SOC dashboard."),
        ("Ground-Truth Process Attribution: ",
         "Architect a Windows IP Helper API process-to-socket attribution subsystem for Dataset V3 to establish provable "
         "ground truth on live endpoint traffic without inspecting payload contents.")
    ]
    for pfx, desc in objectives:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    add_section_heading(doc, "1.5", "Scope of the Project")
    add_body_text(doc,
        "The scope of this project encompasses endpoint and gateway network traffic classification across six major application "
        "classes: Web Browsing, Video Streaming, Messaging, Voice over IP (VoIP), File Transfer, and Other Background traffic. "
        "The empirical investigation focuses on lightweight tabular machine learning models (Logistic Regression, Decision Trees, "
        "Random Forests, and LightGBM) that execute within sub-millisecond inference budgets on standard edge hardware. Deep learning "
        "architectures requiring specialized GPU accelerators or multi-gigabyte memory footprints are explicitly excluded to maintain "
        "real-time edge deployability.")

    add_body_text(doc,
        "The project rigorously evaluates model robustness across nine distinct distribution shift regimes, including temporal "
        "drift, unseen physical media perturbations, network impairments, and bidirectional WireGuard tunnel encapsulation. All "
        "empirical findings are supported by frozen configuration registries, automated unit test suites, and cryptographic data "
        "manifests ensuring end-to-end research reproducibility.")

    add_section_heading(doc, "1.6", "Organization of the Report")
    add_body_text(doc,
        "The remainder of this report is organized into seven subsequent chapters: Chapter 2 discusses the technical motivation, "
        "limitations of deep packet inspection, and core project contributions. Chapter 3 surveys related academic literature, "
        "evaluates machine learning methodologies, and presents a comparative literature matrix. Chapter 4 details the design and "
        "methodology, including the system architecture, dataset provenance, zero-payload feature extraction, and evaluation protocols. "
        "Chapter 5 presents the implementation architecture, detailing the packet sniffer, flow manager, real-time pipeline, SOC console, "
        "and Dataset V3 attribution subsystem. Chapter 6 describes the hardware, software, and development toolchain. Chapter 7 "
        "reports the comprehensive empirical results from experiments EXP-R09 through EXP-R15, accompanied by detailed analytical "
        "discussions. Finally, Chapter 8 summarizes the research conclusions, highlights limitations, and outlines future research directions.")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 2 — MOTIVATION
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 2, "MOTIVATION")

    add_section_heading(doc, "2.1", "Motivation")
    add_body_text(doc,
        "The motivation for this research stems from the critical contradiction between the necessity for network traffic "
        "observability and the non-negotiable requirement for end-to-end cryptographic privacy. Modern enterprise networks, "
        "telecommunication providers, and national critical infrastructure operators must maintain real-time situational awareness "
        "to protect against distributed denial-of-service (DDoS) attacks, detect advanced persistent threat (APT) beaconing, ensure "
        "equitable bandwidth distribution, and enforce network security policies. However, achieving this visibility cannot rely "
        "on intercepting, decrypting, or storing sensitive personal and organizational data.")

    add_body_text(doc,
        "Furthermore, modern cloud infrastructure and software-defined wide area networks (SD-WAN) routinely route traffic across "
        "heterogeneous physical transmission paths—switching seamlessly between Wi-Fi, gigabit Ethernet, and 4G/5G cellular connections "
        "while wrapping data in encrypted overlay tunnels. Network classification models deployed in real-world environments must "
        "therefore withstand severe distribution shifts without suffering silent accuracy collapse.")

    add_section_heading(doc, "2.2", "Limitations of Traditional Deep Packet Inspection")
    add_body_text(doc,
        "Traditional Deep Packet Inspection (DPI) architectures inspect application-layer payload headers, searching for deterministic "
        "regular expressions or known magic-byte signatures. While effective for unencrypted protocols (such as HTTP/1.1 or plain FTP), "
        "DPI exhibits critical and insurmountable limitations in contemporary network environments:", indent=False)

    dpi_limits = [
        ("Cryptographic Blindness: ",
         "TLS 1.3, QUIC, and modern VPN protocols utilize authenticated encryption with associated data (AEAD) ciphers (e.g., "
         "AES-256-GCM, ChaCha20-Poly1305) that render application payloads mathematically indistinguishable from pseudorandom noise."),
        ("Legal and Regulatory Non-Compliance: ",
         "Inspecting or decrypting user payloads violates global privacy regulations, including the European Union General Data "
         "Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and healthcare HIPAA regulations."),
        ("Computational Inefficiency: ",
         "Performing TLS man-in-the-middle (MitM) decryption requires installing enterprise root certificates, consuming massive "
         "CPU cycles for cryptographic handshakes, and introducing multi-millisecond latency penalties incompatible with wire-speed routing."),
        ("Vulnerability to Evasion: ",
         "Adversaries easily circumvent byte-pattern signatures through payload padding, protocol obfuscation, and dynamic port switching.")
    ]
    for pfx, desc in dpi_limits:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    add_section_heading(doc, "2.3", "Need for Zero-Payload Traffic Classification")
    add_body_text(doc,
        "Zero-payload traffic classification eliminates payload inspection entirely by relying strictly on observable metadata "
        "generated by the physical and transport dynamics of the communication session. Even when application content is fully "
        "encrypted, the underlying communication patterns remain constrained by the application's behavioral mechanics. For example, "
        "interactive video streaming exhibits continuous downlink bursts separated by regular keyframe intervals; web browsing generates "
        "sparse request-response bursts with high client-to-server asymmetry; and VoIP sessions produce steady, periodic, bidirectional "
        "micro-packets. By extracting statistical features exclusively from packet sizes, inter-arrival times, and directional byte "
        "ratios, zero-payload systems preserve cryptographic integrity while providing high classification utility.")

    add_section_heading(doc, "2.4", "Need for Lightweight Machine Learning")
    add_body_text(doc,
        "While deep neural networks (such as 1D/2D CNNs, LSTMs, and Transformer datagram encoders) have demonstrated high benchmark "
        "scores in offline academic evaluations, their practical deployment at the network edge is severely constrained. Deep learning "
        "models require tens to hundreds of megabytes of parameter memory, necessitate specialized GPU or NPU hardware accelerators, "
        "and consume several milliseconds per inference. In contrast, line-rate network appliances must process thousands of concurrent "
        "flows per second with sub-millisecond latency budgets.")

    add_body_text(doc,
        "Lightweight machine learning algorithms—specifically Decision Trees, Random Forests, and Gradient Boosted Decision Trees "
        "(LightGBM)—offer decisive advantages for edge deployment. They operate on tabular statistical vectors, require kilobytes of "
        "memory, execute inferences in microseconds on standard commodity CPUs, and provide intrinsic feature importance rankings that "
        "facilitate operational auditing and explainability.")

    add_section_heading(doc, "2.5", "Research Challenges")
    add_body_text(doc,
        "Designing, validating, and deploying a robust zero-payload traffic classifier entails addressing four foundational research challenges:",
        indent=False)

    challenges = [
        ("Session-Level Data Leakage: ",
         "Standard cross-validation randomly assigns flows to train and test partitions. When flows originating from the same browsing "
         "session appear in both splits, models memorize session-specific IP addresses, port ranges, and exact timing artifacts rather "
         "than learning generalizable application behavior, inflating reported F1-scores by up to 30%."),
        ("Asymmetric Tunnel Shift: ",
         "VPN tunneling encapsulates diverse transport packets into uniform UDP envelopes and clamps MTU sizes. Understanding how "
         "direct models behave under encapsulation—and why tunnel-trained models transfer robustly to direct traffic—requires deep empirical study."),
        ("Physical Wire Delay Dominance: ",
         "In real-world networks, classification cannot occur until physical packets traverse the transmission medium. Isolating algorithmic "
         "inference latency from physical radio arrival delays is essential for realistic early-triage engineering."),
        ("Confidence Calibration under Ambiguity: ",
         "Standard softmax outputs produce uncalibrated probabilities that tend to be overconfident on out-of-distribution traffic. A principled "
         "abstention mechanism is required to gate automated actions.")
    ]
    for pfx, desc in challenges:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    add_section_heading(doc, "2.6", "Project Contributions")
    add_body_text(doc,
        "This project delivers eight concrete scientific and engineering contributions to the field of encrypted traffic analysis:",
        indent=False)

    contribs = [
        ("Zero-Payload Streaming Pipeline: ",
         "Engineered an end-to-end, privacy-preserving classification pipeline that ingests live network packets, extracts 84 transport-layer "
         "statistical features, executes lightweight ML inference, and renders security telemetry on a Streamlit SOC dashboard with zero packet drops."),
        ("Multi-Environment Hybrid Benchmark: ",
         "Constructed dataset_v2 (301 flows, 150 sessions), establishing a reproducible benchmark combining physical 802.11ax Wi-Fi traffic with "
         "controlled statistical perturbations representing Ethernet, Cellular LTE, and network impairment regimes."),
        ("Strict Group-Aware Evaluation Protocol: ",
         "Enforced group-aware session isolation (GroupShuffleSplit, 5 splits) eliminating cross-partition session leakage, establishing a realistic "
         "baseline where LightGBM was selected as the validation winner (Val F1 = 0.5664, Test F1 = 0.5474)."),
        ("Compact Feature Dimensionality Discovery: ",
         "Demonstrated that a minimal 3-feature subset (Directional packet and byte ratios) achieves 0.6738 test Macro-F1, outperforming the full "
         "84-feature matrix (0.2985 test Macro-F1) by eliminating the curse of dimensionality on tabular flow features."),
        ("Asymmetric Tunnel Generalization Analysis: ",
         "Uncovered and documented an asymmetric generalization phenomenon where models trained on WireGuard tunneled traffic transfer perfectly "
         "to direct traffic (1.0000 Macro-F1), whereas direct-traffic models collapse under tunnel encapsulation (0.3407 Macro-F1)."),
        ("Physical Wire Delay Characterization: ",
         "Separated physical wire arrival delay from computational inference latency across seven observation horizons, demonstrating that "
         "physical wire transit accounts for over 76% of early triage latency and over 99% of full-flow classification latency."),
        ("Validation-Calibrated Selective Classification: ",
         "Implemented a confidence-gated abstention mechanism that monotonically reduces test error rates from 45.83% to 26.92% at threshold tau* = 0.70 "
         "while maintaining 54.17% coverage."),
        ("Ground-Truth Process Attribution Subsystem: ",
         "Designed and validated a Windows IP Helper API attribution engine for Dataset V3, tracking socket table snapshots at 150 ms intervals "
         "to establish verifiable process-to-flow ground truth on live traffic.")
    ]
    for pfx, desc in contribs:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 3 — LITERATURE SURVEY
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 3, "LITERATURE SURVEY")

    add_section_heading(doc, "3.1", "Introduction")
    add_body_text(doc,
        "The discipline of network traffic classification has evolved through three distinct technological generations over the past three "
        "decades. The first generation relied on deterministic port numbers assigned by the Internet Assigned Numbers Authority (IANA). "
        "The second generation utilized Deep Packet Inspection (DPI) to match application signatures against unencrypted payload byte streams. "
        "The third and current generation leverages statistical machine learning and deep representation learning on encrypted packet headers. "
        "This chapter surveys the foundational and recent academic literature across these paradigms, identifies prevailing methodological gaps, "
        "and contextualizes the contributions of this research.")

    add_section_heading(doc, "3.2", "Existing Encrypted Traffic Classification Approaches")
    add_body_text(doc,
        "Moore and Zuev [1] pioneered the application of statistical machine learning to internet traffic classification using Bayesian analysis "
        "techniques on Cambridge network traces. Their seminal work established that coarse transport-layer metrics—such as flow duration, packet "
        "inter-arrival times, and Fourier transforms of packet lengths—carry sufficient discriminative entropy to classify application types "
        "without inspecting packet payloads. However, early studies predominantly evaluated models on unencrypted academic traces under random "
        "sampling conditions that introduced substantial session-level data leakage.")

    add_body_text(doc,
        "With the proliferation of TLS encryption, Anderson and McGrew [2] introduced machine learning models trained on millions of enterprise "
        "TLS flows. Their framework combined observable TLS handshake metadata (cipher suite offerings, client extensions, certificate chain lengths) "
        "with sequence-of-packet-lengths-and-times (SPLT) features, achieving over 93% accuracy in malware detection. Nevertheless, the recent adoption "
        "of TLS 1.3 and Encrypted Client Hello (ECH) has encrypted the very handshake fields upon which their feature representations relied.")

    add_section_heading(doc, "3.3", "Machine Learning-Based Traffic Classification")
    add_body_text(doc,
        "In a comprehensive survey, Rezaei and Liu [4] reviewed the spectrum of machine learning and deep learning methodologies applied to "
        "encrypted traffic analysis. They observed that while ensemble tree methods (Random Forests and Gradient Boosted Decision Trees) excel on "
        "tabular statistical flow features, deep neural architectures—including 1D/2D Convolutional Neural Networks [3], Recurrent Neural Networks, "
        "and pre-trained datagram Transformers such as ET-BERT [6]—have emerged as popular research directions.")

    add_body_text(doc,
        "Wang et al. [3] proposed end-to-end encrypted traffic classification using 1D Convolutional Neural Networks operating directly on raw "
        "packet byte sequences, achieving 99.4% accuracy on the ISCX-VPN-2016 benchmark dataset. Similarly, Lin et al. [6] developed ET-BERT, "
        "a contextualized datagram representation model pre-trained on massive packet corpora that achieved greater than 97% F1-score across "
        "encrypted and VPN traffic. However, as documented by Arp et al. [7] and Pendlebury et al. [12], deep learning models frequently memorize "
        "spurious artifacts (such as ephemeral session IDs or MAC addresses) when train/test partitions share temporal or environmental overlap. "
        "Moreover, the gigabyte memory footprints and multi-millisecond inference latencies of transformer models render them unsuitable for wire-speed "
        "edge appliances.")

    add_section_heading(doc, "3.4", "Flow-Based Statistical Feature Extraction")
    add_body_text(doc,
        "Statistical flow feature engineering traces its roots to Paxson's foundational measurements of wide-area TCP connection dynamics [8]. "
        "Crotti et al. [9] demonstrated that protocol fingerprinting can be achieved through simplified Gaussian approximations of packet sizes "
        "and inter-arrival times. Draper-Gil et al. [14] standardized time-related flow feature extraction with the development of the ISCX-VPN "
        "benchmark, introducing 80+ bidirectional metrics covering forward/backward packet size statistics, inter-arrival time distributions, and "
        "flow duration characteristics. These statistical representations form the foundation of standardized tools like CICFlowMeter.")

    add_section_heading(doc, "3.5", "Early Traffic Classification")
    add_body_text(doc,
        "Early application identification was first formalized by Bernaille et al. [5], who demonstrated that observing the first three to five "
        "packets of a TCP connection enables accurate application identification using spatial clustering. Subsequent studies evaluated early "
        "triage by truncating offline PCAP files. However, Dainotti et al. [13] emphasized that offline evaluations frequently overlook operational "
        "constraints. Crucially, prior literature consistently fails to account for physical wire delay: in real-time environments, waiting for N "
        "packets to physically traverse the network introduces hundreds of milliseconds of propagation and queuing delay that dwarfs algorithmic "
        "computation time by orders of magnitude.")

    add_section_heading(doc, "3.6", "Research Gaps")
    add_body_text(doc,
        "A critical synthesis of the surveyed literature reveals five major unaddressed research gaps:", indent=False)

    lit_gaps = [
        ("Pervasive Session Leakage in Evaluation: ",
         "The vast majority of published studies employ random packet or flow train/test splits. As documented by Arp et al. [7], this permits "
         "flows from the same user session to appear in both splits, inflating accuracy claims by allowing models to memorize session-level artifacts."),
        ("Absence of Environmental Shift Evaluation: ",
         "Prior research predominantly evaluates models within static, homogeneous capture environments. Models are rarely tested across shifting "
         "physical media (e.g., training on Wi-Fi and evaluating on Cellular LTE) or under VPN tunnel encapsulations."),
        ("Conflation of Algorithmic Inference and Wire Delay: ",
         "Early prediction studies routinely report sub-millisecond classification times while neglecting the tens to hundreds of milliseconds "
         "required for packets to physically arrive at the capture interface."),
        ("Lack of Calibrated Selective Abstention: ",
         "Existing network classifiers enforce forced-choice binary or multi-class predictions, lacking calibrated mechanisms (Geifman and "
         "El-Yaniv [10], Guo et al. [11]) to abstain on low-confidence or out-of-distribution traffic."),
        ("Neglect of Lightweight Edge Feasibility: ",
         "Academic literature heavily favors compute-intensive deep learning architectures that cannot execute within the strict sub-millisecond "
         "budgets of commodity edge network appliances.")
    ]
    for pfx, desc in lit_gaps:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    add_section_heading(doc, "3.7", "Comparative Literature Survey")
    add_body_text(doc,
        "Table 3.1 provides a structured comparative summary of prominent literature benchmarks, categorizing each work by methodology, "
        "dataset, reported performance, and evaluation limitations. In contrast to prior studies, this project explicitly evaluates lightweight "
        "models under strict session isolation, accounts for physical wire delay, and analyzes asymmetric tunnel shifts.")

    lit_headers = ["Ref.", "Authors & Year", "Methodology", "Dataset Used", "Reported Metric", "Evaluation Limitations"]
    lit_rows = [
        ["[1]", "Moore & Zuev (2005)", "Naive Bayes on flow stats", "Cambridge trace (unencrypted)", "95.0% Flow Accuracy", "Random splitting; no session isolation; unencrypted"],
        ["[2]", "Anderson & McGrew (2017)", "Random Forest + TLS meta", "Enterprise TLS traces", "93.5% Macro-F1", "Requires cleartext SNI/certs; bypassed by TLS 1.3/ECH"],
        ["[3]", "Wang et al. (2017)", "1D/2D CNN on packet bytes", "ISCX-VPN-2016 benchmark", "99.4% Accuracy", "High compute cost; memorizes spurious payload tokens"],
        ["[4]", "Rezaei & Liu (2019)", "Deep learning survey + GBDT", "Multiple benchmark traces", "Varies (85–96%)", "Survey paper; no environmental shift evaluation"],
        ["[5]", "Bernaille et al. (2006)", "Early TCP handshake clustering", "University campus traces", "85–95% Early Accuracy", "Offline PCAP truncation; physical wire delay ignored"],
        ["[6]", "Lin et al. (2022)", "ET-BERT Transformer model", "ISCX-VPN + USTC-TFC2016", "97.4% Macro-F1", "1 GB+ model footprint; multi-millisecond GPU latency"],
        ["[7]", "Arp et al. (2022)", "ML security evaluation pitfalls", "Meta-analysis / survey", "N/A (Methodological)", "Highlights session leakage; does not build classifier"],
        ["[10]", "Geifman & El-Yaniv (2017)", "Selective classification framework", "ImageNet / CIFAR vision", "Coverage vs. Risk", "Vision domain; not applied to network traffic dynamics"],
        ["[8]", "This Project (2026)", "LightGBM / DT Zero-Payload", "dataset_v2 (301 hybrid flows)", "0.5664 Val / 0.5474 Test F1", "Strict session isolation; wire-delay aware; tunnel audited"]
    ]
    add_table_with_data(doc, lit_headers, lit_rows, "Comparative Literature Survey Summary", "3.1",
                        col_widths=[0.45, 1.25, 1.35, 1.25, 1.0, 1.7])

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 4 — DESIGN AND METHODOLOGY
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 4, "DESIGN AND METHODOLOGY")

    add_section_heading(doc, "4.1", "Proposed System Overview")
    add_body_text(doc,
        "The proposed system is an end-to-end, zero-payload encrypted traffic classification architecture designed to operate in real-time "
        "on live physical interfaces or recorded PCAP traces. The pipeline operates under a strict privacy invariant: application layer payload "
        "bytes are immediately stripped at the kernel capture hook, ensuring that zero application payload enters the feature extraction or "
        "machine learning inference engines. The system ingests raw packet headers, reconstructs bidirectional 5-tuple flow states, extracts "
        "statistical distribution vectors, executes lightweight model inference, applies validation-calibrated selective classification, and "
        "publishes real-time telemetry to an operational cybersecurity SOC console.")

    add_section_heading(doc, "4.2", "System Architecture")
    add_body_text(doc,
        "Figure 4.1 depicts the high-level system architecture, illustrating the four primary operational stages: (1) Kernel Ingestion and "
        "Payload Hygiene, (2) Bidirectional Flow Management, (3) Zero-Payload Feature Extraction and Lightweight Inference, and (4) Selective "
        "Gating and Security Operations Center (SOC) Telemetry.")

    add_figure(doc, "UROP_Report/Assets/architecture_diagram.png",
               "End-to-End System Architecture", "4.1", width_inches=5.8)

    add_body_text(doc,
        "As illustrated in Figure 4.1, network packets are captured in promiscuous mode via Npcap. The Packet Sanitizer strips all payload "
        "bytes, passing only transport metadata (source/destination IP, ports, protocol, timestamp, wire length, TCP flags, and direction) to the "
        "Flow Manager. The Flow Manager tracks bidirectional flow states using a sliding window table with early prefix triggers (N = 3, 5, 10 "
        "packets) and a 15-second inactivity timeout. The Zero-Payload Feature Extractor computes statistical metrics and routes feature vectors "
        "to the lightweight ML engine (LightGBM / Decision Tree). Predictions are filtered by the Selective Classification Gate, which routes "
        "high-confidence flows to automated enforcement and low-confidence flows to secondary inspection.")

    add_section_heading(doc, "4.3", "Dataset Collection Methodology")
    add_body_text(doc,
        "Physical network traffic was captured on a dedicated Windows 11 workstation connected to the campus network via an Intel Wi-Fi 6 AX201 "
        "802.11ax wireless interface. Controlled user browsing sessions were generated across six predefined application categories: Web Browsing, "
        "Video Streaming, Messaging, VoIP, File Transfer, and Other Background services. To capture tunnel encapsulation effects, sessions were "
        "conducted under both direct unencapsulated Wi-Fi conditions and Cloudflare WARP (WireGuard) encrypted tunnel configurations. Each capture "
        "run was tagged with unique session identifiers to enable strict group-aware isolation.")

    add_section_heading(doc, "4.4", "Dataset Description and Provenance")
    add_body_text(doc,
        "Table 4.1 presents the detailed provenance and compositional breakdown of the project datasets. A fundamental requirement of scientific "
        "integrity is transparently distinguishing between physical traffic measurements and synthetic or perturbed data representations.", indent=False)

    ds_headers = ["Dataset Property", "dataset_real_v1", "dataset_v2 (HYBRID_PERTURBED)"]
    ds_rows = [
        ["Total Flow Count", "121 flows", "301 flows"],
        ["Physical Wi-Fi Flows", "121 flows (100.0%)", "121 flows (40.2%)"],
        ["Controlled Statistical Perturbations", "0 flows (0.0%)", "180 flows (59.8%)"],
        ["Independent Capture Sessions", "60 sessions", "150 sessions"],
        ["Application Traffic Classes", "6 classes", "6 classes"],
        ["Underlying Network Environments", "Wi-Fi 802.11ax", "Wi-Fi, Ethernet*, Cellular LTE*"],
        ["Tunnel Encapsulation States", "WARP + Direct", "WARP + Direct"],
        ["Authoritative Registry Origin", "REAL_DATA", "HYBRID_PERTURBED"],
        ["Data Provenance Manifest", "data/dataset_versions/v1/", "data/dataset_versions/v2/provenance.json"]
    ]
    add_table_with_data(doc, ds_headers, ds_rows, "Dataset Composition and Provenance Summary", "4.1",
                        col_widths=[2.2, 1.8, 2.0])

    add_body_text(doc,
        "Crucially, as indicated in Table 4.1, dataset_v2 is designated as a HYBRID_PERTURBED benchmark. The Ethernet and Cellular LTE conditions "
        "(marked with an asterisk) are represented by controlled statistical feature perturbations applied to the underlying physical Wi-Fi flows, "
        "not by native physical Ethernet or cellular interface captures. Similarly, Dataset V3 represents a separate capture-validation subsystem "
        "whose ambiguous pilot records are quarantined and never conflated with supervised benchmark data.")

    add_section_heading(doc, "4.5", "Traffic Flow Construction")
    add_body_text(doc,
        "A network flow is formally defined as a sequence of packets sharing a common 5-tuple: (Source IP, Destination IP, Source Port, "
        "Destination Port, Transport Protocol) within a bounded temporal window. Bidirectional flows aggregate both forward (client-to-server) "
        "and backward (server-to-client) directions. Directionality is determined by the first observed packet of the 5-tuple, with forward "
        "traffic assigned to the initial sender. Flows are terminated upon encountering a TCP FIN or RST flag, or following a 15-second inactivity timeout.")

    add_section_heading(doc, "4.6", "Zero-Payload Feature Extraction")
    add_body_text(doc,
        "The feature extraction engine computes 84 statistical features from packet header metadata without inspecting payload bytes. The features "
        "capture distribution moments (mean, standard deviation, minimum, maximum, median, skewness), temporal intervals, directional volume ratios, "
        "and burst structures across forward, backward, and aggregated flow directions.")

    add_section_heading(doc, "4.7", "Feature Engineering")
    add_body_text(doc,
        "Table 4.2 outlines the five distinct feature families comprising the 84-feature matrix. Feature engineering is designed to capture "
        "orthogonal behavioral dimensions of application transport dynamics.", indent=False)

    feat_headers = ["Family Identifier", "Feature Family Name", "Count", "Mathematical Description & Behavioral Significance"]
    feat_rows = [
        ["Family A", "Packet Size Distribution", "30", "Summary statistics (min, max, mean, std, median, quartiles) of packet wire lengths across forward, backward, and combined directions."],
        ["Family B", "Inter-Arrival Time (IAT)", "30", "Distribution metrics of inter-packet arrival times (dt = t_i - t_{i-1}) in microseconds, capturing application pacing and queuing dynamics."],
        ["Family C", "Packet & Byte Counts", "12", "Cumulative packet counts, total byte volumes, header length sums, and instantaneous throughput rates."],
        ["Family D", "Directional Ratios", "3", "Downlink-to-uplink packet ratio, byte volume ratio, and directional duration ratio, capturing request-response asymmetry."],
        ["Family E", "Burst Dynamics", "9", "Forward and backward burst count, mean burst size, burst duration, and inter-burst idle times, modeling interactive application transfers."]
    ]
    add_table_with_data(doc, feat_headers, feat_rows, "Zero-Payload Feature Categories and Descriptions", "4.2",
                        col_widths=[1.1, 1.6, 0.6, 2.7])

    add_section_heading(doc, "4.8", "Machine Learning Models")
    add_body_text(doc,
        "Table 4.3 details the architectural configurations and hyperparameters of the four lightweight machine learning classifiers benchmarked "
        "in this study. Hyperparameters were tuned via 5-fold cross-validation on the training split.", indent=False)

    hp_headers = ["Model Architecture", "Algorithm Family", "Key Hyperparameter Configuration", "Operational Rationale"]
    hp_rows = [
        ["Logistic Regression", "Linear Classifier", "C = 1.0, penalty = 'l2', max_iter = 1000, solver = 'lbfgs'", "Fast linear baseline establishing linear separability boundary."],
        ["Decision Tree", "CART Tree", "criterion = 'gini', max_depth = 8, min_samples_split = 4", "Ultra-fast microsecond inference; transparent human-readable rule set."],
        ["Random Forest", "Bagging Ensemble", "n_estimators = 100, max_depth = 12, max_features = 'sqrt'", "Non-linear bagging ensemble robust against tabular noise and outliers."],
        ["LightGBM*", "Gradient Boosting", "n_estimators = 100, learning_rate = 0.05, num_leaves = 31", "Validation-selected winner; leaf-wise tree growth with gradient boosting."]
    ]
    add_table_with_data(doc, hp_headers, hp_rows, "Machine Learning Model Hyperparameters", "4.3",
                        col_widths=[1.4, 1.2, 2.0, 1.4])

    add_section_heading(doc, "4.9", "Training and Evaluation Methodology")
    add_body_text(doc,
        "To prevent session-level data leakage, data partitioning is governed by GroupShuffleSplit (GSS) with 5 independent splits, using the "
        "unique capture session identifier as the grouping variable. Under this protocol, 100% of flows belonging to a given browsing session "
        "reside exclusively in either the training split or the evaluation split. The split ratio allocates 60% of sessions to training, 20% to "
        "validation, and 20% to held-out test evaluation. Model selection is strictly performed on validation split Macro-F1 prior to test evaluation.")

    add_section_heading(doc, "4.10", "Evaluation Metrics")
    add_body_text(doc,
        "Model performance is evaluated using Macro-Averaged F1-Score (Macro-F1), which weights all six traffic classes equally regardless of "
        "class imbalance. For selective classification, Selective Accuracy and Coverage are evaluated across rejection thresholds tau. Computational "
        "efficiency is measured using P50, P95, and P99 latency percentiles in milliseconds, and model memory footprint in kilobytes.")

    add_section_heading(doc, "4.11", "Early Prediction Methodology")
    add_body_text(doc,
        "Early prediction evaluates classification performance when observing only the initial N packets of a connection (N in {3, 5, 10, 20, "
        "30, 50, Full}). Critically, the evaluation methodology separates physical wire delay (the time required for N packets to physically arrive "
        "at the network interface) from algorithmic latency (feature extraction and inference time), providing a realistic operational timeline.")

    add_section_heading(doc, "4.12", "Selective Classification Methodology")
    add_body_text(doc,
        "Selective classification implements a risk-coverage tradeoff using a confidence gating threshold tau. When the model's maximum softmax "
        "probability P_max >= tau, the prediction is accepted; otherwise, the model abstains and flags the flow for secondary inspection. The optimal "
        "threshold tau* = 0.70 is selected on the validation split.")

    add_section_heading(doc, "4.13", "Generalization Experiments")
    add_body_text(doc,
        "Nine distinct distribution shift regimes (REG-01 through REG-08b) are evaluated to quantify model resilience: group-aware random baseline "
        "(REG-01), unseen capture file split (REG-02), unseen session split (REG-03), temporal split (REG-04), unseen environment perturbations "
        "(REG-05), unseen network impairments (REG-06), unseen activity variants (REG-07), and bidirectional tunnel encapsulation shifts (REG-08a and REG-08b).")

    add_section_heading(doc, "4.14", "Research Workflow")
    add_body_text(doc,
        "Figure 4.2 presents the structured research methodology workflow, illustrating the sequential progression from physical packet capture "
        "through feature engineering, group-aware cross-validation, multi-regime generalization testing, early triage, selective classification, "
        "and real-time SOC dashboard validation.")

    add_figure(doc, "UROP_Report/Assets/workflow_flowchart.png",
               "Research Methodology Workflow", "4.2", width_inches=5.8)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 5 — IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 5, "IMPLEMENTATION")

    add_section_heading(doc, "5.1", "Development Environment")
    add_body_text(doc,
        "The project is implemented in Python 3.10+ on a Windows 11 workstation. The codebase follows a modular architecture organized into "
        "distinct packages: capture (packet sniffing), flows (flow generation), preprocessing (feature extraction), models (classifier definitions), "
        "training (dataset registry and splitting), realtime (streaming classification engine), and dashboard (Streamlit SOC console). All "
        "dependencies are locked in requirements-lock.txt for exact reproducibility.")

    add_section_heading(doc, "5.2", "Network Packet Capture")
    add_body_text(doc,
        "The capture module (capture/packet_capture.py) provides two packet ingestion backends: PCAPReader for offline trace analysis and "
        "LiveSniffer for real-time promiscuous capture via Npcap. The LiveSniffer configures interface selection, BPF filters, ring buffers, "
        "and capture duration limits. Transport header metadata is immediately extracted, while application payload bytes are stripped at the "
        "kernel hook to enforce the zero-payload privacy contract.")

    add_section_heading(doc, "5.3", "Bidirectional Flow Management")
    add_body_text(doc,
        "The flow management engine (flows/flow_generator.py) aggregates raw packet metadata into bidirectional flow structures. A thread-safe "
        "sliding window table tracks active flows indexed by 5-tuple hashes. Flows trigger feature extraction upon reaching prefix packet horizons "
        "(N = 3, 5, 10), upon encountering TCP connection termination flags (FIN/RST), or upon reaching a 15-second inactivity timeout.")

    add_section_heading(doc, "5.4", "Statistical Feature Extraction")
    add_body_text(doc,
        "The feature extraction engine (preprocessing/feature_extractor.py) implements vectorized statistical computations using NumPy. It computes "
        "forward, backward, and bidirectional packet size distributions, inter-arrival time moments, cumulative counts, and directional volume ratios. "
        "For real-time triage, the extractor supports computing compact K=3 feature vectors in under 0.4 milliseconds.")

    add_section_heading(doc, "5.5", "Machine Learning Model Integration")
    add_body_text(doc,
        "Trained model artifacts, pre-fitted standardizers, and label encoders are serialized using joblib into the models/artifacts/ directory. "
        "The RealTimeClassifier class (realtime/classifier.py) loads model binaries during initialization and provides warm in-memory inference "
        "routines executing in microseconds.")

    add_section_heading(doc, "5.6", "Classification and Confidence Handling")
    add_body_text(doc,
        "During real-time inference, the classifier outputs both the predicted class label and the full softmax probability distribution. The maximum "
        "probability P_max is evaluated against the validation-calibrated selective threshold tau* = 0.70. Flows exceeding tau* are assigned "
        "PredictionState.ACCEPTED; flows below tau* are flagged as PredictionState.ABSTAINED, routing them for secondary verification.")

    add_section_heading(doc, "5.7", "Real-Time Processing Pipeline")
    add_body_text(doc,
        "The real-time streaming classification engine (realtime/run.py) operates an asynchronous, queue-based architecture. A dedicated sniffer "
        "thread pushes sanitized packet metadata into an in-memory queue, decoupled from the flow tracking and inference worker threads. This "
        "producer-consumer architecture guarantees that bursts of network traffic do not cause packet drops at the capture interface.")

    add_section_heading(doc, "5.8", "Local API and Event Storage")
    add_body_text(doc,
        "Classification events are published through an internal EventBus (realtime/events.py) and persisted to a local SQLite database table "
        "(events.db). The event schema records flow IDs, 5-tuples, packet counts, byte totals, predicted labels, confidence scores, and "
        "selective decision states with microsecond timestamps, while strictly excluding payload content.")

    add_section_heading(doc, "5.9", "Monitoring Dashboard")
    add_body_text(doc,
        "Figure 5.1 depicts the real-time streaming classification pipeline and cybersecurity SOC monitoring architecture. The front-end console "
        "is implemented in Streamlit (dashboard/app.py), providing security analysts with 8 operational tabs: Live Triage Console, Model "
        "Performance Metrics, Flow Inspector, Distribution Drift Monitor, Risk Gauges, System Health, Alert Event Log, and Audit Provenance.")

    add_figure(doc, "submission/fig_soc_architecture.png",
               "Real-Time Streaming Pipeline and Cybersecurity SOC Architecture", "5.1", width_inches=5.8)

    add_section_heading(doc, "5.10", "Error Handling and Fail-Closed Design")
    add_body_text(doc,
        "The pipeline implements a fail-closed architectural design. If feature extraction fails due to malformed packet headers or missing fields, "
        "the flow is assigned an UNKNOWN label and quarantined rather than defaulting to a false-positive prediction. System health monitors "
        "track queue depth, memory consumption, and processing latencies, triggering alerts if ingestion thresholds are exceeded.")

    add_section_heading(doc, "5.11", "Dataset V3 Physical Capture Validation")
    add_body_text(doc,
        "To establish verifiable ground truth on live endpoint traffic without inspecting application payloads, a Windows Process-to-Socket "
        "Attribution subsystem was developed (research/dataset_v3/). Using the Windows IP Helper API (GetExtendedTcpTable / GetExtendedUdpTable), "
        "the subsystem polls socket-to-PID bindings at 150 ms intervals, tracking Chrome and application process trees. In Pilot Session 1 "
        "(25,499 packets, 90 flows), all 90 original labels were preserved as AMBIGUOUS in accordance with strict ground-truth audit rules, "
        "ensuring unverified live captures are never conflated with supervised benchmark data.")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 6 — HARDWARE / SOFTWARE TOOLS USED
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 6, "HARDWARE / SOFTWARE TOOLS USED")

    add_section_heading(doc, "6.1", "Hardware Requirements")
    add_body_text(doc,
        "Table 6.1 specifies the hardware environment utilized for dataset collection, model training, and real-time streaming validation. "
        "All benchmarks were executed on physical commodity hardware without specialized GPU acceleration.", indent=False)

    hw_headers = ["Component", "Development & Validation Specification", "Minimum Edge Deployment Requirement"]
    hw_rows = [
        ["Host Processor", "Intel Core i7-12700H (14 cores, 20 threads, up to 4.70 GHz)", "Quad-core x86_64 or ARM64 processor (>= 2.0 GHz)"],
        ["System Memory", "16 GB DDR5 RAM (4800 MHz dual-channel)", "2 GB available system RAM"],
        ["Storage", "1 TB NVMe PCIe 4.0 Solid State Drive", "10 GB available SSD storage for PCAP traces and DB"],
        ["Network Interface", "Intel Wi-Fi 6 AX201 802.11ax (160 MHz channel width)", "10/100/1000 Mbps Ethernet or 802.11ac/ax Wi-Fi adapter"],
        ["Capture Hardware", "Physical promiscuous-mode wireless network adapter", "Standard promiscuous-capable network interface card (NIC)"]
    ]
    add_table_with_data(doc, hw_headers, hw_rows, "Hardware Requirements and Specifications", "6.1",
                        col_widths=[1.5, 2.5, 2.0])

    add_section_heading(doc, "6.2", "Software Requirements")
    add_body_text(doc,
        "Table 6.2 outlines the software environment, operating system dependencies, and locked library versions governing the research toolchain.",
        indent=False)

    sw_headers = ["Software Layer", "Package / Technology", "Locked Version", "Operational Function in Architecture"]
    sw_rows = [
        ["Operating System", "Microsoft Windows 11 Enterprise", "Build 22631+", "Host execution and live packet capture environment."],
        ["Capture Library", "Npcap Packet Capture Driver", "v1.79+", "Low-level kernel packet sniffing and promiscuous access."],
        ["Runtime Engine", "Python Programming Language", "v3.10.11+", "Core programming language for all pipeline modules."],
        ["Machine Learning", "scikit-learn", "v1.4.0+", "Baseline classifiers (LR, DT, RF), splitting, and metrics."],
        ["Gradient Boosting", "LightGBM", "v4.3.0+", "Validation-selected gradient boosting decision tree engine."],
        ["Packet Parsing", "Scapy", "v2.5.0+", "High-level packet parsing and PCAP read/write operations."],
        ["Scientific Array", "NumPy & SciPy", "v1.26.4+", "Vectorized feature extraction and statistical distribution calculations."],
        ["Data Manipulation", "Pandas", "v2.2.0+", "Tabular data processing, CSV handling, and result aggregation."],
        ["SOC Dashboard", "Streamlit", "v1.32.0+", "Interactive real-time cybersecurity SOC monitoring dashboard."],
        ["Test Harness", "Pytest", "v8.0.0+", "Automated test suite executing 537 comprehensive unit tests."]
    ]
    add_table_with_data(doc, sw_headers, sw_rows, "Software Requirements and Dependencies", "6.2",
                        col_widths=[1.3, 1.6, 1.1, 2.0])

    add_section_heading(doc, "6.3", "Programming Languages")
    add_body_text(doc,
        "The complete research codebase is authored in Python 3.10+, utilizing strict type annotations (PEP 484), dataclasses for immutable "
        "schema representation, and asynchronous concurrent queues for non-blocking packet ingestion. Native C-bindings in NumPy, LightGBM, "
        "and Scapy/Npcap provide line-rate processing efficiency.")

    add_section_heading(doc, "6.4", "Machine Learning Libraries")
    add_body_text(doc,
        "Machine learning model implementation relies on scikit-learn for standard tabular classifiers, GroupShuffleSplit cross-validation, "
        "and evaluation metrics. LightGBM provides high-performance gradient boosted decision trees utilizing histogram-based splitting and "
        "leaf-wise tree growth.")

    add_section_heading(doc, "6.5", "Network Capture Technologies")
    add_body_text(doc,
        "Packet capture is powered by Npcap, the Nmap Project's packet sniffing architecture for Windows. Npcap provides kernel-level packet "
        "filtering via the Berkeley Packet Filter (BPF) syntax, loopback capture capabilities, and direct NDIS 6 filter driver integration, "
        "ensuring zero packet loss under high connection churn.")

    add_section_heading(doc, "6.6", "Development Tools")
    add_body_text(doc,
        "Development and debugging were conducted using Visual Studio Code, Git for version control across isolated research branches, "
        "and PyMuPDF / python-docx for automated academic report compilation and verification.")

    add_section_heading(doc, "6.7", "Testing Tools")
    add_body_text(doc,
        "Software reliability is validated through an extensive automated test suite comprising 537 tests executed via Pytest. The test harness "
        "verifies packet parsing accuracy, zero-payload invariance, feature extraction correctness, model serialisation, fail-closed behavior, "
        "and claims provenance validation (scripts/validate_research_claims.py).")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 7 — RESULTS AND DISCUSSION
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 7, "RESULTS AND DISCUSSION")

    add_section_heading(doc, "7.1", "Experimental Setup")
    add_body_text(doc,
        "All experiments were conducted on the authoritative hybrid benchmark dataset_v2 using strict group-aware session splitting "
        "(GroupShuffleSplit, 5 independent splits). Model selection was performed on the validation split prior to evaluating performance on "
        "the held-out test split. All reported scores reflect exact empirical values stored in authoritative results tables.")

    add_section_heading(doc, "7.2", "Dataset Statistics")
    add_body_text(doc,
        "The hybrid benchmark dataset_v2 comprises 301 total flows originating from 150 independent sessions. It contains 121 genuine physical "
        "Wi-Fi flows (40.2%) and 180 controlled statistical feature perturbations (59.8%) simulating Ethernet, Cellular LTE, and network "
        "impairment conditions across six balanced application classes (Web, Video, Messaging, VoIP, File Transfer, Other).")

    add_section_heading(doc, "7.3", "Baseline Model Comparison")
    add_body_text(doc,
        "Table 7.1 presents the empirical baseline comparison results from experiment EXP-R09 across all four machine learning models. Under the "
        "pre-registered evaluation protocol, LightGBM is the validation-selected winner based on achieving the highest validation Macro-F1 score (0.5664).",
        indent=False)

    base_headers = ["Model Architecture", "Val Macro-F1", "Test Macro-F1", "Test Accuracy", "Selection Status"]
    base_rows = [
        ["Logistic Regression", "0.3684", "0.3703", "0.3750", "Evaluated Baseline"],
        ["Decision Tree", "0.5647", "0.5802", "0.5625", "Candidate Baseline"],
        ["Random Forest", "0.5492", "0.5516", "0.5417", "Candidate Baseline"],
        ["LightGBM*", "0.5664", "0.5474", "0.5417", "VALIDATION WINNER*"]
    ]
    add_table_with_data(doc, base_headers, base_rows, "Baseline Model Comparison Results (EXP-R09)", "7.1",
                        col_widths=[1.6, 1.1, 1.1, 1.1, 1.4])

    add_body_text(doc,
        "* Important Methodological Note: LightGBM is the validation-selected model winner based on highest validation Macro-F1 (0.5664). "
        "While Decision Tree achieved a slightly higher numerical score on the test split (0.5802 vs. 0.5474), selecting a model based on test split "
        "performance would violate academic protocol and introduce evaluation bias. LightGBM remains the authoritative selected model.")

    add_body_text(doc,
        "Figure 7.1 presents the visual comparison of validation and test Macro-F1 scores across all four models, highlighting LightGBM's "
        "validation superiority. Figure 7.2 displays the confusion matrices for Decision Tree and Random Forest on the held-out test split, "
        "illustrating high classification accuracy on Web and Video traffic alongside expected confusion between Messaging and Background flows.")

    add_figure(doc, "UROP_Report/Assets/fig_baseline_comparison.png",
               "Baseline Model Comparison — Validation and Test Macro-F1 Scores", "7.1", width_inches=5.2)

    add_figure(doc, "UROP_Report/Assets/fig_confusion_matrix.png",
               "Decision Tree and Random Forest Confusion Matrices on Test Split", "7.2", width_inches=5.2)

    add_section_heading(doc, "7.4", "Feature Selection and Ablation")
    add_body_text(doc,
        "Table 7.2 presents the feature count tradeoff results from experiment EXP-R10. Evaluating subsets of top-K features (ranked by mutual "
        "information and tree importance) revealed that a compact 3-feature subset achieves the highest test Macro-F1 (0.6738), significantly "
        "outperforming the expansive 84-feature matrix which collapses to 0.2985 test Macro-F1 due to severe overfitting on tabular noise.", indent=False)

    fc_headers = ["Feature Count (K)", "Val Macro-F1", "Test Macro-F1", "Test Accuracy", "Dimensionality Regime"]
    fc_rows = [
        ["3 (Top-3 Features)*", "0.7572", "0.6738", "0.6667", "Optimal Parsimony*"],
        ["5 Features", "0.3567", "0.3741", "0.3750", "Degraded"],
        ["10 Features", "0.3037", "0.3857", "0.3750", "Degraded"],
        ["15 Features", "0.3481", "0.4199", "0.4167", "Moderate"],
        ["20 Features", "0.3550", "0.3327", "0.3333", "Overfitting"],
        ["30 Features", "0.3521", "0.3127", "0.3125", "Overfitting"],
        ["84 (All Features)", "0.3550", "0.2985", "0.2917", "Severe Overfitting"]
    ]
    add_table_with_data(doc, fc_headers, fc_rows, "Feature Count Tradeoff Results (EXP-R10)", "7.2",
                        col_widths=[1.5, 1.1, 1.1, 1.1, 1.4])

    add_body_text(doc,
        "Table 7.3 details the feature family ablation analysis from experiment EXP-R10. Direction-only features (Family D: 3 directional ratios) "
        "achieve the highest individual family performance at 0.4261 test Macro-F1. In contrast, timing features alone (Family B) collapse to 0.2624, "
        "confirming that packet pacing exhibits high variance across network environments.", indent=False)

    abl_headers = ["Configuration", "Feature Family", "Feature Count", "Val Macro-F1", "Test Macro-F1"]
    abl_rows = [
        ["A. Packet-size only", "Family A", "30 features", "0.3058", "0.3542"],
        ["B. Timing only", "Family B", "30 features", "0.3153", "0.2624"],
        ["C. Counts/bytes only", "Family C", "12 features", "0.3349", "0.3098"],
        ["D. Direction only*", "Family D", "3 features", "0.4068", "0.4261*"],
        ["E. Burst only", "Family E", "8 features", "0.3862", "0.2556"],
        ["F. All families combined", "Families A–E", "84 features", "0.3318", "0.3331"]
    ]
    add_table_with_data(doc, abl_headers, abl_rows, "Feature Family Ablation Results (EXP-R10)", "7.3",
                        col_widths=[1.6, 1.1, 1.1, 1.1, 1.1])

    add_body_text(doc,
        "Figure 7.3 illustrates the Pareto frontier of feature count versus test Macro-F1 score, demonstrating the sharp performance peak at K = 3.")

    add_figure(doc, "UROP_Report/Assets/fig_feature_pareto.png",
               "Feature Count Tradeoff Curve and Pareto Frontier", "7.3", width_inches=5.2)

    add_section_heading(doc, "7.5", "Cross-Environment Generalization")
    add_body_text(doc,
        "Table 7.4 presents model performance across nine distribution shift regimes evaluated in experiment EXP-R11. The models demonstrate "
        "high robustness when tested against unseen physical media perturbations (REG-05: 0.9325 Macro-F1) and unseen network impairments "
        "(REG-06: 0.9030 Macro-F1). Note that REG-05 and REG-06 evaluate controlled statistical perturbations, not native physical captures.",
        indent=False)

    gen_headers = ["Regime ID", "Distribution Shift Description", "Test Macro-F1", "F1 Delta", "Robustness Rating"]
    gen_rows = [
        ["REG-01", "Group-Aware Random Baseline", "0.6060", "0.0000", "ROBUST (Reference)"],
        ["REG-02", "Unseen Capture File Split", "0.8255", "+0.2195", "ROBUST"],
        ["REG-03", "Unseen Session Split", "0.8559", "+0.2499", "ROBUST"],
        ["REG-04", "Temporal Chronological Split", "0.5437", "-0.0623", "MODERATE"],
        ["REG-05", "Unseen Environment Perturbations*", "0.9325", "+0.3265", "ROBUST*"],
        ["REG-06", "Unseen Network Condition Perturbations*", "0.9030", "+0.2970", "ROBUST*"],
        ["REG-07", "Unseen Activity Variant Split", "0.8335", "+0.2275", "ROBUST"],
        ["REG-08a", "Tunneled → Direct Transfer", "1.0000", "+0.3940", "ROBUST (Perfect)"],
        ["REG-08b", "Direct → Tunneled Transfer", "0.3407", "-0.2653", "SEVERE COLLAPSE"]
    ]
    add_table_with_data(doc, gen_headers, gen_rows, "Cross-Environment Generalization Results (EXP-R11)", "7.4",
                        col_widths=[0.9, 2.3, 1.1, 1.0, 1.3])

    add_body_text(doc,
        "Figure 7.4 depicts the Macro-F1 performance across all nine distribution shift regimes, visually contrasting the stable generalization "
        "under environmental perturbations against the severe degradation observed in temporal drift and direct-to-tunnel transfer.")

    add_figure(doc, "UROP_Report/Assets/fig_generalization.png",
               "Cross-Environment Generalization Across Distribution Shift Regimes", "7.4", width_inches=5.5)

    add_section_heading(doc, "7.6", "Network Condition Robustness")
    add_body_text(doc,
        "Under the unseen network condition regime (REG-06), models trained on baseline conditions achieved 0.9030 Macro-F1 when tested on flows "
        "subjected to simulated packet loss, jitter, and bandwidth constraints. This demonstrates that directional ratios and coarse burst moments "
        "remain stable across moderate network degradation.")

    add_section_heading(doc, "7.7", "Tunnel Direction Shift")
    add_body_text(doc,
        "The most critical empirical finding in the generalization study is the asymmetric tunnel encapsulation shift documented in REG-08a and REG-08b. "
        "Models trained on Cloudflare WARP (WireGuard) tunneled traffic generalize perfectly when deployed on direct unencapsulated traffic (REG-08a: "
        "1.0000 Macro-F1, 36/36 flows correctly classified). In sharp contrast, models trained exclusively on direct traffic collapse catastrophically "
        "when encountering tunneled traffic (REG-08b: 0.3407 Macro-F1, F1 delta = -0.2653).")

    add_body_text(doc,
        "Figure 7.5 highlights this asymmetric collapse. The failure occurs because WireGuard encapsulation enforces a uniform 1280-byte MTU clamp "
        "and standardizes outer packet envelopes, destroying the packet size distribution cues upon which direct-traffic models rely. Conversely, "
        "models trained on tunneled traffic learn to rely on underlying timing and directional burst dynamics, which transfer seamlessly to direct flows.")

    add_figure(doc, "UROP_Report/Assets/fig_tunnel_shift.png",
               "Asymmetric Tunnel Generalization Failure Under WireGuard Encapsulation", "7.5", width_inches=5.2)

    add_section_heading(doc, "7.8", "Early Prediction Results")
    add_body_text(doc,
        "Table 7.5 presents the early prediction results from experiment EXP-R12 across seven packet horizons. At horizon N = 3 packets, the system "
        "achieves 0.6111 Selective Macro-F1 at 91.67% coverage within 84.33 ms total latency. Crucially, 64.04 ms (76.0%) of this latency is "
        "physical radio arrival delay, while algorithmic computation requires only 20.29 ms. Waiting for full flow completion requires 59.7 seconds "
        "(746 times longer) and collapses to 0.0000 Macro-F1.", indent=False)

    early_headers = ["Observation Horizon", "Macro-F1", "Selective Acc", "Coverage", "Wire Delay (ms)", "Algorithmic Lat (ms)", "Total Latency (ms)"]
    early_rows = [
        ["3 packets*", "0.6111*", "63.64%", "91.67%", "64.04", "20.29", "84.33 ms*"],
        ["5 packets", "0.3643", "41.67%", "100.00%", "327.23", "20.29", "347.52 ms"],
        ["10 packets", "0.5000", "80.00%", "41.67%", "1,308.63", "20.29", "1,328.92 ms"],
        ["20 packets", "0.2778", "42.86%", "58.33%", "3,934.08", "20.29", "3,954.37 ms"],
        ["30 packets", "0.2778", "33.33%", "100.00%", "4,872.29", "20.29", "4,892.58 ms"],
        ["50 packets", "0.3000", "50.00%", "50.00%", "9,261.18", "20.29", "9,281.47 ms"],
        ["Full flow", "0.0000", "0.00%", "33.33%", "59,646.23", "20.29", "59,666.52 ms"]
    ]
    add_table_with_data(doc, early_headers, early_rows, "Early Prediction Results Across Packet Horizons (EXP-R12)", "7.5",
                        col_widths=[1.2, 0.8, 0.9, 0.8, 1.0, 1.1, 1.1])

    add_body_text(doc,
        "Figure 7.6 illustrates the trade-off between packet horizon, selective accuracy, and total latency, clearly highlighting the wire delay "
        "dominance across all observation horizons.")

    add_figure(doc, "UROP_Report/Assets/fig_early_prediction.png",
               "Early Prediction Performance Across Packet Observation Horizons", "7.6", width_inches=5.2)

    add_section_heading(doc, "7.9", "Selective Classification Results")
    add_body_text(doc,
        "Table 7.6 presents the selective classification results from experiment EXP-R13 across rejection thresholds tau. At the validation-selected "
        "threshold tau* = 0.70, selective accuracy rises from 54.17% (no rejection) to 73.08%, reducing the error rate from 45.83% to 26.92% on "
        "accepted traffic at 54.17% coverage.", indent=False)

    sel_headers = ["Rejection Threshold (tau)", "Coverage (%)", "Selective Accuracy", "Error Rate (%)", "Selective Macro-F1", "Decision Policy"]
    sel_rows = [
        ["0.00 (No Abstention)", "100.00%", "54.17%", "45.83%", "0.5474", "Forced Decision"],
        ["0.50", "91.67%", "59.09%", "40.91%", "0.6012", "Minimal Gating"],
        ["0.60", "75.00%", "63.89%", "36.11%", "0.6110", "Moderate Gating"],
        ["0.70*", "54.17%*", "73.08%*", "26.92%*", "0.6515*", "VALIDATION OPTIMAL*"],
        ["0.80", "43.75%", "85.71%", "14.29%", "0.8752", "High Precision"],
        ["0.90", "20.83%", "90.00%", "10.00%", "0.9000", "Ultra-High Precision"]
    ]
    add_table_with_data(doc, sel_headers, sel_rows, "Selective Classification Results at Different Thresholds (EXP-R13)", "7.6",
                        col_widths=[1.5, 0.9, 1.1, 1.0, 1.1, 1.3])

    add_body_text(doc,
        "Figure 7.7 illustrates the monotonic increase in selective accuracy and the corresponding reduction in error rate as the confidence threshold "
        "increases, demonstrating the practical efficacy of confidence-gated triage.")

    add_figure(doc, "UROP_Report/Assets/fig_selective_coverage.png",
               "Selective Classification Coverage vs. Selective Accuracy Tradeoff", "7.7", width_inches=5.2)

    add_section_heading(doc, "7.10", "Computational Efficiency")
    add_body_text(doc,
        "Table 7.7 reports the computational latency benchmarks from experiment EXP-R14 across all pipeline stages. Decision Tree achieved the fastest "
        "warm inference at 0.0578 ms P50 (0.0924 ms P95), enabling a theoretical throughput of over 17,000 flows/sec with an ultra-compact memory "
        "footprint of 9.58 KB. LightGBM achieved 0.3427 ms P50 inference with a 157.34 KB model footprint.", indent=False)

    lat_headers = ["Pipeline Component / Model", "P50 Latency (ms)", "P95 Latency (ms)", "P99 Latency (ms)", "Model Footprint (KB)"]
    lat_rows = [
        ["Feature Extraction (warm)", "0.3681 ms", "7.0281 ms", "9.4446 ms", "N/A (Code)"],
        ["Preprocessing Standardizer", "0.0020 ms", "0.0023 ms", "0.0026 ms", "1.24 KB"],
        ["Decision Tree Inference*", "0.0578 ms*", "0.0924 ms", "0.1138 ms", "9.58 KB*"],
        ["Logistic Regression Inference", "0.0684 ms", "0.0798 ms", "0.1460 ms", "3.42 KB"],
        ["LightGBM Inference (Winner)", "0.3427 ms", "0.5632 ms", "0.7886 ms", "157.34 KB"],
        ["Random Forest Inference", "3.9199 ms", "5.0760 ms", "6.1170 ms", "878.04 KB"]
    ]
    add_table_with_data(doc, lat_headers, lat_rows, "Computational Latency Measurements (EXP-R14)", "7.7",
                        col_widths=[1.8, 1.2, 1.2, 1.2, 1.4])

    add_body_text(doc,
        "Figure 7.8 presents the latency distribution across pipeline stages, illustrating that algorithmic feature extraction and model inference "
        "execute well within sub-millisecond budgets.")

    add_figure(doc, "UROP_Report/Assets/fig_latency_distribution.png",
               "Computational Latency Distribution Across Pipeline Stages", "7.8", width_inches=5.2)

    add_section_heading(doc, "7.11", "Real-Time System Validation")
    add_body_text(doc,
        "Table 7.8 presents the real-time pipeline validation results from experiment EXP-R15. The streaming engine was validated in both DEMO_MODE "
        "(synthetic packet replay) and LIVE_MODE (live physical network capture). Both modes achieved zero packet drops, zero processing failures, "
        "and passed all five privacy/security invariant audits.", indent=False)

    rt_headers = ["Operational Mode", "Packets Processed", "Flows Created", "Classifications", "Packet Drops", "Failures", "Integrity Audit"]
    rt_rows = [
        ["DEMO_MODE (Synthetic)", "68 packets", "12 flows", "44 events", "0 drops (0%)", "0 failures", "PASSED (5/5 Checks)"],
        ["LIVE_MODE (Physical)", "142 packets", "15 flows", "112 events", "0 drops (0%)", "0 failures", "PASSED (5/5 Checks)"]
    ]
    add_table_with_data(doc, rt_headers, rt_rows, "Real-Time Pipeline Validation Results (EXP-R15)", "7.8",
                        col_widths=[1.5, 1.1, 0.9, 1.0, 0.9, 0.8, 1.3])

    add_body_text(doc,
        "Figure 7.9 illustrates the confidence calibration curve and reliability diagram, confirming that the model's predicted probabilities "
        "correlate accurately with empirical accuracy following selective calibration.")

    add_figure(doc, "UROP_Report/Assets/fig_calibration_curve.png",
               "Confidence Calibration Curve and Expected Calibration Error", "7.9", width_inches=5.2)

    add_section_heading(doc, "7.12", "Discussion of Findings")
    add_body_text(doc,
        "The empirical findings of this project provide four fundamental insights for the design of encrypted traffic classification systems. "
        "First, enforcing group-aware session isolation is essential to prevent severe performance inflation: naive splitting permits models to "
        "memorize session-specific artifacts, whereas session-isolated evaluation reveals true out-of-session generalization capabilities. "
        "Second, compact feature engineering decisively outperforms expansive feature sets on tabular network traffic, as demonstrated by the "
        "top-3 feature subset achieving 0.6738 test F1 versus 0.2985 for all 84 features.")

    add_body_text(doc,
        "Third, physical wire delay fundamentally dictates early-triage feasibility: in live networks, physical packet propagation dominates total "
        "classification latency by over 76% to 99%, rendering sub-millisecond algorithmic optimizations secondary to wire arrival constraints. "
        "Fourth, tunnel encapsulation creates severe asymmetric transfer failure that can be mitigated by training on tunneled data to force models "
        "to learn robust transport timing dynamics.")

    add_section_heading(doc, "7.13", "Limitations and Threats to Validity")
    add_body_text(doc,
        "Several methodological limitations and threats to validity must be acknowledged:", indent=False)

    threats = [
        ("Controlled Benchmark Scale: ",
         "dataset_v2 contains 301 total flows across 150 sessions. While sufficient for controlled architectural evaluation and ablation, "
         "evaluation on large-scale ISP traces containing millions of flows is required before broad commercial deployment."),
        ("Simulated Perturbations in dataset_v2: ",
         "Ethernet and Cellular LTE conditions in dataset_v2 are represented by controlled statistical feature perturbations rather than native "
         "physical cellular captures. Future work should evaluate physical cellular hardware testbeds."),
        ("Quarantined Dataset V3 Records: ",
         "The Dataset V3 pilot sessions established attribution feasibility on live Windows sockets, but their unlabelled ambiguous records "
         "remain quarantined and cannot yet serve as verified supervised training ground truth.")
    ]
    for pfx, desc in threats:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 8 — CONCLUSION
    # ═══════════════════════════════════════════════════════════════════════
    add_chapter_heading(doc, 8, "CONCLUSION")

    add_section_heading(doc, "8.1", "Project Summary")
    add_body_text(doc,
        "This Undergraduate Research Opportunity Program (UROP) project has successfully designed, implemented, and empirically validated an "
        "end-to-end, zero-payload encrypted traffic classification system capable of operating in real-time under network environment shift. By "
        "strictly operating on transport-layer statistical distributions without decrypting packets or inspecting payloads, the framework preserves "
        "complete cryptographic user privacy while providing high-fidelity traffic categorization.")

    add_body_text(doc,
        "Under rigorous group-aware session isolation eliminating session-level leakage, LightGBM was established as the validation-selected model "
        "winner (Validation Macro-F1 = 0.5664, Test Macro-F1 = 0.5474), while Decision Tree established superior edge-deployment efficiency "
        "(0.0578 ms P50 latency, 9.58 KB footprint). Compact feature engineering demonstrated that 3 directional features outperform 84 features, "
        "and selective classification at tau* = 0.70 reduced error rates from 45.83% to 26.92%. The live streaming pipeline was validated with zero "
        "packet drops and zero payload leaks.")

    add_section_heading(doc, "8.2", "Research Contributions")
    add_body_text(doc,
        "The project has established eight concrete contributions: (1) zero-payload real-time streaming pipeline, (2) multi-environment hybrid "
        "benchmark (dataset_v2), (3) strict session-isolated evaluation protocol, (4) discovery of compact feature superiority, (5) empirical "
        "documentation of asymmetric tunnel transfer failure, (6) physical wire delay hierarchy characterization, (7) validation-calibrated selective "
        "classification gating, and (8) live Windows process-to-socket attribution architecture.")

    add_section_heading(doc, "8.3", "Limitations")
    add_body_text(doc,
        "The primary limitations of the current study include the controlled scale of the 301-flow hybrid benchmark, the reliance on statistical "
        "perturbations for Ethernet and Cellular conditions rather than native physical multi-NIC hardware captures, and the ambiguous status of "
        "initial Dataset V3 pilot records awaiting production promotion.")

    add_section_heading(doc, "8.4", "Scope of Further Work")
    add_body_text(doc,
        "Promising avenues for future research include:", indent=False)

    future_work = [
        ("Large-Scale Multi-NIC Physical Testbed: ",
         "Constructing a multi-homed physical testbed equipped with concurrent native Wi-Fi 6, 10GbE Ethernet, and 5G cellular modems to capture "
         "large-scale physical multi-environment traces."),
        ("Dataset V3 Attribution Subsystem Maturation: ",
         "Executing continuous physical capture sessions using the validated IP Helper attribution engine to promote thousands of ambiguous flows "
         "to verified supervised ground truth."),
        ("Hardware-Accelerated Edge Offloading: ",
         "Compiling Decision Tree and LightGBM rule sets into eBPF/XDP kernel bytecodes and P4 programmable switches for sub-microsecond in-network line-rate routing."),
        ("Dynamic Online Conformal Prediction: ",
         "Extending static selective classification to adaptive online conformal prediction sets that provide provable coverage guarantees under continuous non-stationary concept drift.")
    ]
    for pfx, desc in future_work:
        add_bullet_item(doc, desc, bold_prefix=pfx)

    # ═══════════════════════════════════════════════════════════════════════
    # BACK MATTER: REFERENCES
    # ═══════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    add_formatted_paragraph(doc, "REFERENCES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    references = [
        "[1] A. W. Moore and D. Zuev, \"Internet traffic classification using Bayesian analysis techniques,\" in Proceedings of the ACM SIGMETRICS Joint International Conference on Measurement and Modeling of Computer Systems, Banff, Alberta, Canada, 2005, pp. 50–60.",
        "[2] B. Anderson and D. McGrew, \"Machine learning for encrypted malware traffic classification: Accounting for noisy labels and non-stationarity,\" in Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, Halifax, NS, Canada, 2017, pp. 1723–1732.",
        "[3] W. Wang, M. Zhu, J. Wang, X. Zeng, and Z. Yang, \"End-to-end encrypted traffic classification with one-dimensional convolution neural networks,\" in Proceedings of the IEEE International Conference on Intelligence and Security Informatics (ISI), Beijing, China, 2017, pp. 43–48.",
        "[4] S. Rezaei and X. Liu, \"Deep learning for encrypted traffic classification: An overview,\" IEEE Communications Surveys & Tutorials, vol. 21, no. 4, pp. 4328–4374, Fourthquarter 2019.",
        "[5] L. Bernaille, R. Teixeira, and K. Salamatian, \"Early application identification,\" in Proceedings of the 2006 ACM Conference on Emerging Network Experiment and Technology (CoNEXT), Lisboa, Portugal, 2006, pp. 1–12.",
        "[6] X. Lin, G. Xiong, G. Gou, Z. Li, J. Shi, and J. Yu, \"ET-BERT: A contextualized datagram representation with pre-training transformers for encrypted traffic classification,\" in Proceedings of the ACM Web Conference 2022 (WWW), Lyon, France, 2022, pp. 633–642.",
        "[7] D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, and K. Rieck, \"Dos and Don'ts of machine learning in computer security,\" in Proceedings of the 31st USENIX Security Symposium, Boston, MA, USA, 2022, pp. 3971–3988.",
        "[8] V. Paxson, \"Empirically derived analytic models of wide-area TCP connections,\" IEEE/ACM Transactions on Networking, vol. 2, no. 4, pp. 316–336, Aug. 1994.",
        "[9] M. Crotti, M. Dusi, F. Gringoli, and L. Salgarelli, \"Traffic classification through simple statistical fingerprinting,\" ACM SIGCOMM Computer Communication Review, vol. 37, no. 1, pp. 5–16, Jan. 2007.",
        "[10] Y. Geifman and R. El-Yaniv, \"Selective classification for deep neural networks,\" in Advances in Neural Information Processing Systems (NeurIPS 2017), Long Beach, CA, USA, vol. 30, 2017, pp. 4878–4887.",
        "[11] C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, \"On calibration of modern neural networks,\" in Proceedings of the 34th International Conference on Machine Learning (ICML 2017), Sydney, NSW, Australia, vol. 70, 2017, pp. 1321–1330.",
        "[12] F. Pendlebury, F. Pierazzi, R. Jordaney, J. Kinder, and L. Cavallaro, \"TESSERACT: Eliminating experimental bias in malware classification across space and time,\" in Proceedings of the 28th USENIX Security Symposium, Santa Clara, CA, USA, 2019, pp. 729–746.",
        "[13] A. Dainotti, A. Pescape, and K. C. Claffy, \"Issues and future directions in traffic classification,\" IEEE Network, vol. 26, no. 1, pp. 35–40, Jan.-Feb. 2012.",
        "[14] G. Draper-Gil, A. H. Lashkari, M. S. I. Mamun, and A. A. Ghorbani, \"Characterization of encrypted and VPN traffic using time-related features,\" in Proceedings of the 2nd International Conference on Information Systems Security and Privacy (ICISSP), Rome, Italy, 2016, pp. 407–414.",
        "[15] E. Rescorla, \"The Transport Layer Security (TLS) Protocol Version 1.3,\" RFC 8446, Internet Engineering Task Force (IETF), Aug. 2018.",
        "[16] J. A. Donenfeld, \"WireGuard: Next generation kernel network tunnel,\" in Proceedings of the Network and Distributed System Security Symposium (NDSS 2017), San Diego, CA, USA, 2017.",
        "[17] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye, and T.-Y. Liu, \"LightGBM: A highly efficient gradient boosting decision tree,\" in Advances in Neural Information Processing Systems (NeurIPS 2017), Long Beach, CA, USA, vol. 30, 2017, pp. 3146–3154."
    ]

    for ref in references:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.left_indent = Inches(0.4)
        p.paragraph_format.first_line_indent = Inches(-0.4)
        run = p.add_run(ref)
        run.font.size = Pt(11)
        run.font.name = "Times New Roman"

    # ─────────────────────────────────────────────────────────────────────
    # BACK MATTER: LIST OF PUBLICATIONS
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "LIST OF PUBLICATIONS", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=24)

    add_body_text(doc,
        "No publications arising from this project as of the submission date.", indent=False)

    return doc


# ─── TWO-PASS RECONCILIATION ENGINE ──────────────────────────────────────────

def extract_page_map_from_pdf(pdf_path):
    """
    Extracts the exact physical and logical page numbers of all chapters,
    sections, tables, and figures from the compiled PDF by searching strictly
    after the List of Figures page.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    lof_pno = None
    for pno in range(total_pages):
        text = doc[pno].get_text()
        if "LIST OF FIGURES" in text:
            lof_pno = pno
            break

    if lof_pno is None:
        lof_pno = 9

    ch1_pno = None
    for pno in range(lof_pno, total_pages):
        text = doc[pno].get_text()
        if "CHAPTER 1" in text:
            ch1_pno = pno
            break

    if ch1_pno is None:
        ch1_pno = lof_pno + 1

    print(f"  -> Layout landmarks: List of Figures pno={lof_pno} (phys {lof_pno+1}), Chapter 1 pno={ch1_pno} (phys {ch1_pno+1})")

    page_map = {}

    roman_numerals = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
    front_items = [
        ("Acknowledgement", "ACKNOWLEDGEMENT"),
        ("Abstract", "ABSTRACT"),
        ("Abbreviations", "ABBREVIATIONS"),
        ("List of Tables", "LIST OF TABLES"),
        ("List of Figures", "LIST OF FIGURES"),
    ]
    for key, needle in front_items:
        for pno in range(ch1_pno):
            text = doc[pno].get_text()
            if needle in text:
                rom_idx = pno
                if rom_idx < len(roman_numerals):
                    page_map[key] = roman_numerals[rom_idx]
                break

    toc_search_entries = [
        ("1", "CHAPTER 1"),
        ("1.1", "1.1 Introduction"),
        ("1.2", "1.2 Background of Encrypted Network Traffic"),
        ("1.3", "1.3 Problem Statement"),
        ("1.4", "1.4 Objectives of the Project"),
        ("1.5", "1.5 Scope of the Project"),
        ("1.6", "1.6 Organization of the Report"),
        ("2", "CHAPTER 2"),
        ("2.1", "2.1 Motivation"),
        ("2.2", "2.2 Limitations of Traditional Deep Packet Inspection"),
        ("2.3", "2.3 Need for Zero-Payload Traffic Classification"),
        ("2.4", "2.4 Need for Lightweight Machine Learning"),
        ("2.5", "2.5 Research Challenges"),
        ("2.6", "2.6 Project Contributions"),
        ("3", "CHAPTER 3"),
        ("3.1", "3.1 Introduction"),
        ("3.2", "3.2 Existing Encrypted Traffic Classification Approaches"),
        ("3.3", "3.3 Machine Learning-Based Traffic Classification"),
        ("3.4", "3.4 Flow-Based Statistical Feature Extraction"),
        ("3.5", "3.5 Early Traffic Classification"),
        ("3.6", "3.6 Research Gaps"),
        ("3.7", "3.7 Comparative Literature Survey"),
        ("4", "CHAPTER 4"),
        ("4.1", "4.1 Proposed System Overview"),
        ("4.2", "4.2 System Architecture"),
        ("4.3", "4.3 Dataset Collection Methodology"),
        ("4.4", "4.4 Dataset Description and Provenance"),
        ("4.5", "4.5 Traffic Flow Construction"),
        ("4.6", "4.6 Zero-Payload Feature Extraction"),
        ("4.7", "4.7 Feature Engineering"),
        ("4.8", "4.8 Machine Learning Models"),
        ("4.9", "4.9 Training and Evaluation Methodology"),
        ("4.10", "4.10 Evaluation Metrics"),
        ("4.11", "4.11 Early Prediction Methodology"),
        ("4.12", "4.12 Selective Classification Methodology"),
        ("4.13", "4.13 Generalization Experiments"),
        ("4.14", "4.14 Research Workflow"),
        ("5", "CHAPTER 5"),
        ("5.1", "5.1 Development Environment"),
        ("5.2", "5.2 Network Packet Capture"),
        ("5.3", "5.3 Bidirectional Flow Management"),
        ("5.4", "5.4 Statistical Feature Extraction"),
        ("5.5", "5.5 Machine Learning Model Integration"),
        ("5.6", "5.6 Classification and Confidence Handling"),
        ("5.7", "5.7 Real-Time Processing Pipeline"),
        ("5.8", "5.8 Local API and Event Storage"),
        ("5.9", "5.9 Monitoring Dashboard"),
        ("5.10", "5.10 Error Handling and Fail-Closed Design"),
        ("5.11", "5.11 Dataset V3 Physical Capture Validation"),
        ("6", "CHAPTER 6"),
        ("6.1", "6.1 Hardware Requirements"),
        ("6.2", "6.2 Software Requirements"),
        ("6.3", "6.3 Programming Languages"),
        ("6.4", "6.4 Machine Learning Libraries"),
        ("6.5", "6.5 Network Capture Technologies"),
        ("6.6", "6.6 Development Tools"),
        ("6.7", "6.7 Testing Tools"),
        ("7", "CHAPTER 7"),
        ("7.1", "7.1 Experimental Setup"),
        ("7.2", "7.2 Dataset Statistics"),
        ("7.3", "7.3 Baseline Model Comparison"),
        ("7.4", "7.4 Feature Selection and Ablation"),
        ("7.5", "7.5 Cross-Environment Generalization"),
        ("7.6", "7.6 Network Condition Robustness"),
        ("7.7", "7.7 Tunnel Direction Shift"),
        ("7.8", "7.8 Early Prediction Results"),
        ("7.9", "7.9 Selective Classification Results"),
        ("7.10", "7.10 Computational Efficiency"),
        ("7.11", "7.11 Real-Time System Validation"),
        ("7.12", "7.12 Discussion of Findings"),
        ("7.13", "7.13 Limitations and Threats to Validity"),
        ("8", "CHAPTER 8"),
        ("8.1", "8.1 Project Summary"),
        ("8.2", "8.2 Research Contributions"),
        ("8.3", "8.3 Limitations"),
        ("8.4", "8.4 Scope of Further Work"),
        ("REFERENCES", "REFERENCES"),
        ("LIST OF PUBLICATIONS", "LIST OF PUBLICATIONS"),
    ]

    for key, needle in toc_search_entries:
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[key] = str(arabic_page)
                break

    table_keys = ["3.1", "4.1", "4.2", "4.3", "6.1", "6.2", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8"]
    for tk in table_keys:
        needle = f"Table {tk}:"
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[f"T_{tk}"] = str(arabic_page)
                break

    fig_keys = ["4.1", "4.2", "5.1", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "7.9"]
    for fk in fig_keys:
        needle = f"Figure {fk}:"
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[f"F_{fk}"] = str(arabic_page)
                break

    return page_map


def main():
    print("================================================================================")
    print("  UROP ACADEMIC REPORT GENERATION — SRM UNIVERSITY-AP CSE")
    print("================================================================================")

    out_dir = PROJECT_ROOT / "submission"
    out_dir.mkdir(exist_ok=True)
    docx_path = out_dir / "UROP_Academic_Report.docx"
    pdf_path = out_dir / "UROP_Academic_Report.pdf"

    # Pass 1: Build initial document
    print("\n[PASS 1] Generating initial Word document (.docx)...")
    doc_pass1 = build_report_document(page_map=None)
    doc_pass1.save(str(docx_path))
    print(f"  -> Saved DOCX to: {docx_path} ({docx_path.stat().st_size:,} bytes)")

    # Pass 1 Conversion: Convert to PDF to extract true page positions
    print("\n[PASS 1] Converting DOCX to PDF for layout measurement...")
    docx2pdf.convert(str(docx_path), str(pdf_path))
    print(f"  -> Converted PDF to: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")

    # Pass 1 Extraction: Read exact page numbers with PyMuPDF
    print("\n[PASS 1] Extracting exact page numbers with PyMuPDF...")
    page_map = extract_page_map_from_pdf(str(pdf_path))
    print(f"  -> Extracted page positions for {len(page_map)} headings, tables, and figures.")

    # Pass 2: Re-generate document with exact reconciled page numbers
    print("\n[PASS 2] Re-generating Word document with reconciled Table of Contents...")
    doc_pass2 = build_report_document(page_map=page_map)
    doc_pass2.save(str(docx_path))
    print(f"  -> Saved reconciled DOCX to: {docx_path} ({docx_path.stat().st_size:,} bytes)")

    # Pass 2 Conversion: Final PDF export
    print("\n[PASS 2] Exporting final PDF report...")
    docx2pdf.convert(str(docx_path), str(pdf_path))
    print(f"  -> Exported final PDF to: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")

    # Verify final PDF
    pdf_doc = fitz.open(str(pdf_path))
    print(f"\n[VERIFICATION] Final PDF page count: {len(pdf_doc)} pages.")

    print("\n[SUCCESS] Both UROP_Academic_Report.docx and UROP_Academic_Report.pdf generated successfully.")


if __name__ == "__main__":
    main()
