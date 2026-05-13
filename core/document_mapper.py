# core/document_mapper.py
import json
import re
from pathlib import Path

from core.llm import call_llm


# ── Filename codes (edit here to rename a convention code) ──────────────────
CODE_CLAIMS         = "_CLMS_"
CODE_DESCRIPTION    = "_DESC_"
CODE_AMENDED_CLAIMS = "_ABEX_"
CODE_REPLY          = "_REPL_"
CODE_ESOP           = "_ESOP_"


def _new_pattern(code: str) -> re.Pattern:
    return re.compile(
        rf"^\d{{4}}-\d{{2}}-\d{{2}}{re.escape(code)}.*\.pdf$",
        re.IGNORECASE,
    )


_NEW_CONVENTION_PATTERNS = [
    (_new_pattern(CODE_CLAIMS),         "claims_as_filed"),
    (_new_pattern(CODE_DESCRIPTION),    "description"),
    (_new_pattern(CODE_AMENDED_CLAIMS), "amended_claims"),
    (_new_pattern(CODE_REPLY),          "reply"),
    (_new_pattern(CODE_ESOP),           "esop"),
]

_LEGACY_PATTERNS = [
    (re.compile(r"^claims(_as_filed)?\.pdf$",  re.IGNORECASE), "claims_as_filed"),
    (re.compile(r"^description\.pdf$",          re.IGNORECASE), "description"),
    (re.compile(r"^amended_claims\.pdf$",       re.IGNORECASE), "amended_claims"),
    (re.compile(r"^reply\.pdf$",                re.IGNORECASE), "reply"),
    (re.compile(r"^esop\.pdf$",                 re.IGNORECASE), "esop"),
    (re.compile(r"^(D\d+)\.pdf$",              re.IGNORECASE), None),  # D-label from group 1
]

_ROLE_TO_STRUCTURE_TYPE = {
    "claims_as_filed": "claims_as_filed",
    "description":     "description_as_filed",
    "amended_claims":  "amended_claims",
    "reply":           "attorney_response",
    "esop":            "epo_communication",
}


def classify_filename(filename: str) -> str | None:
    """Return the examination role for a filename, or None if unclassified."""
    name = Path(filename).name

    for pattern, role in _NEW_CONVENTION_PATTERNS:
        if pattern.match(name):
            return role

    for pattern, role in _LEGACY_PATTERNS:
        m = pattern.match(name)
        if m:
            if role is None:
                return m.group(1).upper()
            return role

    return None


def role_to_structure_type(role: str) -> str:
    """Map a document_mapper role to a core/structure.py document type."""
    if re.match(r"^D\d+$", role):
        return "prior_art"
    return _ROLE_TO_STRUCTURE_TYPE.get(role, "unknown")


def parse_esop_prior_art(esop_text: str) -> list[dict]:
    """
    Locate the PRIOR ART DOCUMENTS section and extract D-label entries.
    Returns list of dicts with keys: label, pub_number, applicant, date.
    """
    if not esop_text:
        return []

    section_match = re.search(r"PRIOR ART DOCUMENTS", esop_text, re.IGNORECASE)
    if not section_match:
        return []

    section = esop_text[section_match.end():]

    # Split into per-entry blocks on lines starting with D<digit>
    entries = re.split(r"\n(?=D\d+\s)", section)

    result = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        label_match = re.match(r"^(D\d+)\s", entry)
        if not label_match:
            continue
        label = label_match.group(1)

        # Publication number: text between D-label and first opening parenthesis
        pub_match = re.match(r"D\d+\s+([^(]+?)\s*\(", entry)
        pub_number = re.sub(r"\s+", " ", pub_match.group(1)).strip() if pub_match else ""

        # Applicant: content of first (...) stopped before date digit
        applicant_match = re.search(r"\((.+?)\)\s+\d", entry, re.DOTALL)
        applicant = re.sub(r"\s+", " ", applicant_match.group(1)).strip() if applicant_match else ""

        # Date: always present as (YYYY-MM-DD)
        date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", entry)
        date = date_match.group(1) if date_match else ""

        if label and pub_number:
            result.append({
                "label":      label,
                "pub_number": pub_number,
                "applicant":  applicant,
                "date":       date,
            })

    return result


def match_prior_art(
    dlabels: list[dict],
    filenames: list[str],
    llm_config: dict,
) -> dict[str, str]:
    """
    Call the LLM to match prior art filenames (titles) to D-label citations.
    Returns {filename: D-label} (inverted from LLM output {D-label: filename}).
    """
    if not dlabels or not filenames:
        return {}

    citations_text = "\n".join(
        f"{d['label']}: {d['pub_number']} — {d['applicant']} — {d['date']}"
        for d in dlabels
    )
    titles_text = "\n".join(f"- {f}" for f in filenames)

    prompt = f"""You are matching patent documents to prior art citations from a European Patent Office Search Opinion.

D-label citations:
{citations_text}

Uploaded document titles (filenames without .pdf extension):
{titles_text}

Return valid JSON only:
{{"D1": "exact_filename.pdf", "D2": "exact_filename.pdf"}}
Omit any D-label you cannot match with confidence.
Only use filenames from the list above. Do not invent filenames."""

    try:
        response = call_llm(prompt=prompt, llm_config=llm_config)
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if not json_match:
            return {}
        data = json.loads(json_match.group(0))
        return {
            v: k
            for k, v in data.items()
            if isinstance(k, str) and isinstance(v, str)
        }
    except Exception:
        return {}


def build_mapping(
    filenames: list[str],
    esop_text: str,
    llm_config: dict,
) -> dict[str, str]:
    """
    Build complete {filename: role} mapping.
    Phase 1: regex classify. Phase 2: ESOP parse + LLM match for unclassified files.
    """
    mapping: dict[str, str] = {}
    unclassified: list[str] = []

    for filename in filenames:
        role = classify_filename(filename)
        if role is not None:
            mapping[filename] = role
        else:
            unclassified.append(filename)

    if esop_text and unclassified:
        dlabels = parse_esop_prior_art(esop_text)
        if dlabels:
            prior_art_matches = match_prior_art(dlabels, unclassified, llm_config)
            mapping.update(prior_art_matches)

    return mapping


def save_mapping(case_name: str, mapping: dict) -> Path:
    """Persist mapping to data/cases/{case_name}/document_mapping.json."""
    from core.document_store import case_dir

    path = case_dir(case_name) / "document_mapping.json"
    path.write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_mapping(case_name: str) -> dict | None:
    """Load mapping from disk. Returns None if no mapping exists."""
    from core.document_store import case_dir

    path = case_dir(case_name) / "document_mapping.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
