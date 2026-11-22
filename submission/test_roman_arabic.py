import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx2pdf
import fitz

doc = docx.Document()

# Section 1: Front Matter
sec1 = doc.sections[0]
sec1.different_first_page_header_footer = True

# Set Roman numeral page numbering for section 1
sectPr1 = sec1._sectPr
pgNumType1 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="lowerRoman" w:start="1"/>')
sectPr1.append(pgNumType1)

footer1 = sec1.footer
p1 = footer1.paragraphs[0]
p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
run1 = p1.add_run()
fld1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
instr1 = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
fld2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
fld3 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
run1._r.extend([fld1, instr1, fld2, fld3])

doc.add_paragraph('Title Page (Cover - no footer)')
doc.add_page_break()
doc.add_paragraph('Declaration (Page ii)')
doc.add_page_break()
doc.add_paragraph('Acknowledgement (Page iii)')

# Section 2: Main Chapters
sec2 = doc.add_section()
sec2.different_first_page_header_footer = False
sectPr2 = sec2._sectPr
pgNumType2 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="decimal" w:start="1"/>')
sectPr2.append(pgNumType2)

footer2 = sec2.footer
footer2.is_linked_to_previous = False
p2 = footer2.paragraphs[0]
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = p2.add_run()
fld4 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
instr2 = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
fld5 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
fld6 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
run2._r.extend([fld4, instr2, fld5, fld6])

doc.add_paragraph('Chapter 1 Page 1')
doc.add_page_break()
doc.add_paragraph('Chapter 1 Page 2')

doc.save('submission/test_roman_arabic.docx')
docx2pdf.convert('submission/test_roman_arabic.docx', 'submission/test_roman_arabic.pdf')

doc_pdf = fitz.open('submission/test_roman_arabic.pdf')
for i, page in enumerate(doc_pdf):
    print(f'Page {i+1} text:', repr(page.get_text().strip()))
