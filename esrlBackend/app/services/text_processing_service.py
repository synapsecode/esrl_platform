import re
from typing import List, Dict

def clean_text(text: str) -> str:
    # Remove multiple newlines
    text = re.sub(r'\n{2,}', '\n\n', text)

    # Remove page numbers like "Page 12"
    text = re.sub(r'Page \d+', '', text, flags=re.IGNORECASE)

    # Fix broken words: ex-ample → example
    text = re.sub(r'-\n', '', text)

    # Remove strange unicode artifacts
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)

    return text.strip()

def is_heading(line: str) -> bool:
    line = line.strip()

    if len(line) < 5:
        return False

    # ALL CAPS
    if line.isupper() and len(line.split()) < 10:
        return True

    # Numbered heading
    if re.match(r'^\d+(\.\d+)*\s+', line):
        return True

    return False

def structure_text(text: str) -> List[Dict]:
    lines = text.splitlines()
    structured = []
    current_section = {"heading": "Introduction", "content": ""}

    for line in lines:
        if is_heading(line):
            structured.append(current_section)
            current_section = {"heading": line.strip(), "content": ""}
        else:
            current_section["content"] += line + "\n"

    structured.append(current_section)
    return structured


def normalize_heading(heading: str) -> str:
    heading = re.sub(r"\s+", " ", heading.strip())
    return heading[:120]


def structure_pages(pages_text: List[str]) -> List[Dict]:
    sections: List[Dict] = []
    for page_index, page_text in enumerate(pages_text):
        cleaned = clean_text(page_text)
        page_sections = structure_text(cleaned)
        for section in page_sections:
            sections.append({
                "heading": normalize_heading(section["heading"]),
                "content": section["content"].strip(),
                "page": page_index
            })
    return sections
