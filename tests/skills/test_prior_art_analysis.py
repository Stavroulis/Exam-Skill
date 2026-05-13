from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.prior_art_analysis import build_prompt, run

MOCK_RESPONSE = f"""# Analysis

Some analysis.

{_SUMMARY_BEGIN}
- Finding one
- Finding two
- Finding three
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "test.txt", "text": "Content."}],
        structured_documents=None,
        user_input={},
        prior_context="- Previous finding",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Previous finding" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "test.txt", "text": "Content."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "test.txt", "text": "Content."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_summary():
    with patch("skills.prior_art_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "test.txt", "text": "Content."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "Finding one" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]
