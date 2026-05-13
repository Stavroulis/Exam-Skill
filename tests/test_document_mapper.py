import pytest
from core.document_mapper import classify_filename, role_to_structure_type, parse_esop_prior_art


# --- classify_filename: new convention ---

def test_new_convention_clms():
    assert classify_filename("2026-05-13_CLMS_EP21760408.pdf") == "claims_as_filed"

def test_new_convention_desc():
    assert classify_filename("2026-05-13_DESC_EP21760408.pdf") == "description"

def test_new_convention_abex():
    assert classify_filename("2026-05-13_ABEX_EP21760408.pdf") == "amended_claims"

def test_new_convention_repl():
    assert classify_filename("2026-05-13_REPL_EP21760408.pdf") == "reply"

def test_new_convention_esop():
    assert classify_filename("2026-05-13_ESOP_EP21760408.pdf") == "esop"

def test_new_convention_case_insensitive_extension():
    assert classify_filename("2026-05-13_CLMS_EP123.PDF") == "claims_as_filed"

# --- classify_filename: legacy convention ---

def test_legacy_claims():
    assert classify_filename("claims.pdf") == "claims_as_filed"

def test_legacy_claims_as_filed():
    assert classify_filename("claims_as_filed.pdf") == "claims_as_filed"

def test_legacy_description():
    assert classify_filename("description.pdf") == "description"

def test_legacy_amended_claims():
    assert classify_filename("amended_claims.pdf") == "amended_claims"

def test_legacy_reply():
    assert classify_filename("reply.pdf") == "reply"

def test_legacy_esop():
    assert classify_filename("esop.pdf") == "esop"

def test_legacy_d1():
    assert classify_filename("D1.pdf") == "D1"

def test_legacy_d2():
    assert classify_filename("D2.pdf") == "D2"

def test_legacy_d10():
    assert classify_filename("D10.pdf") == "D10"

# --- classify_filename: unclassified ---

def test_unclassified_title_name():
    assert classify_filename("Method for real-time sensor calibration.pdf") is None

def test_unclassified_generic():
    assert classify_filename("some_other_file.pdf") is None


# --- role_to_structure_type ---

def test_role_claims_as_filed():
    assert role_to_structure_type("claims_as_filed") == "claims_as_filed"

def test_role_description():
    assert role_to_structure_type("description") == "description_as_filed"

def test_role_amended_claims():
    assert role_to_structure_type("amended_claims") == "amended_claims"

def test_role_reply():
    assert role_to_structure_type("reply") == "attorney_response"

def test_role_esop():
    assert role_to_structure_type("esop") == "epo_communication"

def test_role_d1():
    assert role_to_structure_type("D1") == "prior_art"

def test_role_d2():
    assert role_to_structure_type("D2") == "prior_art"

def test_role_unknown():
    assert role_to_structure_type("something_else") == "unknown"


# --- parse_esop_prior_art ---

ESOP_SAMPLE = """
Some introductory text.

PRIOR ART DOCUMENTS

D1 EP 2 490 004 A1 (UNIV TOHOKU [JP]; TOYOTA CHUO
KENKYUSHO KK [JP] ET AL.) 22 August 2012 (2012-08-22)
D2 US 2017/199090 A1 (ANAN HIROO [JP] ET AL) 13 July 2017

(2017-07-13)

D3 WO 02/44655 A1 (NANODEVICES INC [US]) 6 June 2002

(2002-06-06)

Some text after the citations.
"""

def test_parse_esop_returns_three_entries():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert len(result) == 3

def test_parse_esop_labels():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert result[0]["label"] == "D1"
    assert result[1]["label"] == "D2"
    assert result[2]["label"] == "D3"

def test_parse_esop_pub_numbers():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert "EP" in result[0]["pub_number"]
    assert "US" in result[1]["pub_number"]
    assert "WO" in result[2]["pub_number"]

def test_parse_esop_dates():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert result[0]["date"] == "2012-08-22"
    assert result[1]["date"] == "2017-07-13"
    assert result[2]["date"] == "2002-06-06"

def test_parse_esop_applicant_d1():
    result = parse_esop_prior_art(ESOP_SAMPLE)
    assert "TOHOKU" in result[0]["applicant"]

def test_parse_esop_no_section_returns_empty():
    result = parse_esop_prior_art("This document has no prior art section.")
    assert result == []

def test_parse_esop_empty_string():
    assert parse_esop_prior_art("") == []
