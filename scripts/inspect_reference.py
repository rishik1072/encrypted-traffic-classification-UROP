import docx

doc = docx.Document(r"C:\Users\rishi\Downloads\sample_urop.docx")

print("=== SECTIONS ===")
for i, s in enumerate(doc.sections):
    h = s.header
    f = s.footer
    h_text = " ".join(p.text for p in h.paragraphs).strip()
    f_text = " ".join(p.text for p in f.paragraphs).strip()
    print(f"Section {i}: diff_first_page={s.different_first_page_header_footer}, header='{h_text}', footer='{f_text}'")
    for p in f.paragraphs:
        print(f"   Footer p XML: {p._p.xml}")

print("\n=== PARAGRAPH BREAKDOWN ===")
for i, p in enumerate(doc.paragraphs):
    text = p.text.strip()
    if text:
        fonts = set()
        sizes = set()
        bolds = set()
        for r in p.runs:
            fonts.add(r.font.name)
            sizes.add(r.font.size.pt if r.font.size else None)
            bolds.add(r.bold)
        print(f"P{i:02d} | Style: {p.style.name:<15} | Align: {str(p.alignment):<12} | Fonts: {fonts} | Sizes: {sizes} | Bold: {bolds} | Text: {text[:60]}")

