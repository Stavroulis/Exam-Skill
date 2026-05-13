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
