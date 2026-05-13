from unittest.mock import patch
from core.skill_utils import _SUMMARY_BEGIN, _SUMMARY_END
from skills.basic_analysis import build_prompt, run

MOCK_RESPONSE = f"""# Basic Technical Analysis

Some analysis.

===BEGIN_4P_SUMMARY===
Para 1. Para 2. Para 3. Para 4.
===END_4P_SUMMARY===

{_SUMMARY_BEGIN}
- Invention addresses sensor calibration
- Effect: reduced noise
- No prior art mentioned
{_SUMMARY_END}"""


def test_build_prompt_includes_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
        prior_context="- Previous finding",
    )
    assert "PRIOR ANALYSIS CONTEXT" in prompt
    assert "Previous finding" in prompt


def test_build_prompt_no_prior_context():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
    )
    assert "PRIOR ANALYSIS CONTEXT" not in prompt


def test_build_prompt_includes_summary_instruction():
    prompt = build_prompt(
        case_name="TEST",
        source_documents=[{"filename": "desc.txt", "text": "A device."}],
        structured_documents=None,
        user_input={},
    )
    assert _SUMMARY_BEGIN in prompt


def test_run_extracts_skill_summary():
    with patch("skills.basic_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "desc.txt", "text": "A device."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert "Invention addresses sensor calibration" in out["summary"]
    assert _SUMMARY_BEGIN not in out["result"]


def test_run_returns_dict():
    with patch("skills.basic_analysis.call_llm", return_value=MOCK_RESPONSE):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "desc.txt", "text": "A device."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )
    assert isinstance(out, dict)
    assert "result" in out
    assert "summary" in out
