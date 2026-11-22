import pymupdf as fitz

doc = fitz.open("submission/UROP_Academic_Report.pdf")
p2 = doc[1] # Declaration
print("=== PAGE 2 BLOCKS ===")
for b in p2.get_text("blocks"):
    print(f"y0={b[1]:.1f}, y1={b[3]:.1f}: {b[4].strip().replace(chr(10), ' ')[:60]}")

p11 = doc[10] # Chapter 1
print("\n=== PAGE 11 BLOCKS ===")
for b in p11.get_text("blocks"):
    print(f"y0={b[1]:.1f}, y1={b[3]:.1f}: {b[4].strip().replace(chr(10), ' ')[:60]}")

doc.close()
