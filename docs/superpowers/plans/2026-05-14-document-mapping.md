# Document Mapping Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically classify uploaded PDFs into their examination roles via filename regex and ESOP-based prior art matching, and apply those roles throughout the skill pipeline.

**Architecture:** A new `core/document_mapper.py` module owns the full classification pipeline (regex → ESOP parse → LLM match → persist). `app.py` Tab 1 gains a "Build Document Mapping" button; Tab 2's `auto_prepare_documents()` loads and applies the mapping instead of calling `guess_document_type()`.

**Tech Stack:** Python 3.10, re, json, pytest, unittest.mock, Streamlit

---

## File Map

| File | Change |
|---|---|
| `core/document_mapper.py` | **New** — full mapping pipeline |
| `tests/test_document_mapper.py` | **New** — all tests for document_mapper |
| `app.py` | **Modify** — Tab 1 mapping button + Tab 2 auto_prepare_documents |

Key facts about existing code needed by the implementer:
- `core/llm.py`: `call_llm(prompt, llm_config=None, provider=None, model=None) -> str` — accepts `llm_config={"provider": "Anthropic / Claude", "model": "claude-sonnet-4-6"}`
- `core/document_store.py`: `case_dir(case_name) -> Path` returns `data/cases/{case_name}/`; `list_case_documents(case_name) -> list[Path]`; `get_document_text(pdf_path: Path) -> str | None`
- `core/structure.py`: `structure_document(filename, text, selected_document_type="auto") -> dict`; `guess_document_type(filename, text) -> str`; valid structure types: `"claims_as_filed"`, `"amended_claims"`, `"description_as_filed"`, `"epo_communication"`, `"attorney_response"`, `"prior_art"`, `"unknown"`
- `core/pdf_extract.py`: `extract_and_cache_pdf_text(pdf_path: Path, force_ocr=False)` — extracts text and caches it

---

## Task 1: `classify_filename()` and `role_to_structure_type()`

**Files:**
- Create: `core/document_mapper.py`
- Create: `tests/test_document_mapper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_document_mapper.py
import pytest
from core.document_mapper import classify_filename, role_to_structure_type


# --- classify_filename: new convention ---

def test_new_convention_clms():
    assert classify_filename("2026-05-13_CLMS_EP21760408.pdf") == "claims_as_filed"

def test_new_convention_desc():
    assert classify_filename("2026-05-13_DESC_EP21760408.pdf") == "description"

def test_new_convention_abex():
    assert classify_filename("2026-05-13_ABEX_EP21760408.pdf") == "amended_claims"

def test_new_convention_repl():
    assert classify_filename("2026-05-13_REPL_EP21760408.pdf") == "reply"

def test_new_convention_esop():
    assert classify_filename("2026-05-13_ESOP_EP21760408.pdf") == "esop"

def test_new_convention_case_insensitive_extension():
    assert classify_filename("2026-05-13_CLMS_EP123.PDF") == "claims_as_filed"

# --- classify_filename: legacy convention ---

def test_legacy_claims():
    assert classify_filename("claims.pdf") == "claims_as_filed"

def test_legacy_claims_as_filed():
    assert classify_filename("claims_as_filed.pdf") == "claims_as_filed"

def test_legacy_description():
    assert classify_filename("description.pdf") == "description"

def test_legacy_amended_claims():
    assert classify_filename("amended_claims.pdf") == "amended_claims"

def test_legacy_reply():
    assert classify_filename("reply.pdf") == "reply"

def test_legacy_esop():
    assert classify_filename("esop.pdf") == "esop"

def test_legacy_d1():
    assert classify_filename("D1.pdf") == "D1"

def test_legacy_d2():
    assert classify_filename("D2.pdf") == "D2"

def test_legacy_d10():
    assert classify_filename("D10.pdf") == "D10"

# --- classify_filename: unclassified ---

def test_unclassified_title_name():
    assert classify_filename("Method for real-time sensor calibration.pdf") is None

def test_unclassified_generic():
    assert classify_filename("some_other_file.pdf") is None


# --- role_to_structure_type ---

def test_role_claims_as_filed():
    assert role_to_structure_type("claims_as_filed") == "claims_as_filed"

def test_role_description():
    assert role_to_structure_type("description") == "description_as_filed"

def test_role_amended_claims():
    assert role_to_structure_type("amended_claims") == "amended_claims"

def test_role_reply():
    assert role_to_structure_type("reply") == "attorney_response"

def test_role_esop():
    assert role_to_structure_type("esop") == "epo_communication"

def test_role_d1():
    assert role_to_structure_type("D1") == "prior_art"

def test_role_d2():
    assert role_to_structure_type("D2") == "prior_art"

def test_role_unknown():
    assert role_to_structure_type("something_else") == "unknown"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_document_mapper.py -v`
