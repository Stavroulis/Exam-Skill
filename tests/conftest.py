import pytest

MOCK_LLM_RESPONSE_WITH_SUMMARY = """Some analysis content here.

===BEGIN_SKILL_SUMMARY===
- Key finding one
- Key finding two
- Key finding three
===END_SKILL_SUMMARY==="""

MOCK_LLM_RESPONSE_NO_SUMMARY = "Some analysis content with no summary markers."

MINIMAL_SOURCE_DOCS = [{"filename": "claims.txt", "text": "Claim 1: A device comprising a sensor."}]

BASE_LLM_CONFIG = {"provider": "anthropic", "model": "claude-sonnet-4-6"}
