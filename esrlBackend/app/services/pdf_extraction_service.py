import os
import io
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import fitz
from PIL import Image
import pytesseract

UPLOAD_DIR = "storage/pdfs"
IMAGE_DIR = "storage/images"
LAST_UPLOADED_FILE = "storage/last_uploaded.json"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LAST_UPLOADED_FILE), exist_ok=True)

MIN_TEXT_THRESHOLD = 50


async def save_pdf(file) -> str:
    file_path = os.path.join(
        UPLOAD_DIR,
        f"{datetime.now().timestamp()}_{file.filename}"
    )
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path


def generate_document_id(file_path: str) -> str:
    base = os.path.basename(file_path)
    return f"doc_{int(datetime.now().timestamp())}_{base}"


def is_scanned(page) -> bool:
    blocks = page.get_text("dict")["blocks"]

    text_blocks = sum(1 for b in blocks if b["type"] == 0)
    image_blocks = sum(1 for b in blocks if b["type"] == 1)

    if text_blocks == 0 and image_blocks > 0:
        return True

    text = page.get_text().strip()
    if len(text) < MIN_TEXT_THRESHOLD and image_blocks > 0:
        return True

    return False


def ocr_page(page) -> str:
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(image)


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, List[str]]:
    doc = fitz.open(pdf_path)
    full_text = ""
    pages_text: List[str] = []

    for page_num, page in enumerate(doc):
        text = page.get_text()

        if not is_scanned(page):
            page_text = text
        else:
            page_text = ocr_page(page)

        pages_text.append(page_text)
        full_text += f"\n\n--- Page {page_num + 1} ---\n" + page_text

    return full_text, pages_text


def extract_images_from_pdf(pdf_path: str, document_id: str) -> List[Dict]:
    doc = fitz.open(pdf_path)
    image_data: List[Dict] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            image_path = f"{IMAGE_DIR}/{document_id}_p{page_index}_img{img_index}.png"
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            image_data.append({
                "id": f"{document_id}_image_{page_index}_{img_index}",
                "path": image_path,
                "page": page_index,
                "type": "image",
                "document_id": document_id
            })

    return image_data


def record_last_uploaded(file_path: str, document_id: str) -> None:
    data = {
        "path": file_path,
        "document_id": document_id,
        "timestamp": datetime.now().timestamp()
    }
    with open(LAST_UPLOADED_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps(data))


def get_last_uploaded() -> Optional[Dict]:
    if not os.path.exists(LAST_UPLOADED_FILE):
        return None
    try:
        with open(LAST_UPLOADED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None
    if not data.get("path"):
        return None
    return data
