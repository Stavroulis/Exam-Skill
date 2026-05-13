# Complete Examination Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `complete_examination` skill that runs all 7 EPO examination skills sequentially, shows a short summary per skill, chains summaries as context to downstream skills, and returns a combined full report.

**Architecture:** A shared `core/skill_utils.py` provides summary-marker constants and extraction logic used by all 7 skills. Each skill gains a `prior_context=""` parameter that prepends accumulated prior findings to its prompt. A new `skills/complete_examination.py` orchestrator calls skills in fixed order and accumulates results.

**Tech Stack:** Python 3.10, pytest, unittest.mock

---

## Task 1: Test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/skills/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create test directories and conftest**

```python
# tests/__init__.py  — empty

# tests/skills/__init__.py  — empty

# tests/conftest.py
import pytest

MOCK_LLM_RESPONSE_WITH_SUMMARY = """Some analysis content here.

===BEGIN_SKILL_SUMMARY===
- Key finding one
- Key finding two
- Key finding three
===END_SKILL_SUMMARY==="""

MOCK_LLM_RESPONSE_NO_SUMMARY = "Some analysis content with no summary markers."

MINIMAL_SOURCE_DOCS = [{"filename": "claims.txt", "text": "Claim 1: A device comprising a sensor."}]

BASE_LLM_CONFIG = {"provider": "anthropic", "model": "claude-sonnet-4-6"}
```

- [ ] **Step 2: Verify pytest is available**

Run: `pytest --version`
Expected: `pytest 7.x.x` or similar (any version)

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "feat: add test infrastructure"
```

---

## Task 2: Create `core/skill_utils.py`

**Files:**
- Create: `core/skill_utils.py`
- Create: `tests/test_skill_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_skill_utils.py
from core.skill_utils import extract_skill_summary, format_prior_context_block, SUMMARY_INSTRUCTION, _SUMMARY_BEGIN, _SUMMARY_END


def test_extract_summary_with_markers():
    raw = f"Full analysis text.\n\n{_SUMMARY_BEGIN}\n- Finding 1\n- Finding 2\n{_SUMMARY_END}"
    out = extract_skill_summary(raw)
    assert out["result"] == "Full analysis text."
    assert out["summary"] == "- Finding 1\n- Finding 2"


def test_extract_summary_no_markers():
    raw = "Full analysis text with no markers."
    out = extract_skill_summary(raw)
    assert out["result"] == "Full analysis text with no markers."
    assert out["summary"] == ""


def test_extract_summary_strips_whitespace():
    raw = f"Content.\n\n{_SUMMARY_BEGIN}\n\n  - Bullet  \n\n{_SUMMARY_END}\n"
    out = extract_skill_summary(raw)
    assert out["summary"] == "- Bullet"


def test_format_prior_context_block_with_context():
    block = format_prior_context_block("- finding 1\n- finding 2")
    assert "PRIOR ANALYSIS CONTEXT" in block
    assert "finding 1" in block


def test_format_prior_context_block_empty():
    assert format_prior_context_block("") == ""
    assert format_prior_context_block(None) == ""


def test_summary_instruction_contains_markers():
    assert _SUMMARY_BEGIN in SUMMARY_INSTRUCTION
    assert _SUMMARY_END in SUMMARY_INSTRUCTION
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_skill_utils.py -v`
Expected: `ImportError` or `ModuleNotFoundError` — `core/skill_utils.py` does not exist yet

- [ ] **Step 3: Implement `core/skill_utils.py`**

```python
# core/skill_utils.py
import re

_SUMMARY_BEGIN = "===BEGIN_SKILL_SUMMARY==="
_SUMMARY_END = "===END_SKILL_SUMMARY==="

SUMMARY_INSTRUCTION = f"""
After completing the above analysis, output a short summary wrapped exactly between these markers (include the marker lines verbatim):

{_SUMMARY_BEGIN}
[3-5 bullet points summarising the key findings of this analysis]
{_SUMMARY_END}
"""


def extract_skill_summary(raw: str) -> dict:
    match = re.search(
        rf"{re.escape(_SUMMARY_BEGIN)}(.*?){re.escape(_SUMMARY_END)}",
        raw,
        re.DOTALL,
    )
    if match:
        return {
            "result": raw[: match.start()].strip(),
            "summary": match.group(1).strip(),
        }
    return {"result": raw.strip(), "summary": ""}


def format_prior_context_block(prior_context: str) -> str:
    if not prior_context:
        return ""
    return f"\n\nPRIOR ANALYSIS CONTEXT (from previous examination steps):\n{prior_context}\n"
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_skill_utils.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add core/skill_utils.py tests/test_skill_utils.py
git commit -m "feat: add shared skill_utils for summary extraction"
```

---

## Task 3: Update `skills/basic_analysis.py`

**Files:**
- Modify: `skills/basic_analysis.py`
- Create: `tests/skills/test_basic_analysis.py`

`basic_analysis` already extracts a 4-paragraph summary and returns `{"result", "summary"}`. Changes: add `prior_context=""` to `build_prompt()` and `run()`, inject context block into prompt, append `SUMMARY_INSTRUCTION` to prompt, extract the new skill summary alongside the existing 4p summary.

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_basic_analysis.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.basic_analysis import build_prompt, run

MOCK_RESPONSE = f"""# Basic Technical Analysis

Some analysis.

===BEGIN_4P_SUMMARY===
Para 1. Para 2. Para 3. Para 4.
===END_4P_SUMMARY===

{_SUMMARY_BEGIN}
- Invention addresses sensor calibration
- Effect: reduced noise
- No prior art mentioned
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
        prior_context="- Previous finding",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Previous finding" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_skill_summary():
    with patch("skills.basic_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "desc.txt", "text": "A device."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert "Invention addresses sensor calibration" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]


def test_run_returns_dict():
    with patch("skills.basic_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "desc.txt", "text": "A device."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "result" in out
    assert "summary" in out
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_basic_analysis.py -v`
Expected: failures on `prior_context` param and `_SUMMARY_BEGIN` not in prompt