Expected: `ImportError` — `core/document_mapper.py` does not exist yet

- [ ] **Step 3: Create `core/document_mapper.py` with `classify_filename` and `role_to_structure_type`**

```python
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
                # D-label: extract from capture group 1
                return m.group(1).upper()
            return role

    return None


def role_to_structure_type(role: str) -> str:
    """Map a document_mapper role to a core/structure.py document type."""
    if re.match(r"^D\d+$", role):
        return "prior_art"
    return _ROLE_TO_STRUCTURE_TYPE.get(role, "unknown")
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_document_mapper.py -v`
Expected: `25 passed`

- [ ] **Step 5: Commit**

```bash
git add core/document_mapper.py tests/test_document_mapper.py
git commit -m "feat: add classify_filename and role_to_structure_type"
```

---

## Task 2: `parse_esop_prior_art()`

**Files:**
- Modify: `core/document_mapper.py`
- Modify: `tests/test_document_mapper.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_document_mapper.py`:

```python
from core.document_mapper import parse_esop_prior_art

ESOP_SAMPLE = """
Some introductory text.

PRIOR ART DOCUMENTS

D1 EP 2 490 004 A1 (UNIV TOHOKU [JP]; TOYOTA CHUO
KENKYUSHO KK [JP] ET AL.) 22 August 2012 (2012-08-22)
D2 US 2017/199090 A1 (ANAN HIROO [JP] ET AL) 13 July 2017

(2017-07-13)

D3 WO 02/44655 A1 (NANODEVICES INC [US]) 6 June 2002

(2002-06-06)

Some text after the citations.
"""

def test_parse_esop_returns_three_entries():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert len(result) == 3

def test_parse_esop_labels():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert result[0]["label"] == "D1"
    assert result[1]["label"] == "D2"
    assert result[2]["label"] == "D3"

def test_parse_esop_pub_numbers():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert "EP" in result[0]["pub_number"]
    assert "US" in result[1]["pub_number"]
    assert "WO" in result[2]["pub_number"]

def test_parse_esop_dates():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert result[0]["date"] == "2012-08-22"
    assert result[1]["date"] == "2017-07-13"
    assert result[2]["date"] == "2002-06-06"

def test_parse_esop_applicant_d1():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert "TOHOKU" in result[0]["applicant"]

def test_parse_esop_no_section_returns_empty():
    result = parse_esop_prior_art("This document has no prior art section.")
    assert result == []

def test_parse_esop_empty_string():
    assert parse_esop_prior_art("") == []
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_document_mapper.py::test_parse_esop_returns_three_entries -v`
Expected: `ImportError` — `parse_esop_prior_art` not defined yet

- [ ] **Step 3: Add `parse_esop_prior_art` to `core/document_mapper.py`**

Add after the `role_to_structure_type` function:

```python
def parse_esop_prior_art(esop_text: str) -> list[dict]:
    """
    Locate the PRIOR ART DOCUMENTS section and extract D-label entries.
    Returns a list of dicts with keys: label, pub_number, applicant, date.
    """
    if not esop_text:
        return []

    section_match = re.search(r"PRIOR ART DOCUMENTS", esop_text, re.IGNORECASE)
    if not section_match:
        return []

    section = esop_text[section_match.end():]

    # Split into per-entry blocks on lines that start with D<digit>
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

        # Applicant: content of first (...) group, lazy-stopped before a digit (date text)
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
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_document_mapper.py -v`
Expected: all tests pass (32 total)

- [ ] **Step 5: Commit**

