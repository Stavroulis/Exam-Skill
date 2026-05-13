# Document Mapping Pipeline — Design Spec

**Date:** 2026-05-14
**Status:** Approved

---

## Overview

Automatic classification of uploaded PDF documents into their examination roles (`claims_as_filed`, `description`, `amended_claims`, `reply`, `esop`, `D1`, `D2`, …) without any manual UI interaction. Classification runs in two phases: deterministic regex on filenames for application documents, then one LLM call for prior art matching using the ESOP's citation list.

---

## Goals

- Eliminate `guess_document_type()` in favour of explicit, reliable classification
- Allow users to upload files with real-world EPO naming conventions and have them correctly labelled
- Pass clean role names (not raw filenames) to all downstream skills
- Degrade gracefully: cases without a mapping fall back to the existing `guess_document_type()` behaviour

---

## Filename Naming Convention

Application documents follow this pattern:

```
YYYY-MM-DD_<CODE>_<FileNumber>[anything].pdf
```

| Code | Role assigned |
|---|---|
| `_CLMS_` | `claims_as_filed` |
| `_DESC_` | `description` |
| `_ABEX_` | `amended_claims` |
| `_REPL_` | `reply` |
| `_ESOP_` | `esop` |

Matching is performed on the bare filename (no path), case-insensitive on the `.pdf` extension, exact on the code.

Files that do not match any pattern are left **unclassified** for now (future communications or other document types). They are not passed to skills and are not treated as prior art candidates unless the LLM matching step identifies them as such.

If no file maps to `esop`, the pipeline stops after the regex phase and returns only the classified application documents. Tab 1 shows a warning:

> *"No ESOP detected — prior art documents cannot be matched. Upload a file named `YYYY-MM-DD_ESOP_<number>.pdf`."*

---

## Architecture

### New module: `core/document_mapper.py`

| Function | Input | Output |
|---|---|---|
| `classify_filename(filename)` | bare filename string | role string or `None` |
| `parse_esop_prior_art(esop_text)` | raw ESOP text | `list[dict]` of D-label entries |
| `match_prior_art(dlabels, filenames, llm_config)` | D-label list + unclassified filenames | `{filename: "D1", …}` |
| `build_mapping(filenames, esop_text, llm_config)` | all filenames + ESOP text | complete `{filename: role}` dict |
| `save_mapping(case_name, mapping)` | case name + dict | writes `data/cases/{case}/document_mapping.json` |
| `load_mapping(case_name)` | case name | `{filename: role}` dict or `None` |

### Modified: `app.py`

- **Tab 1**: "Build Document Mapping" button below "Save uploaded PDFs". Runs `build_mapping()`, displays result as a read-only table. "Rebuild Mapping" button re-runs at any time.
- **Tab 2**: `auto_prepare_documents()` loads the mapping; uses mapped role as `selected_document_type` and as `filename` in `source_texts`. Falls back to `guess_document_type()` if no mapping exists.

---

## Phase 1: Filename Regex Classification

`classify_filename(filename)` applies these compiled regex patterns in order:

```python
ROLE_PATTERNS = [
    (r"^\d{4}-\d{2}-\d{2}_CLMS_.*\.pdf$",  "claims_as_filed"),
    (r"^\d{4}-\d{2}-\d{2}_DESC_.*\.pdf$",  "description"),
    (r"^\d{4}-\d{2}-\d{2}_ABEX_.*\.pdf$",  "amended_claims"),
    (r"^\d{4}-\d{2}-\d{2}_REPL_.*\.pdf$",  "reply"),
    (r"^\d{4}-\d{2}-\d{2}_ESOP_.*\.pdf$",  "esop"),
]
```

Returns the matched role string, or `None` if no pattern matches.

---

## Phase 2: ESOP Parsing

`parse_esop_prior_art(esop_text)` locates the `PRIOR ART DOCUMENTS` section header in the ESOP text and extracts each D-label entry using:

```python
r"(D\d+)\s+([\w/\s]+?\w+)\s+\(([^)]+)\)[^(]+\((\d{4}-\d{2}-\d{2})\)"
```

Each entry produces a dict:
```python
{
    "label":      "D1",
    "pub_number": "EP 2 490 004 A1",
    "applicant":  "UNIV TOHOKU [JP]; TOYOTA CHUO KENKYUSHO KK [JP] ET AL.",
    "date":       "2012-08-22",
}
```

Returns an empty list if the section is not found. The caller warns the user.

---

## Phase 3: Prior Art LLM Matching

`match_prior_art(dlabels, filenames, llm_config)` makes one LLM call:

**Prompt:**
```
You are matching patent documents to prior art citations from a European Patent
Office Search Opinion.

D-label citations:
D1: EP 2 490 004 A1 — UNIV TOHOKU; TOYOTA CHUO KENKYUSHO — 2012-08-22
D2: US 2017/199090 A1 — ANAN HIROO — 2017-07-13

Uploaded document titles (filenames without .pdf extension):
- Method for real-time sensor calibration in automotive systems
- Apparatus and method for hierarchical anomaly detection

Return valid JSON only:
{"D1": "exact_filename.pdf", "D2": "exact_filename.pdf"}
Omit any D-label you cannot match with confidence.
Do not invent filenames.
```

Returns a dict `{filename: D-label}` (inverted before merging into the main mapping). D-labels with no confident match are omitted — those files remain unclassified.

---

## Mapping Persistence

### File location
`data/cases/{case_name}/document_mapping.json`

### Format
```json
{
  "2026-05-13_CLMS_EP21760408.pdf": "claims_as_filed",
  "2026-05-13_DESC_EP21760408.pdf": "description",
  "2026-05-13_ABEX_EP21760408.pdf": "amended_claims",
  "2026-05-13_REPL_EP21760408.pdf": "reply",
  "2026-05-13_ESOP_EP21760408.pdf": "esop",
  "Method for real-time sensor calibration.pdf": "D1",
  "Apparatus for hierarchical anomaly detection.pdf": "D2"
}
```

`load_mapping()` returns `None` if the file does not exist.

---

## Application in Tab 2

`auto_prepare_documents()` is updated:

1. Call `load_mapping(case_name)` at the start
2. For each document:
   - If mapping exists: `role = mapping.get(doc.name)` → use as `selected_document_type` and as `filename` in `source_texts`
   - If mapping is `None` or `doc.name` not in mapping: fall back to `guess_document_type(doc.name, text)` and use `doc.name` as `filename`
3. All downstream skills receive `source_texts` entries with `filename` set to the role (e.g., `"claims_as_filed"`, `"D1"`) so prompts contain clean, unambiguous document labels

---

## What Is Not Changing

- All 7 individual skill files — no changes
- `complete_examination.py` orchestrator — no changes
- `core/structure.py` `guess_document_type()` — kept as fallback, not removed
- Existing cases without a `document_mapping.json` — continue to work exactly as before
