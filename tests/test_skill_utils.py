from core.skill_utils import extract_skill_summary, format_prior_context_block, SUMMARY_INSTRUCTION, _SUMMARY_BEGIN, _SUMMARY_END


def test_extract_summary_with_markers():
    raw = f"Full analysis text.\n\n{_SUMMARY_BEGIN}\n- Finding 1\n- Finding 2\n{_SUMMARY_END}"
    out = extract_skill_summary(raw)
    assert out["result"] == "Full analysis text."
    assert out["summary"] == "- Finding 1\n- Finding 2"


def test_extract_summary_no_markers():
    raw = "Full analysis text with no markers."
    out = extract_skill_summary(raw)
    assert out["result"] == "Full analysis text with no markers."
    assert out["summary"] == ""


def test_extract_summary_strips_whitespace():
    raw = f"Content.\n\n{_SUMMARY_BEGIN}\n\n  - Bullet  \n\n{_SUMMARY_END}\n"
    out = extract_skill_summary(raw)
    assert out["summary"] == "- Bullet"


def test_format_prior_context_block_with_context():
    block = format_prior_context_block("- finding 1\n- finding 2")
    assert "PRIOR ANALYSIS CONTEXT" in block
    assert "finding 1" in block


def test_format_prior_context_block_empty():
    assert format_prior_context_block("") == ""
    assert format_prior_context_block(None) == ""


def test_summary_instruction_contains_markers():
    assert _SUMMARY_BEGIN in SUMMARY_INSTRUCTION
    assert _SUMMARY_END in SUMMARY_INSTRUCTION
