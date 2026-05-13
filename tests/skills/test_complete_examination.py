from unittest.mock import patch, MagicMock


def _make_mock_skill(name, summary):
    return {
        "name": name,
        "run": MagicMock(return_value={"result": f"Full output of {name}", "summary": summary}),
    }


def test_run_calls_all_seven_skills():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    skill_mocks = [
        _make_mock_skill(key, f"Summary of {key}")
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    for mock in skill_mocks:
        mock["run"].assert_called_once()


def test_run_returns_combined_report():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    skill_mocks = [
        _make_mock_skill(key, f"Summary of {key}")
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        out = run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    assert isinstance(out, dict)
    assert "result" in out
    assert "summary" in out
    for key, _ in _SKILLS_IN_ORDER:
        assert f"Full output of {key}" in out["result"]


def test_run_chains_prior_context():
    from skills.complete_examination import _SKILLS_IN_ORDER, run

    call_args_list = []

    def make_capturing_run(name, summary):
        def capturing_run(**kwargs):
            call_args_list.append((name, kwargs.get("prior_context", "")))
            return {"result": f"Full output of {name}", "summary": summary}
        return capturing_run

    skill_mocks = [
        {"name": key, "run": make_capturing_run(key, f"Summary of {key}")}
        for key, _ in _SKILLS_IN_ORDER
    ]

    with patch("skills.complete_examination._SKILLS_IN_ORDER",
               [(key, mock) for (key, _), mock in zip(_SKILLS_IN_ORDER, skill_mocks)]):
        run(
            case_name="TEST",
            source_documents=[{"filename": "claims.txt", "text": "Claim 1."}],
            structured_documents=None,
            user_input={},
            llm_config={"provider": "anthropic", "model": "test"},
        )

    # First skill gets empty prior_context
    assert call_args_list[0][1] == ""
    # Second skill gets non-empty prior_context containing first skill's summary
    assert "Summary of" in call_args_list[1][1]
    # Each subsequent skill gets more context than the previous
    for i in range(2, len(call_args_list)):
        assert len(call_args_list[i][1]) > len(call_args_list[i - 1][1])
