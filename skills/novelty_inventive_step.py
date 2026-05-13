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