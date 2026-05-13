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