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
- where the basis in the description as originaly filed is;
- page and line numbers or paragraph numbers from the original description;
- original claim numbers, where relevant.

Unchanged claims must be written as:

Claim X = orig. claim X

Example format:

Claim 1 = orig. claim 1 and
  [brief description of addition/change] (Basis: description as originally filed  page X, lines Y–Z "[short quote]"),
  [next addition if any] (Basis: description as originally filed page X, lines Y–Z).

Claim 2 = orig. claim 2
Claims 3- 5 = orig. claims 4- 6

Reference signs have been added to the claims.

3  Prior Art; Novelty (Art. 54 EPC)

Reference is made to the following documents; the numbering will be adhered
to in the rest of the procedure.

Use one line per document:
D1, publication number, applicant, date.

List the cited prior-art documents.

4   Novelty (Article 54 EPC): distinguishing features

Write one paragraph per cited prior art document.

For each independent claim, state the key distinguishing feature or features over each cited document.

Do not repeat the full claim wording.

Use the form:

"Dx does not disclose [distinguishing feature of claim 1]."

End this section with one sentence identifying the closest prior art and why.

Use the form:

D1 is choosen as the closest prior because [reasoning]


5  Inventive Step (Art. 56 EPC)

5.1  Closest Prior Art

Document D[x] is regarded as being the closest prior art to the subject‐matter of
claim [independent claim], and discloses (the references in parentheses applying to this
document):

Then write out the wording of claim 1 from the amended claims feature by feature.
After each feature disclosed in the closest prior art, add an inline citation as extractable from the esop:
(Dx: [location])
For features not disclosed in the closest prior art, add no citation strike them through.
Use the the respective citations for each technical feature as in the mapping for the claim from the esop (text in parentheses in the esop in the sections "Novelty" or "Inventive step" for the independent claims ).

After the claim text, write:

The subject-matter of claim 1 differs from [Dx] in that:
  a) [first distinguishing feature, verbatim from claim]
  b) [next distinguishing feature, if any]

The subject-matter of claim 1 is therefore novel (Art. 54 EPC).

5.2  Technical Effect and Problem to be Solved

Use two sentences maximum:

The synergetic (if more than one differences found) technical effect of the distinguishing feature(s) a)- b) is [effect].

In a new paragraph add the objective technical problem to be solved by the differences.
The objective technical problem is how to [problem]. 

5.3  Solution

Use two to three sentences.

Explain how the characterising feature of claim 1 solves the objective technical problem.
No hints about the differences to the prior art. 
Refer to the description if useful.

5.4  Why is it inventive

Write one focused paragraph.

The use of xyz is well known in the prior art (see e.g. D[x]: paragraphs/ page
[xy] and lines [yz]). OR 

The problem [e.g. problem to be solved as mentioned above] is a standard problem in the respective prior art [relevant prior art] (see e.g. D[x]: paragraphs/ page
[xy] and lines [yz])

The problem with the solution of [Dx] is that... Furthermore
no ...... is discussed in [Dx].

Do not use sub-sections.

Do not repeat facts already stated.

Reference specific passages of prior-art documents where possible.

State what the skilled person starting from the closest prior art would or would not do and why.

OR

Even if the skilled person would replace the ..... of [Dx] with a ..... as known in
the prior art (see e.g. [Dy]: paragraphs/ page [xy] and lines [yz]) still the solution
of Dx is missing hints in order to adapt the needed technical features as
disclosed in the present application.


End with:

The same reasoning applies mutatis mutandis to [other independent claim(s)].

6  Further Relevant Information (Art. 82, 83, 84, 52, 53 EPC)

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