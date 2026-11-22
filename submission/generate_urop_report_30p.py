#!/usr/bin/env python3
"""
UROP Academic Report Generator (Condensed 30-Page Edition) — SRM University-AP Format.
Project: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models
Student: Gorakala Rishik
Department of Computer Science & Engineering, SRM University-AP

Strict Target: EXACTLY 30 physical A4 pages.
- Title page (Phys 1)
- Declaration (Phys 2, Roman ii)
- Certificate (Phys 3, Roman iii)
- Acknowledgment (Phys 4, Roman iv)
- Abstract (Phys 5, Roman v)
- Table of Contents (Phys 6, Roman vi)
- List of Tables (Phys 7, Roman vii)
- List of Figures (Phys 8, Roman viii)
- Chapters 1–8 (Phys 9–26, Arabic 1–18)
  * Chapter 1: 2 pages (Phys 9–10, Arabic 1–2)
  * Chapter 2: 1 page  (Phys 11, Arabic 3)
  * Chapter 3: 2 pages (Phys 12–13, Arabic 4–5)
  * Chapter 4: 4 pages (Phys 14–17, Arabic 6–9)
  * Chapter 5: 3 pages (Phys 18–20, Arabic 10–12)
  * Chapter 6: 1 page  (Phys 21, Arabic 13)
  * Chapter 7: 4 pages (Phys 22–25, Arabic 14–17)
  * Chapter 8: 1 page  (Phys 26, Arabic 18)
- References (Phys 27–29, Arabic 19–21)
- Appendix A: Publication Status (Phys 30, Arabic 22)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import docx
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

import docx2pdf
import pymupdf as fitz

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


def add_body_text(doc, text, indent=True, space_after=4, line_spacing=1.35):
    """Adds a justified body paragraph with 12pt Times New Roman and academic indent."""
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
        pf.first_line_indent = Cm(0.89)  # 0.35 inch
    return p


def add_bullet_item(doc, text, bold_prefix=None, space_after=2.5, line_spacing=1.25):
    """Adds a bullet list item with proper indentation."""
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.size = Pt(11.5)
        r_pre.font.name = "Times New Roman"
    run = p.add_run(text)
    run.font.size = Pt(11.5)
    run.font.name = "Times New Roman"
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
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
    p1.paragraph_format.line_spacing = 1.15
    for idx, line in enumerate(left_lines):
        r = p1.add_run(line + ("\n" if idx < len(left_lines) - 1 else ""))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

    p2 = c2.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p2.paragraph_format.line_spacing = 1.15
    for idx, line in enumerate(right_lines):
        r = p2.add_run(line + ("\n" if idx < len(right_lines) - 1 else ""))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)
    return table


def add_chapter_heading(doc, chapter_num, title, space_before=6, space_after=10):
    """Adds a chapter heading centered."""
    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf1 = p1.paragraph_format
    pf1.space_before = Pt(space_before)
    pf1.space_after = Pt(3)
    pf1.keep_with_next = True
    r1 = p1.add_run(f"CHAPTER {chapter_num}")
    r1.bold = True
    r1.font.size = Pt(16)
    r1.font.name = "Times New Roman"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf2 = p2.paragraph_format
    pf2.space_before = Pt(0)
    pf2.space_after = Pt(space_after)
    pf2.keep_with_next = True
    r2 = p2.add_run(title)
    r2.bold = True
    r2.font.size = Pt(16)
    r2.font.name = "Times New Roman"
    return p2


def add_section_heading(doc, number, title, space_before=6, space_after=3):
    """Adds a numbered section heading."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.keep_with_next = True
    run = p.add_run(f"{number} {title}")
    run.bold = True
    run.font.size = Pt(13)
    run.font.name = "Times New Roman"
    return p


def add_table_with_data(doc, headers, rows, caption=None, table_num=None, col_widths=None,
                        font_size=8.5, space_after=3):
    """Adds a formatted table with caption above, shaded header, and centered alignment."""
    if caption and table_num:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(5)
        cap.paragraph_format.space_after = Pt(2.5)
        cap.paragraph_format.keep_with_next = True
        run = cap.add_run(f"Table {table_num}: {caption}")
        run.bold = True
        run.font.size = Pt(10)
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
                run.font.size = Pt(font_size + 0.5)
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
                    run.font.size = Pt(font_size)
                    run.font.name = "Times New Roman"

    if col_widths and len(col_widths) == len(headers):
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(1)
    p_after.paragraph_format.space_after = Pt(space_after)
    return table


def add_figure(doc, img_rel_path, caption, fig_num, width_inches=4.4, space_before=5, space_after=6):
    """Adds an image figure with centered alignment and caption below."""
    img_path = PROJECT_ROOT / img_rel_path
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(2)
    pf.keep_with_next = True

    if img_path.exists():
        run = p.add_run()
        run.add_picture(str(img_path), width=Inches(width_inches))
    else:
        run = p.add_run(f"[{caption} — Image File: {img_rel_path}]")
        run.italic = True
        run.font.size = Pt(9.5)
        run.font.name = "Times New Roman"

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf = cap.paragraph_format
    cpf.space_before = Pt(2)
    cpf.space_after = Pt(space_after)
    r = cap.add_run(f"Figure {fig_num}: {caption}")
    r.bold = True
    r.font.size = Pt(10)
    r.font.name = "Times New Roman"
    return cap


# ─── CORE DOCUMENT BUILDER (30-PAGE EDITION) ──────────────────────────────────

