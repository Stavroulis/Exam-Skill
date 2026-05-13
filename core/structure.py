import re
from pathlib import Path
from typing import Dict, List, Any


DOCUMENT_TYPES = [
    "description_as_filed",
    "claims_as_filed",
    "amended_claims",
    "epo_communication",
    "attorney_response",
    "prior_art",
    "unknown",
]


def guess_document_type(filename: str, text: str) -> str:
    """
    Simple heuristic document classifier.
    User-selected tags should override this.
    """
    name = filename.lower()
    sample = text[:5000].lower()

    if "amended" in name and "claim" in name:
        return "amended_claims"

    if "claim" in name:
        return "claims_as_filed"

    if "description" in name or "beschrijving" in name:
        return "description_as_filed"

    if "communication" in name or "epo" in name or "94(3)" in sample:
        return "epo_communication"

    if "response" in name or "reply" in name or "attorney" in name:
        return "attorney_response"

    if "patent" in sample and "claims" in sample and "description" in sample:
        return "prior_art"

    return "unknown"


def clean_pdf_text(text: str) -> str:
    """
    Light cleanup only. Avoid aggressive cleaning because patent wording matters.
    """
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_claims(text: str) -> List[Dict[str, Any]]:
    """
    Extract claims using common claim numbering patterns.

    Supports:
    1. ...
    Claim 1. ...
    CLAIMS
    1 A device...
    """
    text = clean_pdf_text(text)

    # Remove page markers but keep content.
    text = re.sub(r"--- PAGE \d+ ---", "", text, flags=re.IGNORECASE)
    text = re.sub(r"--- OCR PAGE \d+ ---", "", text, flags=re.IGNORECASE)

    # Try to start after "Claims" heading if present.
    match = re.search(r"\bclaims\b", text, flags=re.IGNORECASE)
    if match:
        candidate = text[match.end():]
    else:
        candidate = text

    pattern = re.compile(
        r"(?m)(?:^|\n)\s*(?:Claim\s*)?(\d{1,3})[\.\)]\s+"
    )

    matches = list(pattern.finditer(candidate))
    claims = []

    if not matches:
        return claims

    for i, m in enumerate(matches):
        claim_no = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(candidate)

        claim_text = candidate[start:end].strip()

        if len(claim_text) < 20:
            continue

        claims.append(
            {
                "claim_number": claim_no,
                "text": claim_text,
                "word_count": len(claim_text.split()),
                "is_independent_guess": is_independent_claim_guess(claim_text),
            }
        )

    return claims


def is_independent_claim_guess(claim_text: str) -> bool:
    lower = claim_text.lower()

    dependency_markers = [
        "according to claim",
        "according to any preceding claim",
        "according to any one of the preceding claims",
        "as claimed in claim",
        "claim according to claim",
        "of claim",
    ]

    return not any(marker in lower for marker in dependency_markers)


def parse_description_sections(text: str) -> List[Dict[str, Any]]:
    """
    Extract likely description sections from patent text.
    This is heuristic and intentionally conservative.
    """
    text = clean_pdf_text(text)

    section_patterns = [
        "field of the invention",
        "technical field",
        "background",
        "background art",
        "summary",
        "summary of the invention",
        "brief description of the drawings",
        "detailed description",
        "description of embodiments",
        "embodiments",
        "examples",
        "industrial applicability",
    ]

    combined = "|".join(re.escape(p) for p in section_patterns)

    pattern = re.compile(
        rf"(?im)^\s*({combined})\s*$"
    )

    matches = list(pattern.finditer(text))
    sections = []

    if not matches:
        sections.append(
            {
                "section_title": "full_description",
                "text": text,
                "word_count": len(text.split()),
            }
        )
        return sections

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        section_text = text[start:end].strip()

        sections.append(
            {
                "section_title": title,
                "text": section_text,
                "word_count": len(section_text.split()),
            }
        )

    return sections


def extract_basis_candidates(text: str) -> List[Dict[str, Any]]:
    """
    Find passages that are often useful for Art. 123(2) EPC basis analysis.
    """
    text = clean_pdf_text(text)

    keywords = [
        "in one embodiment",
        "in an embodiment",
        "preferably",
        "more preferably",
        "optionally",
        "may comprise",
        "comprises",
        "configured to",
        "adapted to",
        "wherein",
        "advantage",
        "effect",
        "problem",
        "solution",
    ]

    paragraphs = re.split(r"\n\s*\n", text)
    candidates = []

    for idx, para in enumerate(paragraphs):
        lower = para.lower()

        if any(k in lower for k in keywords):
            candidates.append(
                {
                    "paragraph_index": idx,
                    "text": para.strip(),
                    "word_count": len(para.split()),
                }
            )

    return candidates[:80]


def structure_document(
    filename: str,
    text: str,
    selected_document_type: str = "auto",
) -> Dict[str, Any]:
    """
    Main structuring function.
    """
    text = clean_pdf_text(text)

    if selected_document_type == "auto":
        doc_type = guess_document_type(filename, text)
    else:
        doc_type = selected_document_type

    structured = {
        "filename": filename,
        "document_type": doc_type,
        "text_character_count": len(text),
        "text_word_count": len(text.split()),
        "claims": [],
        "description_sections": [],
        "basis_candidates": [],
    }

    if doc_type in ["claims_as_filed", "amended_claims", "prior_art"]:
        structured["claims"] = parse_claims(text)

    if doc_type in ["description_as_filed", "prior_art", "unknown"]:
        structured["description_sections"] = parse_description_sections(text)
        structured["basis_candidates"] = extract_basis_candidates(text)

    if doc_type in ["epo_communication", "attorney_response"]:
        structured["basis_candidates"] = extract_basis_candidates(text)

    return structured


def build_structured_context(structured_docs: List[Dict[str, Any]]) -> str:
    """
    Build a compact LLM-ready context from structured documents.
    """
    parts = []

    for doc in structured_docs:
        parts.append(
            f"\n\n===== STRUCTURED DOCUMENT: {doc['filename']} =====\n"
            f"Document type: {doc['document_type']}\n"
            f"Word count: {doc.get('text_word_count', 0)}\n"
        )

        if doc.get("claims"):
            parts.append("\n--- CLAIMS ---\n")
            for claim in doc["claims"]:
                independent = (
                    "independent guess"
                    if claim.get("is_independent_guess")
                    else "dependent guess"
                )
                parts.append(
                    f"\nClaim {claim['claim_number']} ({independent}):\n"
                    f"{claim['text']}\n"
                )

        if doc.get("description_sections"):
            parts.append("\n--- DESCRIPTION SECTIONS ---\n")
            for section in doc["description_sections"]:
                section_text = section["text"]

                # Avoid sending huge sections blindly.
                section_text = section_text[:12000]

                parts.append(
                    f"\n[{section['section_title']}]\n"
                    f"{section_text}\n"
                )

        if doc.get("basis_candidates"):
            parts.append("\n--- BASIS CANDIDATE PASSAGES ---\n")
            for cand in doc["basis_candidates"][:40]:
                parts.append(
                    f"\nParagraph candidate {cand['paragraph_index']}:\n"
                    f"{cand['text'][:2000]}\n"
                )

    return "\n".join(parts)