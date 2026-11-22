import fitz
import re

def extract_doc_map(pdf_path):
    doc = fitz.open(pdf_path)
    print(f"Loaded {pdf_path} with {len(doc)} pages.")

    # Front matter search queries
    front_matter_keys = [
        ("Acknowledgement", "ACKNOWLEDGEMENT"),
        ("Abstract", "ABSTRACT"),
        ("Abbreviations", "ABBREVIATIONS"),
        ("Contents", "CONTENTS"),
        ("List of Tables", "LIST OF TABLES"),
        ("List of Figures", "LIST OF FIGURES"),
    ]

    # Chapter search queries
    chapters = [
        ("1", "INTRODUCTION TO THE PROJECT", "CHAPTER 1"),
        ("1.1", "Introduction", "1.1 Introduction"),
        ("1.2", "Background of Encrypted Network Traffic", "1.2 Background"),
        ("1.3", "Problem Statement", "1.3 Problem Statement"),
        ("1.4", "Objectives of the Project", "1.4 Objectives"),
        ("1.5", "Scope of the Project", "1.5 Scope"),
        ("1.6", "Organization of the Report", "1.6 Organization"),
        ("2", "MOTIVATION", "CHAPTER 2"),
        ("2.1", "Motivation", "2.1 Motivation"),
        ("2.2", "Limitations of Traditional Deep Packet Inspection", "2.2 Limitations"),
        ("2.3", "Need for Zero-Payload Traffic Classification", "2.3 Need for Zero-Payload"),
        ("2.4", "Need for Lightweight Machine Learning", "2.4 Need for Lightweight"),
        ("2.5", "Research Challenges", "2.5 Research Challenges"),
        ("2.6", "Project Contributions", "2.6 Project Contributions"),
        ("3", "LITERATURE SURVEY", "CHAPTER 3"),
        ("4", "DESIGN AND METHODOLOGY", "CHAPTER 4"),
        ("5", "IMPLEMENTATION", "CHAPTER 5"),
        ("6", "HARDWARE / SOFTWARE TOOLS USED", "CHAPTER 6"),
        ("7", "RESULTS AND DISCUSSION", "CHAPTER 7"),
        ("8", "CONCLUSION", "CHAPTER 8"),
        ("", "REFERENCES", "REFERENCES"),
        ("", "LIST OF PUBLICATIONS", "LIST OF PUBLICATIONS"),
    ]

    # Find the starting page of Chapter 1 (where Arabic numbering begins at 1)
    ch1_phys_page = None
    for pno, page in enumerate(doc):
        text = page.get_text()
        if "CHAPTER 1" in text:
            ch1_phys_page = pno + 1
            break
    print(f"Chapter 1 begins at physical page: {ch1_phys_page}")

    results = {}
    for num, title, needle in chapters:
        found_pno = None
        for pno, page in enumerate(doc):
            text = page.get_text()
            if needle in text:
                found_pno = pno + 1
                break
        if found_pno and ch1_phys_page:
            arabic_page = found_pno - ch1_phys_page + 1
            results[(num, title)] = str(arabic_page)
            print(f"{num} {title} -> Phys {found_pno} -> Arabic {arabic_page}")
        else:
            print(f"NOT FOUND: {needle}")

    return results

if __name__ == '__main__':
    extract_doc_map('submission/UROP_Academic_Report.pdf')
