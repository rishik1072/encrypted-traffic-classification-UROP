import fitz
import re

doc = fitz.open('submission/UROP_Academic_Report.pdf')
print('Total pages:', len(doc))

toc_queries = [
    'ACKNOWLEDGEMENT',
    'ABSTRACT',
    'CONTENTS',
    'LIST OF TABLES',
    'LIST OF FIGURES',
    'CHAPTER 1',
    '1.1',
    '1.2',
    '1.3',
    '1.4',
    '1.5',
    '1.6',
    'CHAPTER 2',
    'CHAPTER 3',
    'CHAPTER 4',
    'CHAPTER 5',
    'CHAPTER 6',
    'CHAPTER 7',
    'CHAPTER 8',
    'REFERENCES',
    'LIST OF PUBLICATIONS',
]

for q in toc_queries:
    found_pages = []
    for pno, page in enumerate(doc):
        text = page.get_text()
        if q in text:
            found_pages.append(pno + 1)
    print(f'{q:25}: found on page(s) {found_pages}')
