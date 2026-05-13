from pathlib import Path
import json

BASE_DIR = Path("data")
CASES_DIR = BASE_DIR / "cases"


def init_storage():
    CASES_DIR.mkdir(parents=True, exist_ok=True)


def safe_name(name: str) -> str:
    cleaned = "".join(
        c for c in name if c.isalnum() or c in ("-", "_", " ", ".")
    ).strip()

    cleaned = cleaned.replace(" ", "_")

    if not cleaned:
        cleaned = "unnamed"

    return cleaned


def create_case(case_name: str):
    clean_case = safe_name(case_name)
    case_path = CASES_DIR / clean_case

    (case_path / "pdfs").mkdir(parents=True, exist_ok=True)
    (case_path / "texts").mkdir(parents=True, exist_ok=True)
    (case_path / "results").mkdir(parents=True, exist_ok=True)
    (case_path / "structured").mkdir(parents=True, exist_ok=True)

    return case_path


def list_cases():
    init_storage()

    return sorted(
        [
            p.name
            for p in CASES_DIR.iterdir()
            if p.is_dir()
        ]
    )


def case_dir(case_name: str) -> Path:
    return CASES_DIR / safe_name(case_name)


def pdf_dir(case_name: str) -> Path:
    return case_dir(case_name) / "pdfs"


def text_dir(case_name: str) -> Path:
    return case_dir(case_name) / "texts"


def unique_file_path(folder: Path, filename: str) -> Path:
    """
    Preserve original filename if possible.
    If filename already exists, create filename_2.pdf, filename_3.pdf, etc.
    """
    folder.mkdir(parents=True, exist_ok=True)

    filename = safe_name(filename)

    path = folder / filename

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix

    counter = 2

    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_uploaded_pdf(case_name: str, uploaded_file) -> Path:
    """
    Save uploaded PDF using readable original filename.
    """
    create_case(case_name)

    original_name = safe_name(uploaded_file.name)

    if not original_name.lower().endswith(".pdf"):
        original_name += ".pdf"

    target_path = unique_file_path(
        pdf_dir(case_name),
        original_name,
    )

    content = uploaded_file.getvalue()
    target_path.write_bytes(content)

    return target_path


def list_case_documents(case_name: str):
    folder = pdf_dir(case_name)

    if not folder.exists():
        return []

    return sorted(folder.glob("*.pdf"))


def text_cache_path(pdf_path: Path) -> Path:
    """
    Text file gets same readable base name as PDF.
    Example:
        amended_claims.pdf -> amended_claims.txt
    """
    case_path = pdf_path.parent.parent
    texts_folder = case_path / "texts"
    texts_folder.mkdir(parents=True, exist_ok=True)

    return texts_folder / f"{pdf_path.stem}.txt"


def get_document_text(pdf_path: Path):
    txt_path = text_cache_path(pdf_path)

    if txt_path.exists():
        return txt_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    return None


def structured_dir(case_name: str) -> Path:
    folder = case_dir(case_name) / "structured"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def structured_json_path(case_name: str, pdf_path: Path) -> Path:
    return structured_dir(case_name) / f"{pdf_path.stem}.json"


def save_structured_document(case_name: str, pdf_path: Path, data: dict):
    path = structured_json_path(case_name, pdf_path)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def load_structured_document(case_name: str, pdf_path: Path):
    path = structured_json_path(case_name, pdf_path)

    if path.exists():
        return json.loads(
            path.read_text(encoding="utf-8", errors="ignore")
        )

    return None
