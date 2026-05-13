# Complete Examination Skill — Design Spec

**Date:** 2026-05-13
**Status:** Approved

---

## Overview

A new `complete_examination` skill that orchestrates all 7 existing EPO examination skills in a fixed sequence. Each skill runs as a separate LLM call (preserving quality), produces a short summary for display and inter-skill context, and contributes its full output to a combined final report.

---

## Goals

- Run all 7 skills in one user action instead of manually triggering each
- Show the user a concise summary after each skill (not the full output)
- Pass accumulated summaries as context to each subsequent skill to reduce input tokens on downstream calls
- Produce a single combined report (all full outputs) as the final result
- Keep each skill's prompt independently editable without touching the orchestrator

---

## Execution Order

Skills run in this fixed sequence:

| # | Skill key | File | Purpose |
|---|---|---|---|
| 1 | `basic_analysis` | `skills/basic_analysis.py` | Invention problem, technical effect, solution |
| 2 | `analyse_ind_claims` | `skills/analyse_ind_claims.py` | Claim categories, Rule 43(2) EPC, CII |
| 3 | `technical_features` | `skills/technical_features.py` | Atomic feature extraction from claims |
| 4 | `prior_art_analysis` | `skills/prior_art_analysis.py` | Prior-art document summaries |
| 5 | `novelty_inventive_step` | `skills/novelty_inventive_step.py` | Feature mapping, Art. 54/56 EPC |
| 6 | `epo_123_2` | `skills/epo_123_2.py` | Basis for amendments, Art. 123(2) EPC |
| 7 | `votum` | `skills/votum.py` | Final EPO examination report |

---

## Summary Mechanism

### Marker format

Every skill's prompt gains an appended summary block using this exact marker pair:

```
===BEGIN_SKILL_SUMMARY===
- [key finding 1]
- [key finding 2]
- [key finding 3]
- [key finding 4 if relevant]
- [key finding 5 if relevant]
===END_SKILL_SUMMARY===
```

The LLM is instructed to produce 3–5 bullet points covering the key findings of that skill only.

### Extraction

The orchestrator extracts the summary via regex (same pattern as the existing `===BEGIN_4P_SUMMARY===` in `basic_analysis`). Everything before the markers is the full output. Everything inside the markers is the summary.

### Backward compatibility

`basic_analysis` keeps its existing `===BEGIN_4P_SUMMARY===` block. The new `===BEGIN_SKILL_SUMMARY===` block is appended alongside it. No existing behaviour changes.

---

## Inter-Skill Context

After each skill completes, its summary is appended to a `prior_analysis_context` string:

```
=== PRIOR ANALYSIS CONTEXT ===

[Skill 1 — Basic Analysis]
- finding 1
- finding 2
...

[Skill 2 — Analyse Independent Claims]
- finding 1
...
```

This block is prepended to the next skill's prompt. Skills receive it via a new optional `prior_context=""` parameter added to each `build_prompt()` function. When skills are run standalone (individually), `prior_context` defaults to `""` and nothing changes.

---

## Return Shape

### Individual skills (updated)

All 7 skills updated to return consistently:

```python
{"result": full_output_string, "summary": summary_string}
```

`basic_analysis` already returns this shape — the other 6 are updated to match.

### Complete examination skill

```python
{
    "result": combined_report,   # all 7 full outputs concatenated with section headers
    "summary": "Complete examination finished — 7 skills executed."
}
```

---

## Orchestrator (`skills/complete_examination.py`)

```
run(case_name, source_documents, structured_documents, user_input, llm_config):
    prior_context = ""
    combined_report = ""

    for each skill in ORDER:
        output = skill.run(..., prior_context=prior_context)
        combined_report += section_header + output["result"]
        prior_context += format_context_block(skill.name, output["summary"])

    return {"result": combined_report, "summary": "Complete examination finished — 7 skills executed."}
```

---

## Registry

`skills/registry.py` gains one new entry:

```python
from skills.complete_examination import COMPLETE_EXAMINATION_SKILL

SKILLS = {
    ...existing entries...,
    "complete_examination": COMPLETE_EXAMINATION_SKILL,
}
```

The complete examination skill appears alongside individual skills in the existing UI — no UI changes required.

---

## Files Changed

| File | Change |
|---|---|
| `skills/basic_analysis.py` | Add `prior_context=""` param to `build_prompt()`; add `===BEGIN_SKILL_SUMMARY===` block to prompt |
| `skills/analyse_ind_claims.py` | Same as above; update `run()` to return `{"result", "summary"}` |
| `skills/technical_features.py` | Same |
| `skills/prior_art_analysis.py` | Same |
| `skills/novelty_inventive_step.py` | Same |
| `skills/epo_123_2.py` | Same |
| `skills/votum.py` | Same |
| `skills/complete_examination.py` | **New** — orchestrator |
| `skills/registry.py` | Add `complete_examination` entry |

---

## What Is Not Changing

- Existing skill prompts (content) — only the summary block and `prior_context` param are added
- UI — no changes; the new skill appears automatically via the registry
- Individual skill behaviour when run standalone — `prior_context` defaults to `""`, summary markers are stripped before returning