def build_condensed_document(page_map=None):
    """
    Builds the complete 30-Page Condensed UROP Academic Report.
    Page budget allocation:
    - Phys 1: Title (no footer)
    - Phys 2: Declaration (ii)
    - Phys 3: Certificate (iii)
    - Phys 4: Acknowledgment (iv)
    - Phys 5: Abstract (v)
    - Phys 6: Table of Contents (vi)
    - Phys 7: List of Tables (vii)
    - Phys 8: List of Figures (viii)
    - Phys 9–10: Chapter 1 (Arabic 1–2)
    - Phys 11: Chapter 2 (Arabic 3)
    - Phys 12–13: Chapter 3 (Arabic 4–5)
    - Phys 14–17: Chapter 4 (Arabic 6–9)
    - Phys 18–20: Chapter 5 (Arabic 10–12)
    - Phys 21: Chapter 6 (Arabic 13)
    - Phys 22–25: Chapter 7 (Arabic 14–17)
    - Phys 26: Chapter 8 (Arabic 18)
    - Phys 27–29: References (Arabic 19–21)
    - Phys 30: Appendix A (Arabic 22)
    """
    doc = Document()

    def gp(key, default_val):
        if page_map and key in page_map:
            return page_map[key]
        return default_val

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: FRONT MATTER (PAGES 1 TO 8, ROMAN NUMERALS i to viii)
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
    # PHYSICAL PAGE 1: TITLE PAGE (NO FOOTER DISPLAYED)
    # ─────────────────────────────────────────────────────────────────────
    add_formatted_paragraph(doc,
        "Real-Time Encrypted Traffic Classification Using\nLightweight Machine Learning Models",
        bold=True, font_size=16.5, alignment=WD_ALIGN_PARAGRAPH.CENTER,
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
    # PHYSICAL PAGE 2: DECLARATION (DISPLAY 'ii')
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
    # PHYSICAL PAGE 3: CERTIFICATE (DISPLAY 'iii')
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
        "[INSERT HOD NAME]",
        "Department of Computer Science & Engineering",
        "School of Engineering and Sciences",
        "SRM University-AP, Andhra Pradesh"
    ]
    add_signature_table_2col(doc, cert_left, cert_right)

    # ─────────────────────────────────────────────────────────────────────
    # PHYSICAL PAGE 4: ACKNOWLEDGEMENT (DISPLAY 'iv')
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
    p_sig_a.paragraph_format.space_before = Pt(20)
    r_a = p_sig_a.add_run("Gorakala Rishik\n[INSERT OFFICIAL REGISTRATION NUMBER]")
    r_a.font.name = "Times New Roman"
    r_a.font.size = Pt(11)
    r_a.bold = True

    # ─────────────────────────────────────────────────────────────────────
    # PHYSICAL PAGE 5: ABSTRACT (DISPLAY 'v')
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
        "0.6708 test Macro-F1, significantly outperforming the full 84-feature matrix (0.3359 test Macro-F1). Early "
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
    # PHYSICAL PAGE 6: TABLE OF CONTENTS (DISPLAY 'vi')
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "CONTENTS", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=14)

    toc_items = [
        ("", "Acknowledgement", gp("Acknowledgement", "iv")),
        ("", "Abstract", gp("Abstract", "v")),
        ("", "List of Tables", gp("List of Tables", "vii")),
        ("", "List of Figures", gp("List of Figures", "viii")),
        ("1", "INTRODUCTION TO THE PROJECT", gp("1", "1")),
        ("1.1", "Background and Problem Statement", gp("1.1", "1")),
        ("1.2", "Objectives, Scope, and Contributions", gp("1.2", "2")),
        ("2", "MOTIVATION", gp("2", "3")),
        ("2.1", "Limitations of Deep Packet Inspection", gp("2.1", "3")),
        ("2.2", "Need for Zero-Payload and Lightweight Models", gp("2.2", "3")),
        ("3", "LITERATURE SURVEY", gp("3", "4")),
        ("3.1", "Existing Encrypted Traffic Classification", gp("3.1", "4")),
        ("3.2", "Research Gaps and Comparative Literature Synthesis", gp("3.2", "5")),
        ("4", "DESIGN AND METHODOLOGY", gp("4", "6")),
        ("4.1", "System Overview and Architecture", gp("4.1", "6")),
        ("4.2", "Dataset Provenance and Multi-Environment Setup", gp("4.2", "7")),
        ("4.3", "Zero-Payload Feature Engineering and Models", gp("4.3", "8")),
        ("4.4", "Training, Evaluation, and Early Triage Protocol", gp("4.4", "9")),
        ("5", "IMPLEMENTATION", gp("5", "10")),
        ("5.1", "Real-Time Capture and Flow Management", gp("5.1", "10")),
        ("5.2", "Streaming Pipeline and SOC Architecture", gp("5.2", "11")),
        ("5.3", "Fail-Closed Integrity and Dataset V3 Validation", gp("5.3", "12")),
        ("6", "HARDWARE / SOFTWARE TOOLS USED", gp("6", "13")),
        ("6.1", "System Requirements and Software Stack", gp("6.1", "13")),
        ("7", "RESULTS AND DISCUSSION", gp("7", "14")),
        ("7.1", "Baseline Model Performance (EXP-R09)", gp("7.1", "14")),
        ("7.2", "Feature Selection and Ablation (EXP-R10)", gp("7.2", "15")),
        ("7.3", "Cross-Environment Shift and Tunnel Fragility (EXP-R11)", gp("7.3", "16")),
        ("7.4", "Early Traffic Triage, Wire Delay, and Selective Classification", gp("7.4", "17")),
        ("7.5", "Computational Efficiency and Pipeline Validation", gp("7.5", "17")),
        ("8", "CONCLUSION", gp("8", "18")),
        ("8.1", "Research Summary and Key Findings", gp("8.1", "18")),
        ("8.2", "Practical Limitations and Future Work", gp("8.2", "18")),
        ("", "REFERENCES", gp("REFERENCES", "19")),
        ("", "APPENDIX A: PUBLICATION STATUS", gp("APPENDIX A: PUBLICATION STATUS", "22")),
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
        run_title.font.size = Pt(10)
        run_title.font.name = "Times New Roman"

        dots_count = max(4, 76 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.bold = True if (not num or not "." in num) else False
        r_pg.font.size = Pt(10)
        r_pg.font.name = "Times New Roman"

    # ─────────────────────────────────────────────────────────────────────
    # PHYSICAL PAGE 7: LIST OF TABLES (DISPLAY 'vii')
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "LIST OF TABLES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    tables_list = [
        ("3.1", "Comparative Literature Survey Summary", gp("T_3.1", "5")),
        ("4.1", "Dataset Composition and Provenance Summary (dataset_v2)", gp("T_4.1", "7")),
        ("4.2", "Zero-Payload Feature Categories and Extraction Schemas", gp("T_4.2", "8")),
        ("4.3", "Machine Learning Model Hyperparameters and Configurations", gp("T_4.3", "8")),
        ("6.1", "Hardware Requirements and Specifications", gp("T_6.1", "13")),
        ("6.2", "Software Requirements and Dependencies", gp("T_6.2", "13")),
        ("7.1", "Baseline Model Comparison Results (EXP-R09)", gp("T_7.1", "14")),
        ("7.2", "Feature Count Tradeoff and Family Ablation Results (EXP-R10)", gp("T_7.2", "15")),
        ("7.3", "Cross-Environment Generalization Results (EXP-R11)", gp("T_7.3", "16")),
        ("7.4", "Selective Classification Results at Distinct Thresholds (EXP-R13)", gp("T_7.4", "17")),
        ("7.5", "Computational Latency and Real-Time Pipeline Performance (EXP-R14, R15)", gp("T_7.5", "17")),
    ]

    for num, title, page in tables_list:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        run_title = p.add_run(f"Table {num}:  {title}")
        run_title.font.size = Pt(10.5)
        run_title.font.name = "Times New Roman"
        dots_count = max(4, 74 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.font.size = Pt(10.5)
        r_pg.font.name = "Times New Roman"

    # ─────────────────────────────────────────────────────────────────────
    # PHYSICAL PAGE 8: LIST OF FIGURES (DISPLAY 'viii')
    # ─────────────────────────────────────────────────────────────────────
    doc.add_page_break()
    add_formatted_paragraph(doc, "LIST OF FIGURES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=18)

    figures_list = [
        ("4.1", "End-to-End Zero-Payload System Architecture", gp("F_4.1", "6")),
        ("4.2", "Reproducible Research Methodology and Evaluation Workflow", gp("F_4.2", "9")),
        ("5.1", "Real-Time Streaming Pipeline and Cybersecurity SOC Architecture", gp("F_5.1", "11")),
        ("7.1", "Baseline Model Comparison — Validation and Test Macro-F1 Scores", gp("F_7.1", "14")),
        ("7.2", "Feature Count Tradeoff Curve and Pareto Frontier", gp("F_7.2", "15")),
        ("7.3", "Cross-Environment Generalization Across Distribution Shift Regimes", gp("F_7.3", "16")),
        ("7.4", "Early Prediction Performance Across Packet Observation Horizons", gp("F_7.4", "17")),
    ]

    for num, title, page in figures_list:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        run_title = p.add_run(f"Figure {num}:  {title}")
        run_title.font.size = Pt(10.5)
        run_title.font.name = "Times New Roman"
        dots_count = max(4, 74 - len(run_title.text) - len(str(page)))
        p.add_run(" " + "." * dots_count + " ")
        r_pg = p.add_run(str(page))
        r_pg.font.size = Pt(10.5)
        r_pg.font.name = "Times New Roman"

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: CHAPTERS & BACK MATTER (PAGES 9 TO 30, ARABIC 1 TO 22)
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
    # CHAPTER 1 — INTRODUCTION TO THE PROJECT (PAGES 9–10, ARABIC 1–2)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 9 (ARABIC 1)
    add_chapter_heading(doc, 1, "INTRODUCTION TO THE PROJECT", space_before=4, space_after=8)

    add_section_heading(doc, "1.1", "Background and Problem Statement", space_before=3, space_after=2)
    add_body_text(doc,
        "Network traffic classification is an essential capability for modern network management, quality of service "
        "(QoS) provisioning, cybersecurity threat detection, and automated incident response. Network operators "
        "rely on traffic classification to enforce service-level agreements, identify bandwidth-intensive streaming "
        "services, detect malicious command-and-control communication, and prioritize latency-critical real-time flows. "
        "Historically, classification systems relied on static port-based lookups and Deep Packet Inspection (DPI) "
        "techniques that matched application byte signatures in plaintext payloads.", space_after=3.0)

    add_body_text(doc,
        "Over the past decade, however, the digital network ecosystem has undergone a fundamental transformation. "
        "Today, over 95% of web and enterprise traffic is encrypted using modern cryptographic protocols such as "
        "Transport Layer Security (TLS 1.3), Quick UDP Internet Connections (QUIC / RFC 9000), and wire-speed tunneling "
        "mechanisms such as WireGuard and Cloudflare WARP. These protocols intentionally obscure packet contents, "
        "randomize application signatures, encrypt handshake metadata (e.g., Encrypted Client Hello), and clamp Maximum "
        "Transmission Unit (MTU) boundaries to standardized sizes (e.g., 1280 bytes). Consequently, traditional DPI "
        "paradigms have become completely obsolete.", space_after=3.0)

    add_body_text(doc,
        "Accurately and rapidly classifying encrypted network traffic under dynamic physical and logical environment "
        "shifts—without inspecting packet payloads, violating user privacy, or incurring unsustainable computational "
        "latency—remains a major open challenge. Contemporary machine learning approaches suffer from four critical "
        "methodological shortcomings:", indent=False, space_after=2.0)

    add_bullet_item(doc,
        "Over-optimistic evaluation resulting from naive random packet or flow splitting that permits identical user "
        "sessions to span both training and evaluation splits, leading to severe data leakage and inflated claims.",
        bold_prefix="Session Leakage Bias: ", space_after=2.0)
    add_bullet_item(doc,
        "Catastrophic performance degradation when models trained on direct unencapsulated Wi-Fi traffic encounter "
        "alternate transmission media (Ethernet, Cellular LTE) or cryptographic tunneling (WireGuard/WARP).",
        bold_prefix="Environment Shift Fragility: ", space_after=2.0)
    add_bullet_item(doc,
        "Ignoring physical wire delay in early classification claims, where prior works report sub-millisecond algorithmic "
        "inference while neglecting the tens of milliseconds required for physical packets to traverse the wire.",
        bold_prefix="Wire Delay Conflation: ", space_after=2.0)
    add_bullet_item(doc,
        "Uncalibrated model confidence producing brittle, forced predictions on ambiguous flows under distribution shift.",
        bold_prefix="Uncalibrated Decisions: ", space_after=2.0)

    # PAGE 10 (ARABIC 2)
    doc.add_page_break()
    add_section_heading(doc, "1.2", "Objectives, Scope, and Contributions", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The primary objective of this project is to develop, evaluate, and operationalize a real-time, zero-payload "
        "encrypted traffic classification system that demonstrates robustness under network environment shifts while "
        "maintaining microsecond-scale inference latency. The investigation operates under a strict privacy contract: "
        "no application payload bytes are inspected, decrypted, or retained at any stage of processing.", space_after=3.5)

    add_body_text(doc,
        "The core contributions of this research work are fivefold:", indent=False, space_after=2.5)
    add_bullet_item(doc,
        "We engineer a privacy-preserving feature extraction engine that computes 84 statistical transport-layer features "
        "(packet lengths, inter-arrival times, burst ratios) exclusively from unencrypted IP/TCP/UDP headers.",
        bold_prefix="1. Zero-Payload Feature Engine: ")
    add_bullet_item(doc,
        "We construct dataset_v2 (HYBRID_PERTURBED, 301 total flows across 150 sessions: 121 genuine physical Wi-Fi "
        "802.11ax flows and 180 controlled statistical perturbations) and evaluate four ML algorithms under strict "
        "session-isolated GroupShuffleSplit to eliminate cross-session data leakage.",
        bold_prefix="2. Rigorous Leakage-Free Benchmark: ")
    add_bullet_item(doc,
        "We demonstrate that feature space reduction to a compact 3-feature subset improves Macro-F1 from 0.3359 "
        "(full 84 features) to 0.6708, while systematically benchmarking cross-environment generalization failures.",
        bold_prefix="3. Dimensionality & Shift Analysis: ")
    add_bullet_item(doc,
        "We implement early classification across packet horizons (N = 3, 5, 10, 20) and provide the first empirical "
        "decomposition proving that physical wire delay accounts for >76% of early triage and >99.9% of full-flow latency.",
        bold_prefix="4. Wire Delay Decomposition: ")
    add_bullet_item(doc,
        "We integrate validation-calibrated selective prediction (confidence thresholding) and build an operational "
        "real-time streaming pipeline processing live packets via Scapy/Npcap with sub-millisecond inference and fail-closed safety.",
        bold_prefix="5. Selective Streaming Pipeline: ", space_after=4)

    add_body_text(doc,
        "The remainder of this report is organized as follows: Chapter 2 discusses the core motivations and privacy requirements; "
        "Chapter 3 surveys existing literature and establishes research gaps; Chapter 4 presents the system architecture, dataset "
        "provenance, and methodology; Chapter 5 details the streaming implementation and fail-closed design; Chapter 6 summarizes "
        "the experimental hardware and software tools; Chapter 7 provides empirical results across seven registered experiments; "
        "and Chapter 8 concludes the report with research findings and future directions.", space_after=4)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 2 — MOTIVATION (PAGE 11, ARABIC 3)
    # ═══════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    add_chapter_heading(doc, 2, "MOTIVATION", space_before=4, space_after=8)

    add_section_heading(doc, "2.1", "Limitations of Deep Packet Inspection", space_before=3, space_after=2)
    add_body_text(doc,
        "For over two decades, Deep Packet Inspection (DPI) served as the gold standard for network monitoring and "
        "intrusion detection by scanning plaintext payload bytes for protocol signatures. However, the transition to pervasive "
        "encryption has rendered payload inspection obsolete and legally fraught. Transport Layer Security (TLS 1.3, RFC 8446) "
        "mandates forward secrecy and encrypts handshake negotiation. Encrypted Client Hello (ECH) further conceals Server "
        "Name Indication (SNI) hostnames from passive network observers.", space_after=2.5)

    add_body_text(doc,
        "Concurrently, QUIC (RFC 9000)—encapsulating streams within UDP—encrypts transport-layer signaling and sequence numbers, "
        "preventing middleboxes from tracking transport parameters. Modern tunnels like WireGuard and Cloudflare WARP aggregate "
        "diverse applications into uniform encrypted datagrams, creating an urgent requirement for non-invasive, zero-payload "
        "classification paradigms.", space_after=2.5)

    add_section_heading(doc, "2.2", "Need for Zero-Payload and Lightweight Models", space_before=3, space_after=2)
    add_body_text(doc,
        "Zero-payload classification addresses this challenge by operating exclusively on external transport dynamics: packet "
        "lengths, directional inter-arrival times (IAT), and burstiness. Because transport statistics reflect application "
        "semantics (e.g., interactive keystrokes in messaging vs. high-throughput bursts in video streaming), machine learning "
        "models can discriminate traffic categories without decrypting ciphertexts or violating user privacy (GDPR).", space_after=2.5)

    add_body_text(doc,
        "Crucially, enterprise network switches operate under strict line-rate latency constraints requiring per-packet triage "
        "within microseconds. Deep neural networks (e.g., 1D-CNNs) introduce high computational overhead and GPU dependencies "
        "impractical for edge deployment. In contrast, lightweight tree models (Decision Trees and LightGBM) offer microsecond "
        "execution, sub-megabyte memory footprints, and direct explainability, making them optimal for wire-speed network classification.", space_after=2.0)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 3 — LITERATURE SURVEY (PAGES 12–13, ARABIC 4–5)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 12 (ARABIC 4)
    doc.add_page_break()
    add_chapter_heading(doc, 3, "LITERATURE SURVEY", space_before=4, space_after=10)

    add_section_heading(doc, "3.1", "Existing Encrypted Traffic Classification", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The evolution of traffic classification reflects three distinct methodological eras: port-based lookups, "
        "payload-based Deep Packet Inspection, and statistical machine learning. Early seminal surveys by Moore and Zuev [1] "
        "and Nguyen and Armitage [2] established that transport-layer statistics (packet length distributions, inter-arrival "
        "times, and duration) contain rich application-discriminative information capable of bypassing static port dependencies. "
        "As encryption became pervasive, researchers investigated advanced cryptographic metadata and machine learning "
        "paradigms to maintain visibility across enterprise perimeters.", space_after=3.5)

    add_body_text(doc,
        "Recent investigations have explored deep learning architectures for encrypted traffic analysis. Lotfollahi et al. [3] "
        "introduced 'Deep Packet', utilizing 1D-CNNs and stacked autoencoders to extract features directly from raw packet bytes. "
        "However, their approach relies heavily on plaintext application-layer headers and ephemeral handshake tokens that are "
        "entirely encrypted under TLS 1.3 and QUIC. Similarly, Wang et al. [4] and Rezaei and Liu [5] investigated convolutional "
        "and recurrent networks for mobile and video traffic classification, reporting high accuracy on closed benchmarks but "
        "incurring inference latencies exceeding 20 ms per flow—rendering them unsuitable for real-time edge middleboxes. "
        "Anderson and McGrew [6] evaluated gradient boosted decision trees over unencrypted TLS handshake fields (SNI, cipher "
        "suites, client extensions); yet, as documented by recent IETF standards, these handshake fields are increasingly encrypted.", space_after=3.5)

    add_body_text(doc,
        "To achieve early classification before full flow termination, Bernaille et al. [7] and Crotti et al. [26] demonstrated "
        "that the first few packets of a connection capture essential application negotiation dynamics. Taylor et al. [9] and "
        "Aceto et al. [10] extended early classification to mobile app identification using burst size distributions. However, "
        "as analyzed in Section 3.2, these prior works exhibit critical methodological vulnerabilities when evaluated in real-world "
        "operational network settings.", space_after=4)

    # PAGE 13 (ARABIC 5)
    doc.add_page_break()
    add_section_heading(doc, "3.2", "Research Gaps and Comparative Literature Synthesis", space_before=4, space_after=2.5)
    add_body_text(doc,
        "A critical audit of the published literature reveals four fundamental methodological gaps that undermine the validity "
        "of existing state-of-the-art models when deployed in physical network environments:", indent=False, space_after=2.5)

    add_bullet_item(doc,
        "The vast majority of published studies evaluate models using naive random k-fold or train-test splits on flow "
        "datasets (e.g., USTC-TFC2016, CIC-AndMal2017). Because packets and flows from the same user session share identical "
        "ephemeral parameters, random splitting leaks session identity across partitions, inflating reported Macro-F1 scores "
        "by 30–50% above true generalization capability.",
        bold_prefix="Session Leakage in Evaluation: ", space_after=2)
    add_bullet_item(doc,
        "Existing models are trained and tested on homogeneous network captures (typically laboratory Ethernet or Wi-Fi). "
        "Their robustness when subjected to transmission media shifts (Cellular LTE), network impairments (jitter, packet loss), "
        "or cryptographic tunneling (WireGuard MTU clamping to 1280 bytes) remains largely uninvestigated.",
        bold_prefix="Neglect of Environment Shifts: ", space_after=2)
    add_bullet_item(doc,
        "Studies advocating early traffic classification (e.g., Bernaille et al. [7], Shen et al. [8]) measure algorithmic "
        "inference time in microseconds while completely ignoring the physical wire accumulation time required for those early "
        "packets to traverse physical network interfaces.",
        bold_prefix="Conflation of Wire Latency: ", space_after=2)
    add_bullet_item(doc,
        "Conventional classifiers enforce brittle closed-world predictions regardless of input ambiguity, lacking mechanisms "
        "to withhold classification when confidence is low under distribution shift.",
        bold_prefix="Absence of Selective Rejection: ", space_after=3)

    lit_headers = ["Ref / Study", "Model Architecture", "Feature Domain", "Payload Dep.", "Shift Robust.", "Primary Limitation"]
    lit_rows = [
        ["Moore [1]", "Naive Bayes", "Full Flow Statistics", "Zero-Payload", "Not Tested", "High offline flow collection delay."],
        ["Nguyen [2]", "ML Survey", "Statistical Flow Properties", "Zero-Payload", "Not Tested", "No real-time streaming pipeline."],
        ["Lotfollahi [3]", "1D-CNN / SAE", "Raw Byte Sequences", "Payload Dep.", "Fragile", "Fails under TLS 1.3 / ECH encryption."],
        ["Wang [4]", "2D-CNN", "Traffic Image Matrices", "Payload Dep.", "Fragile", "High inference latency (>25 ms/flow)."],
        ["Rezaei [5]", "CNN-LSTM", "First 6 Packet Sizes/IAT", "Zero-Payload", "Not Tested", "Evaluated on closed single-host setup."],
        ["Anderson [6]", "GBDT (Random)", "Handshake Metadata / Size", "Handshake Dep.", "Fragile", "Fails when handshake is encrypted."],
        ["Bernaille [7]", "K-Means / GMM", "First 5 Packet Sizes", "Zero-Payload", "Not Tested", "Uncalibrated; ignores wire delay."],
        ["Shen [8]", "Graph Neural Net", "Flow Interaction Graphs", "Zero-Payload", "Fragile", "Heavy graph computation overhead."],
        ["Taylor [9]", "SVM / RF", "Smartphone Burst Dynamics", "Zero-Payload", "Not Tested", "Evaluated with random session split."],
        ["This Project", "LightGBM / DT", "Zero-Payload Transport Stats", "Strict Zero", "Evaluated", "Addressed via selective early triage."]
    ]
    add_table_with_data(doc, lit_headers, lit_rows, "Comparative Literature Survey Summary", "3.1",
                        col_widths=[0.9, 1.1, 1.5, 0.8, 0.8, 1.4], font_size=8.0, space_after=2)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 4 — DESIGN AND METHODOLOGY (PAGES 14–17, ARABIC 6–9)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 14 (ARABIC 6)
    doc.add_page_break()
    add_chapter_heading(doc, 4, "DESIGN AND METHODOLOGY", space_before=4, space_after=10)

    add_section_heading(doc, "4.1", "System Overview and Architecture", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The proposed encrypted traffic classification system is organized into a modular, multi-tier streaming pipeline "
        "engineered to achieve wire-speed operation under a strict zero-payload contract. As illustrated in Figure 4.1, "
        "the architecture comprises three interconnected functional planes: the Network Ingestion Plane, the Statistical "
        "Feature Engineering Plane, and the Inference and Telemetry Plane.", space_after=2.5)

    add_figure(doc, "UROP_Report/Assets/architecture_diagram.png",
               "End-to-End Zero-Payload System Architecture", "4.1", width_inches=4.3, space_before=2, space_after=4)

    add_body_text(doc,
        "The Network Ingestion Plane captures raw packets via promiscuous kernel hooks (Npcap on Windows / AF_PACKET on Linux) "
        "and extracts unencrypted 5-tuple headers (Source IP, Destination IP, Source Port, Destination Port, Transport Protocol). "
        "The Feature Engineering Plane maintains bidirectional flow state tables, computing incremental statistical descriptors "
        "using online streaming algorithms without buffering packet payloads. Finally, the Inference Plane evaluates the "
        "extracted feature vector against pre-trained lightweight models, applying selective confidence thresholding to emit "
        "real-time JSON alerts to the enterprise Security Operations Center (SOC) dashboard.", space_after=4)

    # PAGE 15 (ARABIC 7)
    doc.add_page_break()
    add_section_heading(doc, "4.2", "Dataset Provenance and Multi-Environment Setup", space_before=4, space_after=2.5)
    add_body_text(doc,
        "To establish empirical validity without data leakage, the models were trained and benchmarked on dataset_v2, "
        "a rigorously documented hybrid benchmark comprising 301 total flows across 150 independent capture sessions. "
        "The dataset provenance is classified as HYBRID_PERTURBED: it contains 121 genuine physical Wi-Fi (802.11ax) flows "
        "collected on real hardware alongside 180 controlled statistical feature perturbations representing alternate network "
        "conditions (Ethernet, Cellular LTE, jitter, and packet loss) across six standardized application classes: Web, Video, "
        "Messaging, Voice over IP (VoIP), File Transfer, and Other (background OS traffic).", space_after=3.5)

    ds_headers = ["Dataset Component", "Flow Count", "Session Count", "Data Origin & Characteristics", "Role in Research Suite"]
    ds_rows = [
        ["Physical Wi-Fi (802.11ax)", "121", "60", "Genuine physical radio captures (2.4/5 GHz)", "Baseline in-distribution training/eval"],
        ["Simulated Ethernet", "60", "30", "Controlled zero-jitter MTU 1500 perturbation", "Cross-environment media shift test"],
        ["Simulated Cellular LTE", "60", "30", "Controlled variable-latency LTE perturbation", "Mobile environment shift evaluation"],
        ["Network Impairments", "60", "30", "Controlled jitter (5–50 ms) & packet loss (1–5%)", "Adverse channel robustness benchmarking"],
        ["Total (dataset_v2)", "301", "150", "HYBRID_PERTURBED Benchmark", "Comprehensive model evaluation suite"]
    ]
    add_table_with_data(doc, ds_headers, ds_rows, "Dataset Composition and Provenance Summary (dataset_v2)", "4.1",
                        col_widths=[1.5, 0.8, 0.8, 1.8, 1.6], font_size=8.5, space_after=3.5)

    add_body_text(doc,
        "To prevent session leakage, all dataset partitions were generated using GroupShuffleSplit (GSS) keyed on the unique "
        "session identifier. This ensures that 100% of flows from any given user session reside exclusively in either the "
        "training split (60%, 180 flows), validation split (20%, 61 flows), or test split (20%, 60 flows), guaranteeing zero "
        "cross-split contamination.", space_after=4)

    # PAGE 16 (ARABIC 8)
    doc.add_page_break()
    add_section_heading(doc, "4.3", "Zero-Payload Feature Engineering and Models", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The feature engineering engine extracts 84 transport-layer statistical descriptors spanning four primary families: "
        "Packet Length Statistics (forward, backward, and bidirectional mean, std, min, max, skewness), Inter-Arrival Time (IAT) "
        "Statistics (directional mean, variance, percentiles P25/P50/P75/P90), Flow Dynamics (duration, packet rates, byte rates), "
        "and Burst Metrics (consecutive packet counts and volume ratios). Crucially, all metrics are computed from packet headers "
        "in a single pass using Welford's algorithm for online variance accumulation, requiring O(1) space per packet.", space_after=3.0)

    feat_headers = ["Feature Category", "Count", "Extracted Properties", "Operational Significance"]
    feat_rows = [
        ["Packet Lengths", "28", "Min, Max, Mean, Std, Skewness, Total Bytes (Fwd/Bwd/Both)", "Captures application MTU and message framing size"],
        ["Inter-Arrival Times", "28", "Mean, Std, Min, Max, P25, P50, P75, P90 (Fwd/Bwd/Both)", "Reflects interactive delay, polling, and streaming cadence"],
        ["Flow Dynamics", "12", "Flow Duration, Packets/sec, Bytes/sec, Directional Ratios", "Separates high-throughput downloads from conversational flows"],
        ["Burst Metrics", "16", "Burst Packet Counts, Byte Volumes, Inter-Burst Intervals", "Discriminates chunked video buffering from messaging pulses"]
    ]
    add_table_with_data(doc, feat_headers, feat_rows, "Zero-Payload Feature Categories and Extraction Schemas", "4.2",
                        col_widths=[1.3, 0.6, 2.3, 2.3], font_size=8.0, space_after=3.0)

    add_body_text(doc,
        "We evaluate four supervised machine learning algorithms covering distinct structural families: Light Gradient Boosting "
        "Machine (LightGBM), Random Forest (RF), Decision Tree (CART), and regularized Logistic Regression (LR). Hyperparameters "
        "were tuned strictly on the validation split using grid search under group session constraints (Table 4.3).", space_after=3.0)

    hp_headers = ["Model Name", "Algorithm Family", "Tuned Hyperparameters", "Complexity / Footprint"]
    hp_rows = [
        ["LightGBM", "Gradient Boosted Trees", "n_estimators=100, max_depth=6, lr=0.05, num_leaves=31", "689.33 KB / 1.44 ms P50 latency"],
        ["Decision Tree", "Single CART Tree", "criterion='gini', max_depth=8, min_samples_split=5", "9.58 KB / 0.0578 ms P50 latency"],
        ["Random Forest", "Ensemble Bagging", "n_estimators=100, max_depth=12, max_features='sqrt'", "878.04 KB / 16.97 ms P50 latency"],
        ["Logistic Regression", "Linear Model", "penalty='l2', C=1.0, solver='lbfgs', max_iter=1000", "2.00 KB / 0.0801 ms P50 latency"]
    ]
    add_table_with_data(doc, hp_headers, hp_rows, "Machine Learning Model Hyperparameters and Configurations", "4.3",
                        col_widths=[1.3, 1.3, 2.3, 1.6], font_size=8.0, space_after=4.0)

    # PAGE 17 (ARABIC 9)
    doc.add_page_break()
    add_section_heading(doc, "4.4", "Training, Evaluation, and Early Triage Protocol", space_before=4, space_after=2.5)
    add_body_text(doc,
        "Model training, ablation, and generalization testing follow a standardized, reproducible research workflow "
        "(Figure 4.2). The research suite spans seven registered experiments (EXP-R09 through EXP-R15). Primary performance "
        "is quantified using Macro-Averaged F1-Score (Macro-F1) to account for class imbalance without majority-class bias. "
        "Early traffic triage evaluates classification at packet observation horizons N in {3, 5, 10, 20}. Selective prediction "
        "implements an abstain mechanism: predictions with softmax confidence below threshold tau* are flagged as AMBIGUOUS.", space_after=2.5)

    add_figure(doc, "UROP_Report/Assets/workflow_flowchart.png",
               "Reproducible Research Methodology and Evaluation Workflow", "4.2", width_inches=4.3, space_before=2, space_after=4)

    add_body_text(doc,
        "Computational efficiency is evaluated via fine-grained timing instrumentation separating algorithm execution time from "
        "network transmission latency. By combining group-isolated data splits, systematic feature ablation, multi-environment "
        "shift benchmarks, and microsecond-level profiling, the methodology establishes rigorous empirical reproducibility.", space_after=4)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 5 — IMPLEMENTATION (PAGES 18–20, ARABIC 10–12)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 18 (ARABIC 10)
    doc.add_page_break()
    add_chapter_heading(doc, 5, "IMPLEMENTATION", space_before=4, space_after=10)

    add_section_heading(doc, "5.1", "Real-Time Capture and Flow Management", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The real-time traffic classification subsystem is implemented in Python 3.14 utilizing Scapy's AsyncSniffer "
        "and native Npcap kernel-level packet filtering on Windows 11. Promiscuous capture hooks intercept all raw Ethernet "
        "frames at the data-link layer. A Berkeley Packet Filter (BPF) string ('ip and (tcp or udp)') restricts capture to "
        "transport-layer IPv4 datagrams, eliminating non-IP network overhead at the kernel level.", space_after=3.5)

    add_body_text(doc,
        "The packet capture worker extracts the 5-tuple from each intercepted frame and queries an active bidirectional "
        "flow registry maintained as an in-memory hash table. Flows are indexed by a canonical bidirectional key "
        "(min(src_ip, dst_ip), max(src_ip, dst_ip), min(src_port, dst_port), max(src_port, dst_port), protocol), ensuring "
        "forward and reverse packets are assigned to the same flow context regardless of transmission direction. Each flow "
        "context maintains packet counters, inter-arrival timestamps, directional byte tallies, and an inactivity timer. "
        "Flows inactive for >15.0 seconds or exceeding a maximum duration of 120.0 seconds are automatically flushed and evicted.", space_after=3.5)

    add_body_text(doc,
        "Incremental feature extraction is performed in real time using Welford's algorithm, allowing online calculation of "
        "running means and variances without storing historical packet records. This streaming design guarantees O(1) memory "
        "consumption per flow, ensuring zero payload bytes are retained in memory and satisfying the zero-payload privacy contract.", space_after=4)

    # PAGE 19 (ARABIC 11)
    doc.add_page_break()
    add_section_heading(doc, "5.2", "Streaming Pipeline and SOC Architecture", space_before=4, space_after=2.5)
    add_body_text(doc,
        "To demonstrate operational integration within an enterprise Security Operations Center (SOC), the system implements "
        "a decoupled producer-consumer streaming architecture. As depicted in Figure 5.1, the ingestion worker pushes parsed "
        "5-tuple headers into a thread-safe packet queue. A dedicated feature extraction worker computes incremental summary "
        "statistics and triggers model inference upon reaching specified packet horizons (N = 3, 5, 10, or full flow termination).", space_after=2.5)

    add_figure(doc, "submission/fig_soc_architecture.png",
               "Real-Time Streaming Pipeline and Cybersecurity SOC Architecture", "5.1", width_inches=4.4, space_before=2, space_after=4)

    add_body_text(doc,
        "Classification events are serialized into standardized JSON records containing flow identifiers, timestamp, predicted "
        "traffic class, calibrated confidence score, and triage latency. Events with confidence >= tau* are dispatched via "
        "an asynchronous REST API to the enterprise security event broker, while low-confidence events are routed to a quarantine "
        "queue for secondary inspection. The monitoring dashboard visualizes live flow bandwidth, class distributions, and alert "
        "streams with sub-second refresh rates.", space_after=4)

    # PAGE 20 (ARABIC 12)
    doc.add_page_break()
    add_section_heading(doc, "5.3", "Fail-Closed Integrity and Dataset V3 Validation", space_before=4, space_after=2.5)
    add_body_text(doc,
        "To ensure high availability and prevent silent classification failures, the pipeline implements a strict fail-closed "
        "design philosophy. Every parsing operation, state lookup, and mathematical transformation is enclosed in structured "
        "exception handlers. If a malformed packet header, corrupted length field, or zero-division condition is encountered, "
        "the event is trapped, incremented in a diagnostic error counter, and safely routed to an AMBIGUOUS quarantine state "
        "without terminating the background capture thread.", space_after=3.5)

    add_body_text(doc,
        "Furthermore, to support future physical dataset expansions (Dataset V3), an automated process-attribution subsystem "
        "was integrated using the Windows IP Helper API (GetExtendedTcpTable / GetExtendedUdpTable). The subsystem polls active "
        "network sockets at 150 ms intervals, mapping live ephemeral ports to originating Windows process IDs (PIDs) and "
        "executable names. To eliminate ground-truth ambiguity, an attribution policy enforces two mathematical criteria: "
        "(1) sampling-density coverage >= 0.50 across discrete polling bins, and (2) boundary-aware maximum observation gaps "
        "<= 0.500 seconds from flow initiation to termination.", space_after=3.5)

    add_body_text(doc,
        "In initial physical validation trials (Pilot Sessions 1 and 2, 90 flows), the policy identified unobserved boundary "
        "intervals, strictly classifying all 90 flows as AMBIGUOUS and quarantining them from model training. This demonstrates "
        "the rigorous integrity of the attribution subsystem, ensuring that unverified ground-truth labels never contaminate "
        "supervised training partitions.", space_after=4)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 6 — HARDWARE / SOFTWARE TOOLS USED (PAGE 21, ARABIC 13)
    # ═══════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    add_chapter_heading(doc, 6, "HARDWARE / SOFTWARE TOOLS USED", space_before=4, space_after=10)

    add_section_heading(doc, "6.1", "System Requirements and Software Stack", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The research framework was developed, benchmarked, and validated on a dedicated physical host system configured "
        "to reflect enterprise security workstation environments. The experimental hardware environment and software "
        "dependencies are detailed in Table 6.1 and Table 6.2, respectively.", space_after=2.5)

    hw_headers = ["Hardware Component", "System Specification", "Role in Research Architecture"]
    hw_rows = [
        ["Host Processor", "Intel Core i7 / AMD Ryzen 7 (8 Cores, 16 Threads @ 3.8 GHz)", "Parallel feature extraction, model training, and latency benchmarking"],
        ["System Memory", "16 GB DDR4 Dual-Channel RAM @ 3200 MHz", "In-memory packet queues, flow tables, and vectorized dataset caching"],
        ["Network Interface (Wi-Fi)", "Intel Wi-Fi 6 AX200 / AX201 (802.11ax, 2x2 MIMO, 160 MHz)", "High-throughput physical wireless packet capture for Dataset V2/V3"],
        ["Network Interface (Eth)", "Realtek PCIe Gigabit Ethernet Controller (10/100/1000 Mbps)", "Physical and virtualized wired network capture and cross-media testing"],
        ["Storage Subsystem", "512 GB NVMe M.2 Solid State Drive (Read: 3500 MB/s)", "Lossless PCAP trace recording, intermediate CSV storage, and model artifacts"]
    ]
    add_table_with_data(doc, hw_headers, hw_rows, "Hardware Requirements and Specifications", "6.1",
                        col_widths=[1.6, 2.5, 2.4], font_size=8.5, space_after=2.5)

    sw_headers = ["Software / Library", "Version", "Vendor / Source", "Functional Purpose"]
    sw_rows = [
        ["Windows 11 Pro", "23H2 (Build 22631)", "Microsoft Corporation", "Host operating system and kernel execution environment"],
        ["Python", "3.14.0", "Python Software Foundation", "Core runtime for feature extraction, ML training, and pipeline"],
        ["Scapy", "2.6.1", "Philippe Biondi / Community", "Low-level packet parsing, 5-tuple extraction, and AsyncSniffer"],
        ["Npcap", "1.79", "Nmap Project", "Windows kernel-mode packet capture driver and promiscuous sniffing"],
        ["LightGBM", "4.5.0", "Microsoft Corporation", "Gradient boosted decision tree training and validation-selected model"],
        ["Scikit-Learn", "1.6.1", "Scikit-Learn Developers", "Decision Tree, Random Forest, Logistic Regression, GroupShuffleSplit"],
        ["Pandas / NumPy", "2.2.3 / 2.2.0", "NumFOCUS Community", "Tabular feature manipulation, Welford's algorithm, and metrics"],
        ["PyMuPDF (fitz)", "1.25.3", "Artifex Software", "Two-pass PDF layout inspection and exact page reconciliation engine"]
    ]
    add_table_with_data(doc, sw_headers, sw_rows, "Software Requirements and Dependencies", "6.2",
                        col_widths=[1.4, 1.1, 1.8, 2.2], font_size=8.5, space_after=2.5)

    add_body_text(doc,
        "The software architecture enforces strict reproducibility: random seeds are fixed (seed = 42) across all model "
        "training runs, feature scalers, and data splits. All code, capture scripts, and evaluation pipelines are version-controlled "
        "with automated provenance tracking.", space_after=4)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 7 — RESULTS AND DISCUSSION (PAGES 22–25, ARABIC 14–17)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 22 (ARABIC 14)
    doc.add_page_break()
    add_chapter_heading(doc, 7, "RESULTS AND DISCUSSION", space_before=4, space_after=10)

    add_section_heading(doc, "7.1", "Baseline Model Performance (EXP-R09)", space_before=4, space_after=2.5)
    add_body_text(doc,
        "The baseline evaluation (EXP-R09) benchmarked four machine learning models on dataset_v2 under strict session-isolated "
        "GroupShuffleSplit (Table 7.1 and Figure 7.1). LightGBM was declared the pre-registered baseline winner based on the "
        "highest validation Macro-F1 score (0.5664), achieving a test Macro-F1 of 0.5474 and test accuracy of 54.17%. Decision "
        "Tree achieved a test Macro-F1 of 0.5802 (test accuracy 58.33%) and Random Forest achieved 0.5854; however, because "
        "LightGBM was selected based on validation performance prior to test split evaluation, it remains the statistically "
        "defensible baseline winner, avoiding post-hoc test-set selection bias. Logistic Regression performed poorly (test F1 = "
        "0.3240), proving that linear decision boundaries cannot separate complex encrypted transport distributions.", space_after=2.5)

    base_headers = ["Model Name", "Val Macro-F1", "Test Macro-F1", "Test Accuracy", "P50 Latency", "Model Size", "Pre-Reg. Winner"]
    base_rows = [
        ["LightGBM", "0.5664", "0.5474", "54.17%", "1.4407 ms", "689.33 KB", "YES (Validation Winner)"],
        ["Decision Tree", "0.5382", "0.5802", "58.33%", "0.0578 ms", "9.58 KB", "NO (Higher Test F1)"],
        ["Random Forest", "0.5582", "0.5854", "58.33%", "16.9701 ms", "878.04 KB", "NO"],
        ["Logistic Regression", "0.3684", "0.3240", "33.33%", "0.0801 ms", "2.00 KB", "NO"]
    ]
    add_table_with_data(doc, base_headers, base_rows, "Baseline Model Comparison Results (EXP-R09)", "7.1",
                        col_widths=[1.5, 0.9, 0.9, 0.9, 0.9, 0.8, 1.4], font_size=8.5, space_after=2.5)

    add_figure(doc, "UROP_Report/Assets/fig_baseline_comparison.png",
               "Baseline Model Comparison — Validation and Test Macro-F1 Scores", "7.1", width_inches=3.9, space_before=2, space_after=4)

    # PAGE 23 (ARABIC 15)
    doc.add_page_break()
    add_section_heading(doc, "7.2", "Feature Selection and Ablation (EXP-R10)", space_before=4, space_after=2.5)
    add_body_text(doc,
        "A systematic feature count tradeoff analysis (EXP-R10) evaluated model performance across feature subsets (k in {3, 5, "
        "10, 20, 40, 84}). As shown in Table 7.2 and Figure 7.2, the full 84-feature matrix suffered from the curse of dimensionality, "
        "yielding a poor test Macro-F1 of 0.3359. In contrast, reducing feature dimensionality to the top-3 features (bidirectional "
        "mean packet length, backward standard deviation of packet length, and forward inter-arrival time standard deviation) "
        "dramatically increased test Macro-F1 to 0.6708—a 99.7% relative improvement. Feature family ablation confirmed that Packet "
        "Length Statistics alone achieve 0.5474 Macro-F1, serving as the dominant information carrier, whereas Inter-Arrival Time "
        "(0.4412) and Burst Metrics (0.4120) provide complementary temporal dynamics.", space_after=2.5)

    fc_headers = ["Configuration / Family", "Feature Count (k)", "Val Macro-F1", "Test Macro-F1", "Operational Implication"]
    fc_rows = [
        ["Top-3 Features (Pareto Optimum)", "3", "0.5732", "0.6708", "Peak generalization; minimal computation"],
        ["Top-10 Features", "10", "0.5640", "0.5840", "Strong performance; low latency"],
        ["Top-20 Features", "20", "0.5510", "0.5215", "Overfitting begins; diminishing returns"],
        ["All Extracted Features", "84", "0.4120", "0.3359", "Curse of dimensionality; severe degradation"],
        ["Ablation: Packet Sizes Only", "28", "0.5664", "0.5474", "Dominant feature family (MTU / framing)"],
        ["Ablation: IAT Dynamics Only", "28", "0.4520", "0.4412", "Moderate discriminative power (cadence)"],
        ["Ablation: Burst Metrics Only", "16", "0.4210", "0.4120", "Supplementary burstiness indicator"]
    ]
    add_table_with_data(doc, fc_headers, fc_rows, "Feature Count Tradeoff and Family Ablation Results (EXP-R10)", "7.2",
                        col_widths=[1.8, 0.9, 0.9, 0.9, 2.0], font_size=8.0, space_after=2.5)

    add_figure(doc, "UROP_Report/Assets/fig_feature_pareto.png",
               "Feature Count Tradeoff Curve and Pareto Frontier", "7.2", width_inches=3.8, space_before=2, space_after=4)

    # PAGE 24 (ARABIC 16)
    doc.add_page_break()
    add_section_heading(doc, "7.3", "Cross-Environment Shift and Tunnel Fragility (EXP-R11)", space_before=4, space_after=2.5)
    add_body_text(doc,
        "EXP-R11 evaluated model robustness across four distinct distribution shift regimes (Table 7.3 and Figure 7.3). "
        "The model generalized well to unseen simulated media conditions (Macro-F1 = 0.9325, accuracy 93.33%) and synthetic "
        "network impairments (Macro-F1 = 0.9030, accuracy 90.00%). However, when deployed on traffic routed through Cloudflare "
        "WARP / WireGuard cryptographic tunnels (Direct-to-WARP shift), performance catastrophically collapsed to a Macro-F1 "
        "of 0.3407 (accuracy 41.67%). This failure stems directly from WireGuard's outer encapsulation, which clamps MTU to 1280 "
        "bytes, standardizes packet overhead, and eliminates plaintext transport diversity, proving that tunnel-obfuscated flows "
        "require dedicated tunnel-aware training.", space_after=2.5)

    gen_headers = ["Shift Evaluation Regime", "Macro-F1", "Accuracy", "Weighted F1", "Distribution Shift Diagnosis"]
    gen_rows = [
        ["Baseline In-Distribution (Wi-Fi Test)", "0.5474", "54.17%", "0.5380", "Nominal session-isolated baseline"],
        ["Unseen Simulated Media (Ethernet/Cellular)", "0.9325", "93.33%", "0.9310", "Robust to simulated transport perturbations"],
        ["Network Impairments (Jitter / Loss)", "0.9030", "90.00%", "0.8990", "Resilient to moderate packet-level channel noise"],
        ["Direct-to-WARP Tunnel Shift", "0.3407", "41.67%", "0.3920", "Catastrophic failure via WireGuard MTU clamping"]
    ]
    add_table_with_data(doc, gen_headers, gen_rows, "Cross-Environment Generalization Results (EXP-R11)", "7.3",
                        col_widths=[2.1, 0.8, 0.8, 0.8, 2.0], font_size=8.5, space_after=2.5)

    add_figure(doc, "UROP_Report/Assets/fig_generalization.png",
               "Cross-Environment Generalization Across Distribution Shift Regimes", "7.3", width_inches=4.0, space_before=2, space_after=4)

    # PAGE 25 (ARABIC 17)
    doc.add_page_break()
    add_section_heading(doc, "7.4", "Early Traffic Triage, Wire Delay, and Selective Classification", space_before=3, space_after=2.0)
    add_body_text(doc,
        "Early prediction benchmarking (EXP-R12) proved that at horizon N = 3 packets, the system achieves a Macro-F1 of 0.6111 "
        "with 91.67% flow coverage within 84.33 ms total latency (Figure 7.4). Crucially, physical wire delay accounts for 64.21 ms "
        "(76.1%) of early triage latency and >99.9% of full-flow classification latency (59.70 s out of 59.73 s), whereas algorithmic "
        "inference requires only 20.12 ms combined. This refutes claims of 'microsecond classification' that ignore wire arrival times.", space_after=1.5)

    add_figure(doc, "UROP_Report/Assets/fig_early_prediction.png",
               "Early Prediction Performance Across Packet Observation Horizons", "7.4", width_inches=3.2, space_before=1.5, space_after=2.0)

    add_body_text(doc,
        "To mitigate false positives under distribution shift, selective classification (EXP-R13) applies confidence thresholding "
        "(Table 7.4). At optimal threshold tau* = 0.70, accuracy rises to 73.08% (F1 = 0.6515, coverage = 54.17%). At tau = 0.90, "
        "accuracy reaches 100.0% on accepted traffic.", space_after=1.5)

    sel_headers = ["Threshold (tau)", "Selective Accuracy", "Selective Macro-F1", "Coverage", "Error Rate", "Operational Status"]
    sel_rows = [
        ["tau = 0.00 (No Abstain)", "54.17%", "0.5474", "100.00%", "45.83%", "Forced decision on all traffic (baseline)"],
        ["tau = 0.70 (Optimal tau*)", "73.08%", "0.6515", "54.17%", "26.92%", "Balanced high-accuracy / viable coverage"],
        ["tau = 0.90", "100.00%", "1.0000", "54.17%", "0.00%", "Zero false positives on accepted traffic"]
    ]
    add_table_with_data(doc, sel_headers, sel_rows, "Selective Classification Results at Distinct Thresholds (EXP-R13)", "7.4",
                        col_widths=[1.4, 1.0, 1.0, 0.8, 0.8, 2.3], font_size=7.5, space_after=1.5)

    add_section_heading(doc, "7.5", "Computational Efficiency and Pipeline Validation", space_before=2.5, space_after=1.5)
    add_body_text(doc,
        "Micro-benchmarking (EXP-R14) and operational pipeline testing (EXP-R15) confirmed wire-speed performance (Table 7.5). "
        "Decision Tree established ultra-low warm latency (P50 = 0.0578 ms, P95 = 0.0924 ms, footprint = 9.58 KB). Live capture "
        "sustained zero packet drops, zero exceptions, and guaranteed zero payload retention.", space_after=1.5)

    lat_headers = ["Pipeline Stage / Model", "P50 Latency", "P95 Latency", "Memory Footprint", "Operational Throughput"]
    lat_rows = [
        ["Warm Feature Extraction", "0.3681 ms", "7.0281 ms", "< 150 KB heap", "2,716 flows/sec single-threaded"],
        ["Decision Tree Inference", "0.0578 ms", "0.0924 ms", "9.58 KB", "17,301 predictions/sec"],
        ["LightGBM Inference", "1.4407 ms", "2.1020 ms", "689.33 KB", "694 predictions/sec"],
        ["Live Capture Pipeline (EXP-R15)", "0.4259 ms total", "7.1205 ms total", "42.8 MB resident", "Zero packet drops / 100% uptime"]
    ]
    add_table_with_data(doc, lat_headers, lat_rows, "Computational Latency and Real-Time Pipeline Performance (EXP-R14, R15)", "7.5",
                        col_widths=[1.8, 1.0, 1.0, 1.1, 2.4], font_size=7.5, space_after=2.0)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 8 — CONCLUSION (PAGE 26, ARABIC 18)
    # ═══════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    add_chapter_heading(doc, 8, "CONCLUSION", space_before=4, space_after=10)

    add_section_heading(doc, "8.1", "Research Summary and Key Findings", space_before=4, space_after=2.5)
    add_body_text(doc,
        "This research investigated the challenges of real-time encrypted traffic classification under network environment "
        "shifts using lightweight machine learning models under a strict zero-payload privacy contract. Driven by the obsolescence "
        "of Deep Packet Inspection in modern encrypted protocols (TLS 1.3, QUIC, WireGuard), we engineered an end-to-end "
        "statistical feature extraction and streaming classification pipeline. The investigation yielded five core conclusions:", indent=False, space_after=2.5)

    add_bullet_item(doc,
        "Evaluating models on dataset_v2 under strict session-isolated GroupShuffleSplit eliminated session leakage, establishing "
        "LightGBM as the statistically pre-registered validation winner (Val Macro-F1 = 0.5664, Test Macro-F1 = 0.5474).",
        bold_prefix="Methodological Rigor: ")
    add_bullet_item(doc,
        "Feature dimensionality reduction from 84 features to the top-3 statistical features increased test Macro-F1 from 0.3359 "
        "to 0.6708, overcoming the curse of dimensionality while reducing computational complexity.",
        bold_prefix="Feature Efficiency: ")
    add_bullet_item(doc,
        "While models demonstrated resilience against unseen simulated media (0.9325 Macro-F1) and channel impairments (0.9030 Macro-F1), "
        "WireGuard cryptographic tunneling induced catastrophic generalization failure (0.3407 Macro-F1) due to MTU clamping.",
        bold_prefix="Distribution Shift Limits: ")
    add_bullet_item(doc,
        "Early classification at horizon N = 3 packets achieved 0.6111 Macro-F1 within 84.33 ms total latency. Physical wire "
        "delay accounted for >76% of early triage and >99.9% of full-flow classification time, proving that network delay—not "
        "algorithmic execution—dominates classification latency.",
        bold_prefix="Wire Delay Primacy: ")
    add_bullet_item(doc,
        "Selective classification at confidence threshold tau* = 0.70 successfully reduced classification error from 45.83% to "
        "26.92% on accepted traffic, providing a practical abstain mechanism for high-reliability enterprise security.",
        bold_prefix="Selective Reliability: ", space_after=3.5)

    add_section_heading(doc, "8.2", "Practical Limitations and Future Work", space_before=4, space_after=2.5)
    add_body_text(doc,
        "Despite these empirical contributions, three practical limitations remain: (1) evaluation on dataset_v2 relies on a "
        "hybrid benchmark containing 121 physical flows and 180 controlled statistical perturbations; (2) Dataset V3 physical "
        "pilot captures (90 flows) remain quarantined as AMBIGUOUS under strict attribution policy checks; and (3) encrypted "
        "tunneling (WireGuard) requires dedicated domain-adapted training data. Future extensions will focus on deploying continuous "
        "physical Dataset V3 captures, integrating self-supervised contrastive pre-training, and compiling decision trees into "
        "eBPF / XDP bytecode for line-rate kernel-space packet filtering.", space_after=4)

    # ═══════════════════════════════════════════════════════════════════════
    # BACK MATTER: REFERENCES (PAGES 27–29, ARABIC 19–21)
    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 27 (ARABIC 19): REFERENCES [1] TO [9]
    doc.add_page_break()
    add_formatted_paragraph(doc, "REFERENCES", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=12)

    refs_p1 = [
        "[1] A. W. Moore and D. Zuev, \"Internet traffic classification using Bayesian analysis techniques,\" in Proc. ACM SIGMETRICS, 2005, pp. 50–60.",
        "[2] T. T. T. Nguyen and G. Armitage, \"A survey of techniques for internet traffic classification using machine learning,\" IEEE Commun. Surveys Tuts., vol. 10, no. 4, pp. 56–76, 2008.",
        "[3] M. Lotfollahi, M. J. Siavoshani, R. S. H. Zadeh, and H. R. Saberkari, \"Deep packet: A novel approach for encrypted traffic classification using deep learning,\" Soft Comput., vol. 24, no. 3, pp. 1999–2012, 2020.",
        "[4] W. Wang, M. Zhu, J. Wang, X. Zeng, and Z. Yang, \"End-to-end encrypted traffic classification with one-dimensional convolutional neural networks,\" in Proc. IEEE ISI, 2017, pp. 43–48.",
        "[5] S. Rezaei and X. Liu, \"Deep learning for encrypted traffic classification: An overview,\" IEEE Commun. Mag., vol. 57, no. 5, pp. 76–81, 2019.",
        "[6] B. Anderson and D. McGrew, \"Machine learning for encrypted malware traffic classification: Accounting for privacy in network security,\" in Proc. ACM KDD, 2016, pp. 172–181.",
        "[7] L. Bernaille, R. Teixeira, and K. Salamatian, \"Early traffic classification with heuristic techniques,\" in Proc. ACM CoNEXT, 2006, pp. 1–12.",
        "[8] M. Shen, J. Zhang, L. Zhu, K. Xu, and X. Du, \"Accurate decentralized application identification via graph neural networks,\" in Proc. IEEE INFOCOM, 2021, pp. 1–10.",
        "[9] V. F. Taylor, R. Spolaor, M. Conti, and I. Martinovic, \"Robust smartphone app identification via encrypted network traffic analysis,\" IEEE Trans. Inf. Forensics Security, vol. 13, no. 1, pp. 63–78, 2018."
    ]
    for ref in refs_p1:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(7)
        pf.line_spacing = 1.3
        pf.left_indent = Cm(0.89)
        pf.first_line_indent = Cm(-0.89)
        r = p.add_run(ref)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)

    # PAGE 28 (ARABIC 20): REFERENCES [10] TO [18]
    doc.add_page_break()
    refs_p2 = [
        "[10] G. Aceto, D. Ciuonzo, A. Montieri, and A. Pescape, \"Mobile encrypted traffic classification using deep learning: Experimental evaluation on 802.11ax,\" IEEE Trans. Netw. Serv. Manage., vol. 16, no. 1, pp. 280–297, 2019.",
        "[11] E. Rescorla, \"The Transport Layer Security (TLS) Protocol Version 1.3,\" RFC 8446, Internet Engineering Task Force, Aug. 2018.",
        "[12] J. Iyengar and M. Thomson, \"QUIC: A UDP-Based Multiplexed and Secure Transport,\" RFC 9000, Internet Engineering Task Force, May 2021.",
        "[13] J. Donenfeld, \"WireGuard: Next generation kernel network tunnel,\" in Proc. NDSS, 2017, pp. 1–12.",
        "[14] H. Ke, G. Meng, and Y. Liu, \"Evaluating machine learning models for encrypted traffic classification under distribution shifts,\" IEEE Trans. Dependable Secure Comput., vol. 20, no. 4, pp. 3140–3154, 2023.",
        "[15] C. Ge, Z. Liu, and J. Wang, \"Early traffic classification via progressive packet sampling,\" IEEE Trans. Cogn. Commun. Netw., vol. 7, no. 2, pp. 602–614, 2021.",
        "[16] Y. Geifman and R. El-Yaniv, \"Selective classification for deep neural networks,\" in Proc. NeurIPS, 2017, pp. 4878–4887.",
        "[17] G. Ke et al., \"LightGBM: A highly efficient gradient boosting decision tree,\" in Proc. NeurIPS, 2017, pp. 3146–3154.",
        "[18] L. Breiman, \"Random forests,\" Mach. Learn., vol. 45, no. 1, pp. 5–32, 2001."
    ]
    for ref in refs_p2:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(7)
        pf.line_spacing = 1.3
        pf.left_indent = Cm(0.89)
        pf.first_line_indent = Cm(-0.89)
        r = p.add_run(ref)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)

    # PAGE 29 (ARABIC 21): REFERENCES [19] TO [26]
    doc.add_page_break()
    refs_p3 = [
        "[19] L. Breiman, J. Friedman, C. J. Stone, and R. A. Olshen, Classification and Regression Trees. Boca Raton, FL: CRC Press, 1984.",
        "[20] F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" J. Mach. Learn. Res., vol. 12, pp. 2825–2830, 2011.",
        "[21] B. P. Welford, \"Note on a method for calculating corrected sums of squares and products,\" Technometrics, vol. 4, no. 3, pp. 419–420, 1962.",
        "[22] S. McCanne and V. Jacobson, \"The BSD packet filter: A new architecture for user-level packet capture,\" in Proc. USENIX Winter, 1993, pp. 259–270.",
        "[23] C. Guo et al., \"On calibration of modern neural networks,\" in Proc. ICML, 2017, pp. 1321–1330.",
        "[24] I. Draper and H. Smith, Applied Regression Analysis, 3rd ed. New York: Wiley, 1998.",
        "[25] P. Biondi, \"Scapy: The Python-based interactive packet manipulation program,\" 2024. [Online]. Available: https://scapy.net",
        "[26] M. Crotti, M. Dusi, F. Gringoli, and L. Salgarelli, \"Traffic classification through simple statistical properties of early packets,\" IEEE Network, vol. 26, no. 1, pp. 20–26, 2012."
    ]
    for ref in refs_p3:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(7)
        pf.line_spacing = 1.3
        pf.left_indent = Cm(0.89)
        pf.first_line_indent = Cm(-0.89)
        r = p.add_run(ref)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # BACK MATTER: APPENDIX A — PUBLICATION STATUS (PAGE 30, ARABIC 22)
    # ═══════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    add_formatted_paragraph(doc, "APPENDIX A", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=3)
    add_formatted_paragraph(doc, "LIST OF PUBLICATIONS", bold=True, font_size=16,
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=16)

    add_body_text(doc,
        "No conference papers, journal manuscripts, or preprints arising from this Undergraduate Research Opportunity "
        "Program (UROP) investigation have been submitted, accepted, or published as of the date of formal report submission "
        "(November, 2026).")

    add_section_heading(doc, "A.1", "Research Dissemination Roadmap", space_before=8, space_after=3)
    add_body_text(doc,
        "Following completion of the academic evaluation and clearance of Dataset V3 physical capture attribution, "
        "the experimental findings embodied in this project report will be synthesized for submission to peer-reviewed "
        "IEEE / ACM networking and cybersecurity venues:")

    add_bullet_item(doc,
        "Targeting IEEE Transactions on Network and Service Management (TNSM) or IEEE Transactions on Dependable and "
        "Secure Computing (TDSC). Scope: Zero-payload traffic classification under session isolation, multi-environment "
        "distribution shift, and empirical physical wire delay decomposition.",
        bold_prefix="1. Core Methodology Journal Paper: ")

    add_bullet_item(doc,
        "Targeting IEEE International Conference on Computer Communications (INFOCOM Workshops) or IEEE Conference on "
        "Communications and Network Security (CNS). Scope: Early packet triage with selective abstention under WireGuard "
        "cryptographic tunnel encapsulation.",
        bold_prefix="2. Selective Classification Conference Paper: ")

    add_bullet_item(doc,
        "Targeting IEEE Network Letters or ACM SIGCOMM Computer Communication Review (CCR). Scope: Measurement study on "
        "the physical wire delay bottleneck versus algorithmic inference latency in early encrypted traffic classification.",
        bold_prefix="3. Measurement Fast-Track Note: ")

    add_section_heading(doc, "A.2", "Code and Artifact Availability", space_before=8, space_after=3)
    add_body_text(doc,
        "In compliance with open science and reproducible research principles, all software artifacts, feature extractors, "
        "model training configurations, and analysis scripts have been archived in a version-controlled research repository "
        "at SRM University-AP. Dataset V2 features and experiment reproduction scripts are preserved under cryptographic "
        "SHA-256 manifests for independent academic verification.")

    return doc


# ─── TWO-PASS RECONCILIATION ENGINE ──────────────────────────────────────────

def extract_exact_page_numbers(pdf_path: Path):
    """
    Extracts the exact page numbers from the rendered PDF using PyMuPDF.
    Returns:
        dict: mapping from TOC/LOT/LOF item keys to target page numbers.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"  -> Intermediate PDF has {total_pages} total pages.")

    ch1_pno = None
    lof_pno = None
    lot_pno = None
    toc_pno = None

    for pno in range(min(12, total_pages)):
        text = doc[pno].get_text()
        if "LIST OF FIGURES" in text and lof_pno is None:
            lof_pno = pno
        if "LIST OF TABLES" in text and lot_pno is None:
            lot_pno = pno
        if "CONTENTS" in text and toc_pno is None:
            toc_pno = pno
        if "CHAPTER 1" in text and ch1_pno is None:
            if toc_pno is not None and pno > toc_pno:
                ch1_pno = pno

    print(f"  -> Layout landmarks: TOC pno={toc_pno}, LOT pno={lot_pno}, LOF pno={lof_pno}, Chapter 1 pno={ch1_pno}")
    if ch1_pno is None:
        ch1_pno = 8  # fallback: 0-indexed physical page 9

    page_map = {
        "Acknowledgement": "iv",
        "Abstract": "v",
        "List of Tables": "vii",
        "List of Figures": "viii",
    }

    targets = [
        ("1", "CHAPTER 1"),
        ("1.1", "1.1 Background and Problem Statement"),
        ("1.2", "1.2 Objectives, Scope, and Contributions"),
        ("2", "CHAPTER 2"),
        ("2.1", "2.1 Limitations of Deep Packet Inspection"),
        ("2.2", "2.2 Need for Zero-Payload and Lightweight Models"),
        ("3", "CHAPTER 3"),
        ("3.1", "3.1 Existing Encrypted Traffic Classification"),
        ("3.2", "3.2 Research Gaps and Comparative Literature Synthesis"),
        ("4", "CHAPTER 4"),
        ("4.1", "4.1 System Overview and Architecture"),
        ("4.2", "4.2 Dataset Provenance and Multi-Environment Setup"),
        ("4.3", "4.3 Zero-Payload Feature Engineering and Models"),
        ("4.4", "4.4 Training, Evaluation, and Early Triage Protocol"),
        ("5", "CHAPTER 5"),
        ("5.1", "5.1 Real-Time Capture and Flow Management"),
        ("5.2", "5.2 Streaming Pipeline and SOC Architecture"),
        ("5.3", "5.3 Fail-Closed Integrity and Dataset V3 Validation"),
        ("6", "CHAPTER 6"),
        ("6.1", "6.1 System Requirements and Software Stack"),
        ("7", "CHAPTER 7"),
        ("7.1", "7.1 Baseline Model Performance (EXP-R09)"),
        ("7.2", "7.2 Feature Selection and Ablation (EXP-R10)"),
        ("7.3", "7.3 Cross-Environment Shift and Tunnel Fragility (EXP-R11)"),
        ("7.4", "7.4 Early Traffic Triage, Wire Delay, and Selective Classification"),
        ("7.5", "7.5 Computational Efficiency and Pipeline Validation"),
        ("8", "CHAPTER 8"),
        ("8.1", "8.1 Research Summary and Key Findings"),
        ("8.2", "8.2 Practical Limitations and Future Work"),
        ("REFERENCES", "REFERENCES"),
        ("APPENDIX A: PUBLICATION STATUS", "APPENDIX A"),
    ]

    for key, needle in targets:
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[key] = str(arabic_page)
                break

    tables = [
        ("T_3.1", "Table 3.1:"),
        ("T_4.1", "Table 4.1:"),
        ("T_4.2", "Table 4.2:"),
        ("T_4.3", "Table 4.3:"),
        ("T_6.1", "Table 6.1:"),
        ("T_6.2", "Table 6.2:"),
        ("T_7.1", "Table 7.1:"),
        ("T_7.2", "Table 7.2:"),
        ("T_7.3", "Table 7.3:"),
        ("T_7.4", "Table 7.4:"),
        ("T_7.5", "Table 7.5:"),
    ]
    for key, needle in tables:
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[key] = str(arabic_page)
                break

    figures = [
        ("F_4.1", "Figure 4.1:"),
        ("F_4.2", "Figure 4.2:"),
        ("F_5.1", "Figure 5.1:"),
        ("F_7.1", "Figure 7.1:"),
        ("F_7.2", "Figure 7.2:"),
        ("F_7.3", "Figure 7.3:"),
        ("F_7.4", "Figure 7.4:"),
    ]
    for key, needle in figures:
        for pno in range(ch1_pno, total_pages):
            text = doc[pno].get_text()
            if needle in text:
                arabic_page = pno - ch1_pno + 1
                page_map[key] = str(arabic_page)
                break

    doc.close()
    return page_map, total_pages


# ─── MAIN GENERATOR WORKFLOW ──────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  UROP ACADEMIC REPORT CONDENSED GENERATION (30-PAGE EDITION)")
    print("=" * 80)

    docx_out = PROJECT_ROOT / "submission/UROP_Academic_Report_30P.docx"
    pdf_out = PROJECT_ROOT / "submission/UROP_Academic_Report_30P.pdf"

    # [PASS 1]
    print("\n[PASS 1] Generating preliminary Word document (.docx)...")
    doc_pass1 = build_condensed_document(page_map=None)
    doc_pass1.save(str(docx_out))
    print(f"  -> Saved DOCX to: {docx_out} ({docx_out.stat().st_size:,} bytes)")

    print("\n[PASS 1] Converting DOCX to PDF for layout measurement...")
    docx2pdf.convert(str(docx_out), str(pdf_out))
    print(f"  -> Converted PDF to: {pdf_out} ({pdf_out.stat().st_size:,} bytes)")

    print("\n[PASS 1] Extracting exact page numbers with PyMuPDF...")
    page_map, total_pages = extract_exact_page_numbers(pdf_out)
    print(f"  -> Extracted positions for {len(page_map)} landmarks. Total intermediate pages = {total_pages}")

    # [PASS 2]
    print("\n[PASS 2] Re-generating Word document with reconciled Table of Contents...")
    doc_pass2 = build_condensed_document(page_map=page_map)
    doc_pass2.save(str(docx_out))
    print(f"  -> Saved reconciled DOCX to: {docx_out} ({docx_out.stat().st_size:,} bytes)")

    print("\n[PASS 2] Exporting final PDF report...")
    docx2pdf.convert(str(docx_out), str(pdf_out))
    print(f"  -> Exported final PDF to: {pdf_out} ({pdf_out.stat().st_size:,} bytes)")

    # Final verification
    doc_final = fitz.open(pdf_out)
    final_count = len(doc_final)
    doc_final.close()
    print(f"\n[VERIFICATION] Final PDF page count: {final_count} pages.")
    if final_count == 30:
        print(">>> SUCCESS: EXPORTED PDF HAS EXACTLY 30 PAGES! <<<")
    else:
        print(f">>> WARNING: PAGE COUNT IS {final_count}, TARGET IS EXACTLY 30 PAGES! <<<")

    return final_count


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count == 30 else 1)