- [ ] **Step 3: Update `skills/basic_analysis.py`**

Replace the existing `build_prompt` signature and body as follows (keep all existing prompt content, add two insertions):

```python
# skills/basic_analysis.py
import re

from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block

_SUMMARY_BEGIN = "===BEGIN_4P_SUMMARY==="
_SUMMARY_END = "===END_4P_SUMMARY==="


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:40000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
Your task is to perform a basic technical analysis of the patent application description.

Focus on:
1. The underlying technical problem
2. The technical effect on which the solution is based
3. Advantages disclosed in the description
4. Prior art mentioned in the description
5. Differences over the mentioned prior art, if explicitly or implicitly disclosed

Important rules:
- Base the analysis only on the provided documents.
- Do not invent a technical problem.
- Distinguish clearly between:
  - explicitly stated problem
  - inferred problem
  - technical effect
  - advantage
  - prior-art drawback
  - difference over prior art
- If no prior art is mentioned, state this clearly.
- If a difference over prior art is not clearly derivable, state this clearly.
- Use exact wording from the description where useful, but do not overquote.
- Be concise but precise.

CASE:
{case_name}

SOURCE MATERIAL:
{docs_block}

Prepare the output in the following structure:

# Basic Technical Analysis

## 1. Documents considered

List the documents used and their classified document type.

## 2. Underlying technical problem

### 2.1 Explicitly stated problem

State the problem if expressly disclosed.

### 2.2 Inferred technical problem

If no explicit problem is stated, infer the likely technical problem from the description, but clearly label it as inferred.

## 3. Technical effect

Identify the technical effect produced by the disclosed solution.

Explain which features appear to contribute to this effect.

## 4. Advantages

List the advantages disclosed in the description.

For each advantage, indicate whether it is:
- technical
- economic/commercial
- usability-related
- unclear/non-technical

## 5. Prior art mentioned

Identify any prior-art systems, documents, methods, devices, or general background technologies mentioned.

## 6. Drawbacks of the prior art

Identify any disadvantages, limitations, or problems of the prior art discussed in the description.

## 7. Differences over the mentioned prior art

For each prior-art item or background system, identify the disclosed differences of the invention over that prior art.

Use a table:

| Prior art / background | Drawback mentioned | Difference of invention | Technical effect of difference | Basis in description |
|---|---|---|---|---|

## 8. Examiner-style summary

Provide a short EPO-style summary of:

- the closest disclosed background, if any
- the objective or underlying technical problem
- the proposed solution
- the technical effect
- the disclosed advantages

---

After completing the above analysis, also output a standalone 4-paragraph plain-text summary wrapped exactly between the markers below (include the marker lines verbatim):

{_SUMMARY_BEGIN}
[Paragraph 1 – Underlying technical problem: State the underlying technical problem of the invention, whether explicitly stated or inferred from the description.]

[Paragraph 2 – Technical effect: Describe the technical effect on which the solution is based and which features contribute to it.]

[Paragraph 3 – Solution: Describe the solution as disclosed in the application.]

[Paragraph 4 – Advantages: Describe the advantages of the disclosed solution as extracted from both the description and the claims.]
{_SUMMARY_END}
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    # Extract 4-paragraph summary (existing behaviour)
    match_4p = re.search(
        rf"{re.escape(_SUMMARY_BEGIN)}(.*?){re.escape(_SUMMARY_END)}",
        raw,
        re.DOTALL,
    )
    if match_4p:
        four_p_summary = match_4p.group(1).strip()
        raw_without_4p = raw[: match_4p.start()].strip() + raw[match_4p.end():]
    else:
        four_p_summary = ""
        raw_without_4p = raw

    # Extract skill summary (new behaviour)
    extracted = extract_skill_summary(raw_without_4p)

    return {"result": extracted["result"], "summary": extracted["summary"]}


BASIC_ANALYSIS_SKILL = {
    "name": "Basic analysis (Problem, technical effect)",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_basic_analysis.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/basic_analysis.py tests/skills/test_basic_analysis.py
git commit -m "feat: add prior_context and skill summary to basic_analysis"
```

---

## Task 4: Update `skills/analyse_ind_claims.py`

**Files:**
- Modify: `skills/analyse_ind_claims.py`
- Create: `tests/skills/test_analyse_ind_claims.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_analyse_ind_claims.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.analyse_ind_claims import build_prompt, run

MOCK_RESPONSE = f"""# Independent Claims Analysis

Some analysis.

{_SUMMARY_BEGIN}
- 2 independent claims found
- Rule 43(2) complied with
- No CII issues
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
        prior_context="- Basic analysis done",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Basic analysis done" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.analyse_ind_claims.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "2 independent claims found" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_analyse_ind_claims.py -v`
Expected: failures — `prior_context` param not accepted, `_SUMMARY_BEGIN` not in prompt

- [ ] **Step 3: Update `skills/analyse_ind_claims.py`**