```bash
git add core/document_mapper.py tests/test_document_mapper.py
git commit -m "feat: add parse_esop_prior_art"
```

---

## Task 3: `match_prior_art()`, `build_mapping()`, `save_mapping()`, `load_mapping()`

**Files:**
- Modify: `core/document_mapper.py`
- Modify: `tests/test_document_mapper.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_document_mapper.py`:

```python
import json
import pytest
from unittest.mock import patch
from core.document_mapper import match_prior_art, build_mapping, save_mapping, load_mapping

_DLABELS = [
    {"label": "D1", "pub_number": "EP 2 490 004 A1", "applicant": "UNIV TOHOKU", "date": "2012-08-22"},
    {"label": "D2", "pub_number": "US 2017/199090 A1", "applicant": "ANAN HIROO", "date": "2017-07-13"},
]

_LLM_CONFIG = {"provider": "Anthropic / Claude", "model": "claude-sonnet-4-6"}


# --- match_prior_art ---

def test_match_prior_art_returns_inverted_mapping():
    llm_json = '{"D1": "Method for sensor calibration.pdf", "D2": "Anomaly detection apparatus.pdf"}'
    with patch("core.document_mapper.call_llm", return_value=llm_json):
        result = match_prior_art(_DLABELS, ["Method for sensor calibration.pdf", "Anomaly detection apparatus.pdf"], _LLM_CONFIG)
    assert result == {
        "Method for sensor calibration.pdf": "D1",
        "Anomaly detection apparatus.pdf": "D2",
    }

def test_match_prior_art_empty_inputs():
    assert match_prior_art([], [], _LLM_CONFIG) == {}
    assert match_prior_art(_DLABELS, [], _LLM_CONFIG) == {}
    assert match_prior_art([], ["file.pdf"], _LLM_CONFIG) == {}

def test_match_prior_art_invalid_json_returns_empty():
    with patch("core.document_mapper.call_llm", return_value="not json at all"):
        result = match_prior_art(_DLABELS, ["file.pdf"], _LLM_CONFIG)
    assert result == {}

def test_match_prior_art_partial_match():
    llm_json = '{"D1": "Method for sensor calibration.pdf"}'
    with patch("core.document_mapper.call_llm", return_value=llm_json):
        result = match_prior_art(_DLABELS, ["Method for sensor calibration.pdf", "Unknown doc.pdf"], _LLM_CONFIG)
    assert "Method for sensor calibration.pdf" in result
    assert "Unknown doc.pdf" not in result


# --- build_mapping ---

def test_build_mapping_new_convention():
    filenames = ["2026-05-13_CLMS_EP123.pdf", "2026-05-13_ESOP_EP123.pdf"]
    result = build_mapping(filenames, esop_text="", llm_config=_LLM_CONFIG)
    assert result["2026-05-13_CLMS_EP123.pdf"] == "claims_as_filed"
    assert result["2026-05-13_ESOP_EP123.pdf"] == "esop"

def test_build_mapping_legacy_convention():
    filenames = ["claims.pdf", "D1.pdf", "D2.pdf"]
    result = build_mapping(filenames, esop_text="", llm_config=_LLM_CONFIG)
    assert result["claims.pdf"] == "claims_as_filed"
    assert result["D1.pdf"] == "D1"
    assert result["D2.pdf"] == "D2"

def test_build_mapping_no_esop_skips_llm_for_unclassified():
    filenames = ["2026-05-13_CLMS_EP123.pdf", "Prior art title.pdf"]
    result = build_mapping(filenames, esop_text="", llm_config=_LLM_CONFIG)
    assert "Prior art title.pdf" not in result
    assert result["2026-05-13_CLMS_EP123.pdf"] == "claims_as_filed"

def test_build_mapping_calls_llm_for_prior_art(tmp_path):
    filenames = ["2026-05-13_CLMS_EP123.pdf", "2026-05-13_ESOP_EP123.pdf", "Prior art title.pdf"]
    esop_text = """PRIOR ART DOCUMENTS

D1 EP 2 490 004 A1 (UNIV TOHOKU [JP]) 22 August 2012 (2012-08-22)
"""
    llm_json = '{"D1": "Prior art title.pdf"}'
    with patch("core.document_mapper.call_llm", return_value=llm_json):
        result = build_mapping(filenames, esop_text=esop_text, llm_config=_LLM_CONFIG)
    assert result["Prior art title.pdf"] == "D1"
    assert result["2026-05-13_CLMS_EP123.pdf"] == "claims_as_filed"


# --- save_mapping / load_mapping ---

def test_save_and_load_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "cases" / "TestCase").mkdir(parents=True)
    mapping = {"claims.pdf": "claims_as_filed", "D1.pdf": "D1"}
    save_mapping("TestCase", mapping)
    loaded = load_mapping("TestCase")
    assert loaded == mapping

def test_load_mapping_returns_none_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "cases").mkdir(parents=True)
    assert load_mapping("NonExistentCase") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_document_mapper.py::test_match_prior_art_returns_inverted_mapping -v`
