import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.parser import ResumeParserService
from pathlib import Path

def parse():
    pdf_path = Path(r"C:\Users\Siddhant\Downloads\Resume_SiddhantPrasad_Final.pdf")
    if not pdf_path.exists():
        print(f"Error: {pdf_path} does not exist.")
        return
        
    print(f"Parsing {pdf_path}...")
    doc = ResumeParserService.parse_resume(pdf_path)
    output_path = Path("app/tests/parsed_resume.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("--- Extracted Text ---\n")
        for i, page in enumerate(doc):
            f.write(f"=== Page {i+1} ===\n")
            f.write(page.content + "\n")
        f.write("----------------------\n")
    print(f"Written parsed text to {output_path}")

if __name__ == "__main__":
    parse()
