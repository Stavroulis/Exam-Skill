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