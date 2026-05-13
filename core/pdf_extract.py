import platform
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path

from core.document_store import text_cache_path


# ============================================================
# Platform-aware OCR configuration
# ============================================================

IS_WINDOWS = platform.system() == "Windows"

WINDOWS_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
WINDOWS_POPPLER_PATH = r"C:\Program Files\poppler-25.12.0\Library\bin"

if IS_WINDOWS and Path(WINDOWS_TESSERACT_CMD).exists():
    pytesseract.pytesseract.tesseract_cmd = WINDOWS_TESSERACT_CMD


# ============================================================
# Settings
# ============================================================

MIN_EXTRACTED_CHARS = 500
OCR_DPI = 300


# ============================================================
# Text extraction using PyMuPDF
# ============================================================

def extract_text_with_pymupdf(pdf_path: Path) -> str:
    parts = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text("text")
            parts.append(
                f"\n\n--- PAGE {page_index + 1} ---\n{text}"
            )

    return "\n".join(parts).strip()


# ============================================================
# OCR extraction using Poppler + Tesseract
# ============================================================

def extract_text_with_ocr(pdf_path: Path, dpi: int = OCR_DPI) -> str:
    try:
        if IS_WINDOWS and Path(WINDOWS_POPPLER_PATH).exists():
            pages = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                poppler_path=WINDOWS_POPPLER_PATH,
            )
        else:
            # Streamlit Cloud / Linux:
            # uses poppler-utils from packages.txt
            pages = convert_from_path(
                str(pdf_path),
                dpi=dpi,
            )

    except Exception as e:
        raise RuntimeError(
            "Poppler failed while converting PDF pages to images. "
            "On Streamlit Cloud, make sure packages.txt contains: poppler-utils. "
            f"Original error: {e}"
        ) from e

    parts = []

    for page_index, image in enumerate(pages):
        try:
            text = pytesseract.image_to_string(image)
        except Exception as e:
            raise RuntimeError(
                "Tesseract OCR failed. "
                "On Streamlit Cloud, make sure packages.txt contains: tesseract-ocr. "
                f"Original error: {e}"
            ) from e

        parts.append(
            f"\n\n--- OCR PAGE {page_index + 1} ---\n{text}"
        )

    return "\n".join(parts).strip()


# ============================================================
# Main extraction/cache function
# ============================================================

def extract_and_cache_pdf_text(
    pdf_path: Path,
    force_ocr: bool = False,
) -> str:
    cache_path = text_cache_path(pdf_path)

    if cache_path.exists() and not force_ocr:
        cached_text = cache_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        return f"already cached ({len(cached_text)} characters)"

    extracted = ""

    if not force_ocr:
        extracted = extract_text_with_pymupdf(pdf_path)

    if force_ocr or len(extracted) < MIN_EXTRACTED_CHARS:
        extracted = extract_text_with_ocr(pdf_path)

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_path.write_text(
        extracted,
        encoding="utf-8",
    )

    return f"cached {len(extracted)} characters"