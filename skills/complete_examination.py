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
