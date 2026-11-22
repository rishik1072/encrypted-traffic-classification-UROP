import pymupdf as fitz
import re

pdf_path = "submission/UROP_Academic_Report.pdf"
doc = fitz.open(pdf_path)

print(f"Total Pages: {len(doc)}")
print("\n=== FRONT MATTER AUDIT (Pages 1-11) ===")
for i in range(min(12, len(doc))):
    page = doc[i]
    text = page.get_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    first_3 = lines[:3] if len(lines) >= 3 else lines
    last_3 = lines[-3:] if len(lines) >= 3 else lines
    
    # Check bottom-most text for page numbers
    rects = page.get_text("blocks")
    # sort blocks by y1
    blocks_sorted = sorted(rects, key=lambda b: b[3], reverse=True)
    bottom_text = blocks_sorted[0][4].strip().replace("\n", " ") if blocks_sorted else "NONE"
    
    print(f"Phys Page {i+1:02d}: Top: '{first_3[0] if first_3 else ''}' | Bottom: '{bottom_text}'")

print("\n=== TOC PAGES (Pages 7-8) ===")
for p in [6, 7]:
    print(f"--- Physical Page {p+1} ---")
    text = doc[p].get_text()
    for line in text.split("\n"):
        if any(term in line for term in ["CHAPTER", "REFERENCES", "APPENDIX", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."]):
            print("  ", line.strip())

print("\n=== LIST OF TABLES (Page 9) ===")
text = doc[8].get_text()
for line in text.split("\n"):
    if "Table " in line:
        print("  ", line.strip())

print("\n=== LIST OF FIGURES (Page 10) ===")
text = doc[9].get_text()
for line in text.split("\n"):
    if "Figure " in line:
        print("  ", line.strip())

print("\n=== CHAPTER 1 (Page 11) ===")
page11 = doc[10]
print("Top lines of Chapter 1 page:")
for l in page11.get_text().split("\n")[:6]:
    if l.strip():
        print("  ", l.strip())
blocks_sorted = sorted(page11.get_text("blocks"), key=lambda b: b[3], reverse=True)
print("Bottom block of Chapter 1 page:", blocks_sorted[0][4].strip().replace("\n", " ") if blocks_sorted else "NONE")

doc.close()
