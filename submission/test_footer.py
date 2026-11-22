import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx2pdf
import fitz

doc = docx.Document()
section = doc.sections[0]
section.different_first_page_header_footer = True

# Regular footer (page 2 onward)
footer = section.footer
p = footer.paragraphs[0]
p.alignment = WD_ALIGN_PARAGRAPH.CENTER

fldChar1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
instrText = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
fldChar2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
fldChar3 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')

run = p.add_run()
run._r.append(fldChar1)
run._r.append(instrText)
run._r.append(fldChar2)
run._r.append(fldChar3)

doc.add_paragraph('Hello page 1 (Title page - no footer)')
doc.add_page_break()
doc.add_paragraph('Hello page 2 (Should have footer 2)')

doc.save('submission/test_page_num.docx')
docx2pdf.convert('submission/test_page_num.docx', 'submission/test_page_num.pdf')

doc_pdf = fitz.open('submission/test_page_num.pdf')
for i, page in enumerate(doc_pdf):
    print(f'Page {i+1} text:', repr(page.get_text()))
