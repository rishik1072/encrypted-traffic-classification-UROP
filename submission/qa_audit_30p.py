import pymupdf as fitz
from pathlib import Path

pdf_path = Path("submission/UROP_Academic_Report_30P.pdf")
img_dir = Path("submission/page_images_30p")
img_dir.mkdir(parents=True, exist_ok=True)

doc = fitz.open(str(pdf_path))
total_pages = len(doc)
print(f"Total Pages in PDF: {total_pages}")
assert total_pages == 30, f"Expected 30 pages, got {total_pages}"

print("\n--- AUDITING ALL 30 PAGES ---")
page_details = []

for i in range(total_pages):
    page = doc[i]
    pix = page.get_pixmap(dpi=150)
    img_out = img_dir / f"page_{i+1:02d}.png"
    pix.save(str(img_out))
    
    text = page.get_text().strip()
    char_count = len(text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    first_line = lines[0] if lines else "EMPTY"
    
    # Extract bottom-most block (footer)
    blocks = sorted(page.get_text("blocks"), key=lambda b: b[3], reverse=True)
    footer_text = blocks[0][4].strip().replace("\n", " ") if blocks else "NONE"
    
    # Expected page numbering
    if i == 0:
        expected_num = "None (Suppressed)"
    elif i == 1:
        expected_num = "ii"
    elif i == 2:
        expected_num = "iii"
    elif i == 3:
        expected_num = "iv"
    elif i == 4:
        expected_num = "v"
    elif i == 5:
        expected_num = "vi"
    elif i == 6:
        expected_num = "vii"
    elif i == 7:
        expected_num = "viii"
    else:
        expected_num = str(i - 7)  # Physical 9 is Arabic 1, etc.
        
    print(f"Page {i+1:02d}: Chars={char_count:<5} | ExpectedNum={expected_num:<18} | FooterBlock='{footer_text[:20]}' | Top='{first_line[:40]}'")
    page_details.append((i+1, char_count, first_line, footer_text))

print("\n--- VERIFYING EXACT TOC ALIGNMENT ---")
toc_text = doc[5].get_text() # Page 6 (0-indexed 5)
lot_text = doc[6].get_text() # Page 7 (0-indexed 6)
lof_text = doc[7].get_text() # Page 8 (0-indexed 7)

print("TOC sample lines:")
for l in toc_text.splitlines():
    if any(k in l for k in ["CHAPTER", "REFERENCES", "APPENDIX", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."]):
        print("  ", l)

print("\nLOT sample lines:")
for l in lot_text.splitlines():
    if "Table " in l:
        print("  ", l)

print("\nLOF sample lines:")
for l in lof_text.splitlines():
    if "Figure " in l:
        print("  ", l)

# Cross-check each item in TOC with actual page text
print("\n--- CHECKING TARGET LANDMARK PAGES ---")
checks = [
    ("CHAPTER 1", 1),
    ("CHAPTER 2", 3),
    ("CHAPTER 3", 4),
    ("CHAPTER 4", 6),
    ("CHAPTER 5", 10),
    ("CHAPTER 6", 13),
    ("CHAPTER 7", 14),
    ("CHAPTER 8", 18),
    ("REFERENCES", 19),
    ("APPENDIX A", 22),
    ("Table 3.1:", 5),
    ("Table 4.1:", 7),
    ("Table 4.2:", 8),
    ("Table 4.3:", 9),
    ("Table 6.1:", 13),
    ("Table 6.2:", 13),
    ("Table 7.1:", 14),
    ("Table 7.2:", 15),
    ("Table 7.3:", 15),
    ("Table 7.4:", 16),
    ("Table 7.5:", 17),
    ("Table 7.6:", 17),
    ("Figure 4.1:", 6),
    ("Figure 4.2:", 9),
    ("Figure 5.1:", 11),
    ("Figure 7.1:", 14),
    ("Figure 7.2:", 15),
    ("Figure 7.3:", 16),
    ("Figure 7.4:", 16),
]

all_ok = True
for name, arabic_pg in checks:
    # Physical page index = 8 + arabic_pg - 1 = 7 + arabic_pg
    phys_idx = 7 + arabic_pg
    p_text = doc[phys_idx].get_text()
    if name in p_text:
        print(f"  [OK] {name:<14} -> Arabic p.{arabic_pg:02d} (Phys p.{phys_idx+1:02d}) verified.")
    else:
        print(f"  [MISMATCH] {name:<14} expected on Arabic p.{arabic_pg:02d} (Phys p.{phys_idx+1:02d})!")
        all_ok = False

if all_ok:
    print("\n>>> ALL LANDMARKS 100% MATCHED! ZERO DRIFT! <<<")
else:
    print("\n>>> SOME LANDMARKS MISMATCHED! <<<")

doc.close()
