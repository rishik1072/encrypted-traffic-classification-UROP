import pymupdf as fitz
import re

doc = fitz.open("submission/UROP_Academic_Report.pdf")

# Physical page 11 is Arabic 1.
# So Arabic page N is at physical page 10 + N (0-indexed: 9 + N).
print("Verifying TOC target pages:")

# Check TOC targets
toc_checks = [
    ("CHAPTER 1", 1),
    ("CHAPTER 2", 5),
    ("CHAPTER 3", 9),
    ("CHAPTER 4", 13),
    ("CHAPTER 5", 19),
    ("CHAPTER 6", 22),
    ("CHAPTER 7", 24),
    ("CHAPTER 8", 35),
    ("REFERENCES", 37),
    ("Table 3.1", 12),
    ("Table 4.1", 14),
    ("Table 4.2", 15),
    ("Table 4.3", 16),
    ("Table 6.1", 22),
    ("Table 6.2", 22),
    ("Table 7.1", 24),
    ("Table 7.2", 26),
    ("Table 7.3", 27),
    ("Table 7.4", 28),
    ("Table 7.5", 30),
    ("Table 7.6", 30),
    ("Table 7.7", 31),
    ("Table 7.8", 32),
    ("Figure 4.1", 13),
    ("Figure 4.2", 18),
    ("Figure 5.1", 21),
    ("Figure 7.1", 25),
    ("Figure 7.2", 26),
    ("Figure 7.3", 27),
    ("Figure 7.4", 28),
    ("Figure 7.5", 29),
    ("Figure 7.6", 30),
    ("Figure 7.7", 31),
    ("Figure 7.8", 32),
    ("Figure 7.9", 33),
]

all_passed = True
for name, expected_arabic_page in toc_checks:
    phys_idx = 10 + expected_arabic_page - 1 # 0-indexed physical page
    page_text = doc[phys_idx].get_text()
    if name in page_text:
        print(f"  [PASS] {name:<12} -> Arabic p.{expected_arabic_page:02d} (Phys p.{phys_idx+1:02d}) confirmed in page text.")
    else:
        # Check nearby pages
        found = False
        for offset in [-1, 1]:
            if 0 <= phys_idx + offset < len(doc) and name in doc[phys_idx + offset].get_text():
                print(f"  [FAIL] {name:<12} expected Arabic p.{expected_arabic_page} but found on phys p.{phys_idx + offset + 1}")
                found = True
                all_passed = False
                break
        if not found:
            print(f"  [FAIL] {name:<12} NOT FOUND near expected page!")
            all_passed = False

if all_passed:
    print("\n>>> ALL 35 CHECKED HEADINGS, TABLES, AND FIGURES MATCH THEIR TOC/LOT/LOF TARGET PAGES EXACTLY! <<<")
else:
    print("\n>>> DISCREPANCIES DETECTED <<<")

doc.close()