Expected: `ImportError` — functions not defined yet

- [ ] **Step 3: Add the four functions to `core/document_mapper.py`**

Add after `parse_esop_prior_art`:

```python
def match_prior_art(
    dlabels: list[dict],
    filenames: list[str],
    llm_config: dict,
) -> dict[str, str]:
    """
    Call the LLM to match prior art filenames (titles) to D-label citations.
    Returns {filename: D-label} (inverted from LLM output).
    """
    from core.llm import call_llm

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
        # Invert: {D-label: filename} → {filename: D-label}
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
    Build the complete {filename: role} mapping for all uploaded documents.
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
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_document_mapper.py -v`
Expected: all 42 tests pass

- [ ] **Step 5: Run full test suite to verify nothing broken**

Run: `pytest tests/ -q`
Expected: all 80 tests pass (38 existing + 42 new)

- [ ] **Step 6: Commit**

```bash
git add core/document_mapper.py tests/test_document_mapper.py
git commit -m "feat: add match_prior_art, build_mapping, save_mapping, load_mapping"
```

---

## Task 4: Update `auto_prepare_documents()` in `app.py`

**Files:**
- Modify: `app.py` (lines 10–24 imports section, lines 230–306 `auto_prepare_documents` function)

The function currently calls `guess_document_type()` and uses `doc.name` as the filename. With the mapping it should use the mapped role instead.

- [ ] **Step 1: Add import to `app.py`**

Find this block at the top of `app.py` (around line 10):
```python
from core.structure import guess_document_type, structure_document
```

Replace with:
```python
from core.structure import guess_document_type, structure_document
from core.document_mapper import (
    classify_filename,
    build_mapping,
    save_mapping,
    load_mapping,
    role_to_structure_type,
)
```

- [ ] **Step 2: Update `auto_prepare_documents()`**

Find the function `auto_prepare_documents` (starts around line 230). Replace the entire function body with:

```python
def auto_prepare_documents(
    case_name: str,
    docs,
    force_reprocess: bool = False,
    force_ocr: bool = False,
):
    """
    Prepare documents for all skills.

    Steps:
    1. Load document mapping if available.
    2. Reuse cached extracted text if available.
    3. Extract/OCR PDF text if needed.
    4. Reuse structured JSON if available.
    5. Structure the document using mapped role (or guess_document_type fallback).
    6. Return both raw text blocks and structured document blocks.
    """
    mapping = load_mapping(case_name)

    source_texts = []
    structured_docs = []

    progress = st.progress(0)
    status = st.empty()

    total_steps = max(len(docs) * 2, 1)
    step = 0

    for doc in docs:
        status.write(f"Extracting text from `{doc.name}`...")

        text = get_document_text(doc)

        if force_reprocess or not text:
            extract_and_cache_pdf_text(
                doc,
                force_ocr=force_ocr,
            )
            text = get_document_text(doc)

        # Determine display name and structure type from mapping or fallback
        if mapping and doc.name in mapping:
            role = mapping[doc.name]
            display_name = role
            structure_type = role_to_structure_type(role)
        else:
            display_name = doc.name
            structure_type = guess_document_type(doc.name, text or "")

        source_texts.append(
            {
                "filename": display_name,
                "text": text or "",
            }
        )

        step += 1
        progress.progress(step / total_steps)

        status.write(f"Structuring `{doc.name}`...")

        structured = None

        if not force_reprocess:
            structured = load_structured_document(case_name, doc)

        if not structured:
            structured = structure_document(
                filename=display_name,
                text=text or "",
                selected_document_type=structure_type,
            )

            save_structured_document(
                case_name,
                doc,
                structured,
            )

        structured_docs.append(structured)

        step += 1
        progress.progress(step / total_steps)

    status.write("Document preparation complete.")

    return source_texts, structured_docs
```