```python
# skills/analyse_ind_claims.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:40000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
Your task is to analyse the independent claims of the uploaded claim set.

Focus on:

1. Identifying the categories of all independent claims.
2. Checking compliance with Rule 43(2) EPC.
3. Checking the allowability of computer-implemented claims.
4. Checking whether there is a sufficient technical correlation between independent device/system claims and independent method claims.

Important rules:
- Base the analysis only on the provided claims.
- Do not invent claim content.
- Distinguish clearly between claim categories:
  - device
  - apparatus
  - system
  - method
  - process
  - use
  - computer program
  - computer-readable medium
  - data carrier
  - signal
  - unclear
- Identify independent claims by claim wording and dependency.
- If the claim dependency is unclear, say so.
- Apply EPO-style reasoning.
- Do not perform novelty or inventive-step analysis.

CASE:
{case_name}

SOURCE MATERIAL:
{docs_block}

Prepare the output in the following structure:

# Independent Claims Analysis

## 1. Documents considered

List the documents used and their classified document type.

## 2. Independent claims identified

Create a table:

| Independent claim | Category | Subject-matter | Reason why independent |
|---|---|---|---|

## 3. Claim category analysis

For each independent claim, explain:
- claim category
- technical subject-matter
- whether it is a product, process, use, or computer-implemented category
- whether the category is clear

## 4. Rule 43(2) EPC assessment

Assess whether the claim set contains more than one independent claim in the same category.

Use this table:

| Category | Independent claims in category | Potential Rule 43(2) issue | Examiner assessment |
|---|---|---|---|

Then assess whether any of the Rule 43(2) exceptions may apply:

- interrelated products
- different uses of a product or apparatus
- alternative solutions to a particular problem where a single claim would be inappropriate

For each exception, state whether it appears applicable and why.

Conclude whether Rule 43(2) EPC appears complied with.

## 5. Computer-implemented claim assessment

Identify any claims directed to:
- software
- computer program
- algorithm
- data processing
- AI / machine learning
- mathematical method
- business method
- presentation of information
- computer-readable medium
- signal

For each such claim, assess:

| Claim | CII-related subject-matter | Technical means present? | Potential exclusion issue | Examiner comment |
|---|---|---|---|---|

Apply EPO-style analysis:
- A claim involving technical means, such as a computer, processor, memory, sensor, network, or control unit, normally has technical character as a whole.
- Purely abstract algorithms, business methods, mathematical methods, or presentations of information may raise issues under Art. 52(2) and (3) EPC.
- Do not decide inventive step under COMVIK; only flag whether the claim appears allowable in category/form as a computer-implemented invention.

## 6. Correlation between device/system and method claims

If both device/system claims and method claims are present, compare them.

Use this table:

| Device/system claim | Corresponding method claim | Shared technical features | Missing or inconsistent features | Correlation assessment |
|---|---|---|---|---|

Assess whether:
- the method claim corresponds to the operation/use of the device/system
- the method steps reflect the functional features of the device/system
- essential features appear consistently claimed
- there are unexplained mismatches
- the independent claims appear to define the same general inventive concept

If no device/system-method pair exists, state this clearly.

## 7. Examiner-style objections, if any

Draft concise EPO-style objections for:
- Rule 43(2) EPC
- unclear or inconsistent claim categories
- potentially excluded computer-implemented subject-matter
- insufficient correlation between independent claims

Only draft objections where the issue is reasonably supported by the claim wording.

## 8. Overall conclusion

Provide a concise conclusion on:
- independent claim categories
- Rule 43(2) EPC compliance
- computer-implemented claim form
- correlation between independent claims
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


ANALYSE_IND_CLAIMS_SKILL = {
    "name": "Analyse Ind. Claims",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_analyse_ind_claims.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/analyse_ind_claims.py tests/skills/test_analyse_ind_claims.py
git commit -m "feat: add prior_context and skill summary to analyse_ind_claims"
```

---

## Task 5: Update `skills/technical_features.py`

**Files:**
- Modify: `skills/technical_features.py`
- Create: `tests/skills/test_technical_features.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_technical_features.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.technical_features import build_prompt, run

MOCK_RESPONSE = f"""# Technical Features Analysis

Some analysis.

BEGIN_TECHNICAL_FEATURES_JSON
{{}}
END_TECHNICAL_FEATURES_JSON

{_SUMMARY_BEGIN}
- 5 independent features extracted from claim 1
- 3 method steps found in claim 5
- No unclear features
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
        prior_context="- Claim categories identified",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Claim categories identified" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.technical_features.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "5 independent features" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_technical_features.py -v`
Expected: failures — `prior_context` not accepted, `_SUMMARY_BEGIN` not in prompt

- [ ] **Step 3: Update `skills/technical_features.py`**

Add the following imports at the top and modify `build_prompt` / `run`:

