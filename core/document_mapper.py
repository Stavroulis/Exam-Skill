# core/document_mapper.py
import json
import re
from pathlib import Path


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
