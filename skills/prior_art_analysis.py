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