```python
# skills/technical_features.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:40000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
Your task is to extract the technical features from the provided claims with maximum structural precision.

STRICT INSTRUCTIONS:
1. Work claim by claim.
2. Do not merge features.
3. Extract atomic technical features.
3a. Each element introduced by "comprising", a semicolon, "wherein", or a separate functional clause must normally be a separate feature.
3b. Do not output "a detector, a feature amount extractor, and a display" as one feature. Output them as separate features.
3c. If a feature contains several components joined by "and", split them if they correspond to separate technical entities or separate technical functions.
4. Preserve original claim wording as far as possible.
5. Maintain the hierarchy of each claim.
6. Identify dependencies between claims.
7. Distinguish structural features, functional features, and method steps.
8. Do NOT interpret beyond the claim wording.
9. If unclear, explicitly state "unclear".
10. The JSON block must be valid JSON. Do not include comments, trailing commas, markdown fences, or explanatory text inside the JSON block.

FEATURE EXTRACTION RULES:
- A claim preamble such as "A machine tool" or "A display device" is a feature.
- Each claimed component is a separate feature.
- Each functional limitation of a component is a separate feature if it defines what the component does.
- Each "wherein" clause is normally a separate feature.
- For dependent claims, extract only the additional feature introduced by the dependent claim, not the whole parent claim again.
- For method claims, extract method steps in sequential order.
- If a claim contains alternatives, preserve the alternatives in the feature text.

CASE:
{case_name}

SOURCE MATERIAL:
{docs_block}

First provide a normal Markdown analysis.

Then, at the very end, provide a machine-readable JSON block between these exact markers:

BEGIN_TECHNICAL_FEATURES_JSON
{{
  "claim_overview": [
    {{
      "claim_number": 1,
      "dependency": "independent",
      "claim_type": "device",
      "main_subject": "..."
    }}
  ],
  "features": [
    {{
      "claim_number": 1,
      "feature_id": "F1",
      "feature_text": "...",
      "feature_type": "structural",
      "relationship_or_function": "..."
    }}
  ],
  "method_steps": [
    {{
      "claim_number": 5,
      "step_id": "S1",
      "step_text": "...",
      "input": "...",
      "operation": "...",
      "output": "..."
    }}
  ],
  "dependent_claims": [
    {{
      "claim_number": 2,
      "parent_claim": 1,
      "added_feature": "...",
      "technical_contribution": "..."
    }}
  ],
  "essential_features": [
    {{
      "claim_number": 1,
      "feature": "...",
      "status": "clearly essential",
      "reason": "..."
    }}
  ],
  "examiner_summary": "..."
}}
END_TECHNICAL_FEATURES_JSON

Rules for the JSON block:
- Use only double quotes.
- Use integers for claim numbers where possible.
- Use empty arrays [] if no method steps, dependent claims, or essential features are identified.
- Do not wrap the JSON in ```json fences.
- Do not include any text between BEGIN_TECHNICAL_FEATURES_JSON and the opening {{.
- Do not include any text between the closing }} and END_TECHNICAL_FEATURES_JSON.
- Every atomic technical feature must be a separate object in the "features" array.
- Do not put feature IDs such as F1/F2 inside "feature_text"; use "feature_id" only for the ID.
- For dependent claims, the "features" array should contain the added feature, not the entire parent claim text.

Markdown output structure:

# Technical Features Analysis

## 1. Independent and dependent claims

## 2. Claim-by-claim feature extraction

## 3. Method steps, if present

## 4. Dependent claim contributions

## 5. Essential features

## 6. Examiner-style summary
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


