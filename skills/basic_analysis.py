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
[Paragraph 1 - Underlying technical problem: State the underlying technical problem of the invention, whether explicitly stated or inferred from the description.]

[Paragraph 2 - Technical effect: Describe the technical effect on which the solution is based and which features contribute to it.]

[Paragraph 3 - Solution: Describe the solution as disclosed in the application.]

[Paragraph 4 - Advantages: Describe the advantages of the disclosed solution as extracted from both the description and the claims.]
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
        raw_without_4p = raw[: match_4p.start()].strip() + raw[match_4p.end():]
    else:
        raw_without_4p = raw

    # Extract skill summary (new behaviour)
    extracted = extract_skill_summary(raw_without_4p)

    return {"result": extracted["result"], "summary": extracted["summary"]}


BASIC_ANALYSIS_SKILL = {
    "name": "Basic analysis (Problem, technical effect)",
    "run": run,
}
