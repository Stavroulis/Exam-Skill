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