TECHNICAL_FEATURES_SKILL = {
    "name": "Technical features",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_technical_features.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/technical_features.py tests/skills/test_technical_features.py
git commit -m "feat: add prior_context and skill summary to technical_features"
```

---

## Task 6: Update `skills/prior_art_analysis.py`

**Files:**
- Modify: `skills/prior_art_analysis.py`
- Create: `tests/skills/test_prior_art_analysis.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_prior_art_analysis.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.prior_art_analysis import build_prompt, run

MOCK_RESPONSE = f"""# Prior Art Analysis

Some analysis.

{_SUMMARY_BEGIN}
- D1 discloses a sensor array
- D2 discloses a calibration method
- No document discloses the claimed combination
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
        prior_context="- Features extracted",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Features extracted" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.prior_art_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "D1 discloses a sensor array" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_prior_art_analysis.py -v`
Expected: failures — `prior_context` not accepted, `_SUMMARY_BEGIN` not in prompt

- [ ] **Step 3: Update `skills/prior_art_analysis.py`**

```python
# skills/prior_art_analysis.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:50000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
Your task is to analyse prior-art documents, such as published patent applications,
patents, scientific papers, technical articles, standards, or product documents.

The purpose of this skill is NOT yet to perform full novelty or inventive-step analysis.
The purpose is to prepare a concise, structured prior-art summary that can later be
used for mapping against technical features of claims.

Important rules:
- Base the analysis only on the provided documents.
- Do not invent missing disclosure.
- Distinguish clearly between explicit disclosure and inference.
- Preserve technical terminology.
- Identify disclosed technical features in a way that can later be mapped to claim features.
- If the document is a patent publication, identify claims/embodiments where possible.
- If the document is a scientific paper, identify experimental setup, technical method, and results where possible.
- Do not make a final Art. 54 EPC or Art. 56 EPC conclusion yet.

CASE:
{case_name}

SOURCE MATERIAL:
{docs_block}

Prepare the output in the following structure:

# Prior Art Analysis

## 1. Documents considered

List each prior-art document and, if possible, identify:
- document title
- publication number or bibliographic identifier
- document type
- relevant technical field

## 2. Short summary

For each prior-art document, provide a concise technical summary.

Use this table:

| Document | Short technical summary | Main purpose / technical problem | Main disclosed solution |
|---|---|---|---|

## 3. Disclosed technical features

Extract the main technical features disclosed in each prior-art document.

Use this table:

| Document | Feature No. | Disclosed technical feature | Where disclosed / basis | Explicit or inferred |
|---|---|---|---|---|

## 4. Relevant embodiments or examples

Identify embodiments, examples, figures, or experimental setups that may be relevant for later claim mapping.

Use this table:

| Document | Embodiment / example / figure | Relevant disclosure | Possible relevance for claim mapping |
|---|---|---|---|

## 5. Advantages and technical effects disclosed

Identify any stated advantages or technical effects.

Use this table:

| Document | Technical effect / advantage | Feature causing the effect | Basis in document |
|---|---|---|---|

## 6. Potential mapping candidates for later novelty analysis

Without making a final novelty conclusion, identify features that appear suitable for later comparison with claim features.

Use this table:

| Document | Potentially mappable disclosure | Why it may be relevant |
|---|---|---|

## 7. Examiner-style prior-art summary

Provide a concise EPO-style summary of the most relevant disclosure of each prior-art document.
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


PRIOR_ART_ANALYSIS_SKILL = {
    "name": "Prior art analysis",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_prior_art_analysis.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/prior_art_analysis.py tests/skills/test_prior_art_analysis.py
git commit -m "feat: add prior_context and skill summary to prior_art_analysis"
```

---

## Task 7: Update `skills/novelty_inventive_step.py`

**Files:**
- Modify: `skills/novelty_inventive_step.py`
- Create: `tests/skills/test_novelty_inventive_step.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_novelty_inventive_step.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.novelty_inventive_step import build_prompt, run

MOCK_RESPONSE = f"""# Novelty / Inventive Step Analysis

Some analysis.

BEGIN_NOVELTY_IS_JSON
{{}}
END_NOVELTY_IS_JSON

{_SUMMARY_BEGIN}
- Claim 1 novel over D1 and D2
- Distinguishing feature: real-time calibration
- Inventive step present — D2 teaches away from combination
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
        prior_context="- D1 discloses a sensor array",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "D1 discloses a sensor array" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.novelty_inventive_step.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "D1.txt", "text": "Prior art."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "Claim 1 novel" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_novelty_inventive_step.py -v`
Expected: failures

- [ ] **Step 3: Update `skills/novelty_inventive_step.py`**

Add imports and modify `build_prompt` / `run` — keep all existing prompt content, add `prior_context_block` injection and `SUMMARY_INSTRUCTION` at the end:

```python
# skills/novelty_inventive_step.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:50000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
Your task is to prepare a preliminary Novelty and Inventive Step analysis under
Articles 54 and 56 EPC.

The key output must be a claim-feature mapping table:

| Claim | Feature | D1 | D2 | D3 | ... |

The claims and prior-art documents may be in English, German, or French.
Compare technical meaning, not merely identical wording.

GENERAL RULES:
- Use only the provided documents.
- Do not invent disclosure.
- Identify atomic claim features.
- Identify prior-art disclosures corresponding to each claim feature.
- If a prior-art document discloses a feature, identify:
  - reference sign if available,
  - paragraph number if available,
  - page/line/figure if paragraph number is not available,
  - short disclosure.
- If a feature is not disclosed, mark it as "NOT COVERED".
- If only partly disclosed, mark it as "PARTIAL".
- If fully disclosed, mark it as "COVERED".
- Treat equivalent English/German/French terminology as potentially matching.
- If translation uncertainty exists, mention it.

DOCUMENT LABELS:
Assign labels:
- D1 = closest or most relevant prior-art document
- D2, D3, ... = further prior-art documents

If closest prior art is not obvious, choose as D1 the document covering the largest number of claim features.

CASE:
{case_name}

SOURCE MATERIAL:
{docs_block}

First provide a concise Markdown analysis.

Then provide a machine-readable JSON block between these exact markers:

BEGIN_NOVELTY_IS_JSON
{{
  "prior_art_documents": [
    {{
      "label": "D1",
      "document": "...",
      "language": "English/German/French/unknown",
      "type": "patent/scientific paper/technical document/unknown",
      "relevance": "..."
    }}
  ],
  "mapping_table": [
    {{
      "claim": 1,
      "feature": "...",
      "documents": {{
        "D1": {{
          "status": "COVERED",
          "reference_sign": "...",
          "basis": "paragraph/page/line/figure",
          "disclosure": "...",
          "comment": "..."
        }},
        "D2": {{
          "status": "NOT COVERED",
          "reference_sign": "",
          "basis": "",
          "disclosure": "",
          "comment": "..."
        }}
      }}
    }}
  ],
  "novelty_conclusions": [
    {{
      "claim": 1,
      "document": "D1",
      "all_features_covered": false,
      "missing_features": ["..."],
      "conclusion": "NOVEL"
    }}
  ],
  "closest_prior_art": {{
    "document": "D1",
    "reason": "...",
    "covered_features": ["..."],
    "missing_features": ["..."]
  }},
  "differences_over_d1": [
    {{
      "claim": 1,
      "missing_feature": "...",
      "technical_effect": "...",
      "basis_or_reasoning": "..."
    }}
  ],
  "synergy": [
    {{
      "claim": 1,
      "missing_features": ["..."],
      "assessment": "separate effects/synergistic effect/unclear",
      "reasoning": "..."
    }}
  ],
  "objective_technical_problem": [
    {{
      "claim": 1,
      "starting_point": "D1",
      "differences": ["..."],
      "technical_effect": "...",
      "problem": "..."
    }}
  ],
  "secondary_documents": [
    {{
      "missing_feature_over_d1": "...",
      "found": true,
      "document": "D2",
      "basis": "...",
      "comment": "..."
    }}
  ],
  "obviousness": [
    {{
      "claim": 1,
      "combination": "D1 + D2",
      "missing_feature_supplied": true,
      "would_combine": "yes/no/unclear",
      "straightforward_amendment": "yes/no/unclear",
      "conclusion": "NOT INVENTIVE / INVENTIVE STEP MAY BE PRESENT / unclear",
      "reasoning": "..."
    }}
  ],
  "final_opinion": [
    {{
      "claim": 1,
      "novelty": "NOVEL / NOT NOVEL OVER D1 / unclear",
      "inventive_step": "NOT INVENTIVE / INVENTIVE STEP MAY BE PRESENT / unclear",
      "closest_prior_art": "D1",
      "missing_features": ["..."],
      "technical_effect": "...",
      "objective_technical_problem": "...",
      "reasoning": "..."
    }}
  ]
}}
END_NOVELTY_IS_JSON

JSON RULES:
- The JSON must be valid.
- Use only double quotes.
- Use empty arrays [] if no entries exist.
- Do not wrap the JSON in markdown fences.
- Do not include text inside the JSON block except JSON.
- Each claim feature must be a separate row in "mapping_table".
- Each D1/D2/D3 cell must have a "status" field:
  - "COVERED"
  - "PARTIAL"
  - "NOT COVERED"
  - "UNCLEAR"
- If a feature is not covered, status must be exactly "NOT COVERED".
- If all features of an independent claim are covered by one prior-art document, conclude "NOT NOVEL OVER Dx".
- If at least one feature is not covered, conclude "NOVEL".
- Starting from D1, identify missing features, technical effect, objective technical problem, and whether D2-Dxy supplies the missing feature.
- If D1 + Dxy makes the missing feature straightforward and the combination is motivated, conclude "NOT INVENTIVE".

Markdown output structure:

# Novelty / Inventive Step Analysis

## 1. Prior-art documents

## 2. Claim-feature mapping

## 3. Novelty conclusions

## 4. Closest prior art

## 5. Differences over D1

## 6. Technical effect and objective technical problem

## 7. Secondary documents and obviousness

## 8. Final preliminary opinion
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


NOVELTY_INVENTIVE_STEP_SKILL = {
    "name": "Novelty/ Inventive Step analysis",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_novelty_inventive_step.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/novelty_inventive_step.py tests/skills/test_novelty_inventive_step.py
git commit -m "feat: add prior_context and skill summary to novelty_inventive_step"
```

---

## Task 8: Update `skills/epo_123_2.py`

**Files:**
- Modify: `skills/epo_123_2.py`
- Create: `tests/skills/test_epo_123_2.py`

Note: `render_input_ui()` is kept unchanged. `build_prompt()` does not use `user_input` in the prompt body — this is existing behaviour and is preserved.

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_epo_123_2.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.epo_123_2 import build_prompt, run

MOCK_RESPONSE = f"""# Article 123(2) EPC Assessment

Some analysis.

{_SUMMARY_BEGIN}
- Claim 1 amendment has basis on page 5, lines 12-15
- No intermediate generalisation found
- Art. 123(2) complied with
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "Description."}],
        structured_documents=None,
        user_input={},
        prior_context="- Novelty present",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Novelty present" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "Description."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "Description."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.epo_123_2.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "desc.txt", "text": "Description."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "Art. 123(2) complied with" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_epo_123_2.py -v`
Expected: failures

- [ ] **Step 3: Update `skills/epo_123_2.py`**

```python
# skills/epo_123_2.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def render_input_ui():
    st.markdown(
        """
        This skill checks whether amended claims comply with **Article 123(2) EPC**.
        """
    )

    claims_as_filed = st.text_area(
        "Claims as filed",
        height=250,
        placeholder="Paste the original claims here if not fully contained in the uploaded documents.",
    )

    amended_claims = st.text_area(
        "Amended claims",
        height=250,
        placeholder="Paste the amended claims here.",
    )

    applicant_basis = st.text_area(
        "Applicant's indicated basis",
        height=150,
        placeholder="Example: page 5, lines 12-20; claim 3 as filed; Fig. 2.",
    )

    examiner_focus = st.text_area(
        "Specific examiner focus",
        height=120,
        placeholder="Example: check intermediate generalisation in claim 1, feature concerning the locking member.",
    )

    return {
        "claims_as_filed": claims_as_filed,
        "amended_claims": amended_claims,
        "applicant_basis": applicant_basis,
        "examiner_focus": examiner_focus,
    }


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:40000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an experienced European Patent Office examiner.
{prior_context_block}
You must examine whether the amendments comply with Article 123(2) EPC.

Apply the EPO gold standard:

An amendment is allowable only if the skilled person, using common general knowledge, would derive the amended subject-matter directly and unambiguously from the application as filed, explicitly or implicitly.

Do not use obviousness reasoning.
Do not accept amendments because they are merely technically plausible.
Do not speculate beyond the application as filed.

CASE:
{case_name}

STRUCTURED SOURCE MATERIAL:
{docs_block}

TASK:

Prepare a strict EPO-style Article 123(2) EPC assessment.

First identify:
- claims as filed
- amended claims
- description as filed
- any passages potentially forming basis

Then compare the amended claims against the original disclosure.

Use this output structure:

# Article 123(2) EPC Assessment

## 1. Documents compared

List the documents used and their classified document type.

## 2. Identified claim set

Identify:
- claims as filed
- amended claims
- independent claims
- relevant amended features

## 3. Amendment table

Create a table with:

- claim
- amended feature
- type of amendment
- alleged or possible basis
- examiner assessment
- preliminary conclusion

## 4. Detailed analysis

For each amendment:

- amended feature
- possible basis
- actual original disclosure
- whether the amendment is explicitly disclosed
- whether the amendment is implicitly disclosed
- whether there is an intermediate generalisation
- whether there is a combination of embodiments
- whether there is a selection from lists
- whether an essential feature has been omitted
- conclusion under Article 123(2) EPC

## 5. Overall conclusion

State whether the amended claims comply with Article 123(2) EPC.

## 6. Possible allowable fallback positions

Suggest fallback amendments only if they are directly and unambiguously supported.

## 7. Draft EPO objection text

Draft formal examination language suitable for a communication under Article 94(3) EPC.

Be precise.
Use claim numbers and document references where available.
If the basis cannot be verified, say so.
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


EPO_123_2_SKILL = {
    "name": "EPO Article 123(2) EPC Examiner",
    "render_input_ui": render_input_ui,
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_epo_123_2.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/epo_123_2.py tests/skills/test_epo_123_2.py
git commit -m "feat: add prior_context and skill summary to epo_123_2"
```

---

## Task 9: Update `skills/votum.py`

**Files:**
- Modify: `skills/votum.py`
- Create: `tests/skills/test_votum.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_votum.py
from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.votum import build_prompt, run

MOCK_RESPONSE = f"""VOTUM

1 Independent Claims ...

{_SUMMARY_BEGIN}
- Claim 1 novel and inventive
- Art. 123(2) complied with
- No further objections
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
        prior_context="- Art. 123(2) complied with",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Art. 123(2) complied with" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.votum.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "Claim 1 novel and inventive" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_votum.py -v`
Expected: failures

- [ ] **Step 3: Update `skills/votum.py`**

```python
# skills/votum.py
from core.llm import call_llm
from core.structure import build_structured_context
from core.skill_utils import SUMMARY_INSTRUCTION, extract_skill_summary, format_prior_context_block


def build_prompt(case_name, source_documents, structured_documents, user_input, prior_context=""):
    if structured_documents:
        docs_block = build_structured_context(structured_documents)
    else:
        docs_block = ""
        for doc in source_documents:
            docs_block += f"\n\n===== DOCUMENT: {doc['filename']} =====\n"
            docs_block += doc["text"][:50000]

    prior_context_block = format_prior_context_block(prior_context)

    prompt = f"""
You are an expert European Patent Office examiner.
{prior_context_block}
You are drafting a concise internal EPO examination report called a "Votum".

Analyse the uploaded patent documents strictly according to the EPC and the EPO Guidelines for Examination.

Application / case name:
{case_name}

Use the language of the main examination document if detectable. Otherwise use English.

Be brief and precise.
Avoid repetition, verbose legal preambles, and restating what is already obvious from the documents.
Every section must be as short as possible while remaining complete.

Use the following exact structure.

─────────────────────────────────────────
VOTUM — REQUIRED STRUCTURE AND FORMAT
─────────────────────────────────────────

1  Independent Claims

Write one short sentence per independent claim in this form:

Apparatus claim 1 discloses a [brief subject-matter description].

Method claim X discloses a method for [brief purpose].

If Rule 43(2)(a), 43(2)(b), or 43(2)(c) EPC applies to multiple independent claims of the same category, state which sub-paragraph applies and give a one-sentence justification.

Otherwise omit the Rule 43(2) discussion.

2  Basis for Amendments (Art. 123(2), 76(1) EPC)

Use compact mapping format.

For each claim, state only:
- what changed;
- where the basis is;
- page and line numbers or paragraph numbers from the original description;
- original claim numbers, where relevant.

Unchanged claims must be written as:

Claim X = orig. claim X

Example format:

Claim 1 = orig. claim 1 and
  [brief description of addition/change] (Basis: description page X, lines Y–Z "[short quote]"),
  [next addition if any] (Basis: description page X, lines Y–Z).

Claim 2 = orig. claim 2

Claim 3 = orig. claim 4

Reference signs have been added to the claims.

3  Prior Art; Novelty (Art. 54 EPC)

List the cited prior-art documents.

Use one line per document:

D1, publication number, applicant, date.

Then write one paragraph per independent claim.

For each independent claim, state the key distinguishing feature or features over each cited document.

Do not repeat the full claim wording.

Use the form:

"Dx does not disclose [distinguishing feature of claim 1]."

End this section with one sentence identifying the closest prior art and why.

4  Inventive Step (Art. 56 EPC)

4.1  Closest Prior Art

Name the closest prior art document in one sentence.

Then write out the wording of claim 1 from the amended claims feature by feature.

After each feature disclosed in the closest prior art, add an inline citation:

(Dx: [location])

For features not disclosed in the closest prior art, add no citation.

Do not use strikethrough.

After the claim text, write:

The subject-matter of claim 1 differs from [Dx] in that:
  a) [first distinguishing feature, verbatim from claim]
  b) [next distinguishing feature, if any]

The subject-matter of claim 1 is therefore novel (Art. 54 EPC).

4.2  Technical Effect and Problem to be Solved

Use two sentences maximum:

The technical effect of the distinguishing feature(s) is [effect].

The objective technical problem is how to [problem].

4.3  Solution

Use two to three sentences.

Explain how the characterising feature of claim 1 solves the objective technical problem.

Refer to the description if useful.

4.4  Why the Solution is Not Obvious

Write one focused paragraph.

Do not use sub-sections.

Do not repeat facts already stated.

Reference specific passages of prior-art documents where possible.

State what the skilled person starting from the closest prior art would or would not do and why.

End with:

The same reasoning applies mutatis mutandis to [other independent claim(s)].

5  Further Relevant Information (Art. 82, 83, 84, 52, 53 EPC)

Only include this section if there is something to report.

If all objections have been resolved, write one sentence:

[Objection type] objections raised in the previous communication have been resolved by the amendments.

If issues remain, state them briefly.

─────────────────────────────────────────
STRICT RULES
─────────────────────────────────────────

- No introductory boilerplate.
- No "In accordance with..." style legal preambles.
- No restatement of legal standards.
- No repeating information from one section in another section.
- Method claims and other independent claims should normally be handled with:
  "The same reasoning applies mutatis mutandis to claim X."
- Do not repeat the full inventive-step analysis for each independent claim unless necessary.
- Do not analyse dependent claims individually unless they contain a feature that independently contributes to inventive step.
- If dependent claims do not add independently inventive matter, omit dependent-claim analysis.
- Keep the total length concise and examination-style.
- Base all findings on the provided documents.
- If a necessary document or passage is missing, state this clearly.

SOURCE DOCUMENTS:
{docs_block}
{SUMMARY_INSTRUCTION}"""

    return prompt


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    prompt = build_prompt(
        case_name=case_name,
        source_documents=source_documents,
        structured_documents=structured_documents,
        user_input=user_input,
        prior_context=prior_context,
    )

    raw = call_llm(
        prompt=prompt,
        provider=llm_config["provider"],
        model=llm_config["model"],
    )

    return extract_skill_summary(raw)


VOTUM_SKILL = {
    "name": "Votum",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_votum.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/votum.py tests/skills/test_votum.py
git commit -m "feat: add prior_context and skill summary to votum"
```

---

## Task 10: Create `skills/complete_examination.py`

**Files:**
- Create: `skills/complete_examination.py`
- Create: `tests/skills/test_complete_examination.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/skills/test_complete_examination.py
from unittest.mock import patch, MagicMock
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END


def _make_mock_skill(name, summary):
    return {
        "name": name,
        "run": MagicMock(return_value={"result": f"Full output of {name}", "summary": summary}),
    }


def test_run_calls_all_seven_skills():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    skill_mocks = [
        _make_mock_skill(key, f"Summary of {key}")
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    for mock in skill_mocks:
        mock["run"].assert_called_once()


def test_run_returns_combined_report():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    skill_mocks = [
        _make_mock_skill(key, f"Summary of {key}")
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    assert isinstance(out, dict)
    assert "result" in out
    assert "summary" in out
    for key, _ in _SKILLS_IN_ORDER:
        assert f"Full output of {key}" in out["result"]


def test_run_chains_prior_context():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    call_args_list = []

    def make_capturing_run(name, summary):
        def capturing_run(**kwargs):
            call_args_list.append((name, kwargs.get("prior_context", "")))
            return {"result": f"Full output of {name}", "summary": summary}
        return capturing_run

    skill_mocks = [
        {"name": key, "run": make_capturing_run(key, f"Summary of {key}")}
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    # First skill gets empty prior_context
    assert call_args_list[0][1] == ""
    # Second skill gets non-empty prior_context containing first skill's summary
    assert "Summary of" in call_args_list[1][1]
    # Each subsequent skill gets more context
    for i in range(2, len(call_args_list)):
        assert len(call_args_list[i][1]) > len(call_args_list[i - 1][1])
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/skills/test_complete_examination.py -v`
Expected: `ModuleNotFoundError` — `skills/complete_examination.py` does not exist

- [ ] **Step 3: Create `skills/complete_examination.py`**

```python
# skills/complete_examination.py
from skills.basic_analysis import BASIC_ANALYSIS_SKILL
from skills.analyse_ind_claims import ANALYSE_IND_CLAIMS_SKILL
from skills.technical_features import TECHNICAL_FEATURES_SKILL
from skills.prior_art_analysis import PRIOR_ART_ANALYSIS_SKILL
from skills.novelty_inventive_step import NOVELTY_INVENTIVE_STEP_SKILL
from skills.epo_123_2 import EPO_123_2_SKILL
from skills.votum import VOTUM_SKILL

_SKILLS_IN_ORDER = [
    ("basic_analysis", BASIC_ANALYSIS_SKILL),
    ("analyse_ind_claims", ANALYSE_IND_CLAIMS_SKILL),
    ("technical_features", TECHNICAL_FEATURES_SKILL),
    ("prior_art_analysis", PRIOR_ART_ANALYSIS_SKILL),
    ("novelty_inventive_step", NOVELTY_INVENTIVE_STEP_SKILL),
    ("epo_123_2", EPO_123_2_SKILL),
    ("votum", VOTUM_SKILL),
]

_SECTION_SEPARATOR = "\n\n" + "=" * 60 + "\n"


def run(
    case_name,
    source_documents,
    structured_documents,
    user_input,
    llm_config,
    prior_context="",
):
    accumulated_context = prior_context
    combined_report = ""

    for _key, skill in _SKILLS_IN_ORDER:
        output = skill["run"](
            case_name=case_name,
            source_documents=source_documents,
            structured_documents=structured_documents,
            user_input=user_input,
            llm_config=llm_config,
            prior_context=accumulated_context,
        )

        result = output["result"] if isinstance(output, dict) else str(output)
        summary = output.get("summary", "") if isinstance(output, dict) else ""

        combined_report += (
            f"{_SECTION_SEPARATOR}{skill['name'].upper()}\n{'=' * 60}\n\n{result}"
        )

        if summary:
            accumulated_context += f"\n[{skill['name']}]\n{summary}\n"

    return {
        "result": combined_report,
        "summary": "Complete examination finished — 7 skills executed.",
    }


COMPLETE_EXAMINATION_SKILL = {
    "name": "Complete Examination",
    "run": run,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/skills/test_complete_examination.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/complete_examination.py tests/skills/test_complete_examination.py
git commit -m "feat: add complete_examination orchestrator skill"
```

---

## Task 11: Register the skill and run full test suite

**Files:**
- Modify: `skills/registry.py`

- [ ] **Step 1: Update `skills/registry.py`**

```python
# skills/registry.py
from skills.basic_analysis import BASIC_ANALYSIS_SKILL
from skills.technical_features import TECHNICAL_FEATURES_SKILL
from skills.analyse_ind_claims import ANALYSE_IND_CLAIMS_SKILL
from skills.prior_art_analysis import PRIOR_ART_ANALYSIS_SKILL
from skills.novelty_inventive_step import NOVELTY_INVENTIVE_STEP_SKILL
from skills.epo_123_2 import EPO_123_2_SKILL
from skills.votum import VOTUM_SKILL
from skills.complete_examination import COMPLETE_EXAMINATION_SKILL


SKILLS = {
    "basic_analysis": BASIC_ANALYSIS_SKILL,
    "technical_features": TECHNICAL_FEATURES_SKILL,
    "analyse_ind_claims": ANALYSE_IND_CLAIMS_SKILL,
    "prior_art_analysis": PRIOR_ART_ANALYSIS_SKILL,
    "novelty_inventive_step": NOVELTY_INVENTIVE_STEP_SKILL,
    "epo_123_2": EPO_123_2_SKILL,
    "votum": VOTUM_SKILL,
    "complete_examination": COMPLETE_EXAMINATION_SKILL,
}
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass — no failures, no errors

- [ ] **Step 3: Commit**

```bash
git add skills/registry.py
git commit -m "feat: register complete_examination in skill registry"
```