- [ ] **Step 3: Start the app and verify it still loads**

Run: `streamlit run app.py`
Expected: app loads without errors, Tab 2 "Run Full Analysis" still works for existing cases (mapping is None → falls back to guess_document_type)

Stop the app with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: apply document mapping in auto_prepare_documents"
```

---

## Task 5: Add "Build Document Mapping" button to Tab 1

**Files:**
- Modify: `app.py` (Tab 1 section, around lines 771–803)

- [ ] **Step 1: Add mapping UI to Tab 1**

Find the Tab 1 section in `app.py`. It starts with `with tabs[0]:` (around line 771) and ends before `with tabs[1]:`. After the existing `with st.expander("Advanced: storage information"):` block, add the following (as the last thing inside `with tabs[0]:`):

```python
    # ── Document Mapping ────────────────────────────────────────────────────

    st.divider()
    st.subheader("Document Mapping")

    existing_mapping = load_mapping(selected_case)

    if existing_mapping:
        st.success(f"Mapping active — {len(existing_mapping)} document(s) classified.")
        st.dataframe(
            pd.DataFrame(
                [{"File": k, "Role": v} for k, v in existing_mapping.items()]
            ),
            use_container_width=True,
        )

    build_label = "Rebuild Mapping" if existing_mapping else "Build Document Mapping"

    if st.button(build_label):
        all_docs = list_case_documents(selected_case)

        if not all_docs:
            st.warning("No documents uploaded yet.")
        else:
            all_filenames = [doc.name for doc in all_docs]

            # Find ESOP and ensure its text is extracted
            esop_text = ""
            esop_found = False

            for doc in all_docs:
                if classify_filename(doc.name) == "esop":
                    esop_found = True
                    text = get_document_text(doc)
                    if not text:
                        with st.spinner(f"Extracting ESOP text from `{doc.name}`..."):
                            extract_and_cache_pdf_text(doc)
                        text = get_document_text(doc)
                    esop_text = text or ""
                    break

            if not esop_found:
                st.warning(
                    "No ESOP detected — prior art documents cannot be matched automatically. "
                    "Upload a file named `YYYY-MM-DD_ESOP_<number>.pdf` or `esop.pdf`."
                )

            with st.spinner("Building document mapping..."):
                mapping = build_mapping(all_filenames, esop_text, llm_config)

            save_mapping(selected_case, mapping)

            st.success(f"Mapping built — {len(mapping)} document(s) classified.")

            st.dataframe(
                pd.DataFrame(
                    [{"File": k, "Role": v} for k, v in mapping.items()]
                ),
                use_container_width=True,
            )

            unclassified = [f for f in all_filenames if f not in mapping]
            if unclassified:
                st.info(
                    f"{len(unclassified)} file(s) could not be classified and will be ignored: "
                    + ", ".join(f"`{f}`" for f in unclassified)
                )

            st.rerun()
```

- [ ] **Step 2: Start the app and test the mapping button**

Run: `streamlit run app.py`

Test sequence:
1. Select an existing case (e.g. `EP11111` which has `claims.pdf`, `D1.pdf`, `D2.pdf`)
2. Go to Tab 1
3. Click "Build Document Mapping"
4. Verify the mapping table shows `claims.pdf → claims_as_filed`, `D1.pdf → D1`, `D2.pdf → D2`
5. Go to Tab 2, run any skill — verify it runs without errors

Stop the app.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -q`
Expected: all 80 tests pass

- [ ] **Step 4: Commit and push**

```bash
git add app.py
git commit -m "feat: add Build Document Mapping button to Tab 1"
git push origin main
```
