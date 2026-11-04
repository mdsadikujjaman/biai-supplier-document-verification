from decimal import Decimal
from pathlib import Path
import pytest

from src.app_helpers import (
    get_all_decision_reasons,
    get_evidence_traceability_items,
    get_financial_discrepancies,
)
from src.decision_engine import DecisionEngine
from src.models.schemas import DecisionEnum


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine(pr_path="sample_data/purchase-request.csv")


# Test 12: Pack 09 financial discrepancy presentation
def test_12_pack_09_financial_discrepancy_presentation(engine):
    rep_09 = engine.verify_document(Path("sample_data/supplier-pack-09.pdf"))
    assert rep_09.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW

    # 1. Financial discrepancy table data
    math_discrepancies = get_financial_discrepancies(rep_09)
    assert len(math_discrepancies) >= 1

    line_disc = math_discrepancies[0]
    assert "Line" in line_disc["Component"]
    assert "322,000.00 BDT" in line_disc["Quoted Amount"]
    assert "320,000.00 BDT" in line_disc["Recalculated Amount"]
    assert "2,000.00 BDT" in line_disc["Difference"]
    assert "Explanation" in line_disc

    # 2. Aggregated decision reasons communicating both issues
    all_reasons = get_all_decision_reasons(rep_09)
    assert len(all_reasons) >= 2

    # Check reason 1: Quoted 322,000, recalculated 320,000, difference 2,000
    math_reason = next((r for r in all_reasons if "322,000" in r and "320,000" in r), None)
    assert math_reason is not None
    assert "2,000" in math_reason

    # Check reason 2: Ambiguous payment terms "30–90 days as agreed"
    terms_reason = next((r for r in all_reasons if "30–90" in r or "30-90" in r), None)
    assert terms_reason is not None
    assert "payment" in terms_reason.lower() or "terms" in terms_reason.lower()


# Test 13: Evidence verification versus interpretation status
def test_13_evidence_verification_vs_interpretation_status(engine):
    rep_09 = engine.verify_document(Path("sample_data/supplier-pack-09.pdf"))
    evidence_items = get_evidence_traceability_items(rep_09)

    # Must contain both Source Verified and Interpretation Status
    for it in evidence_items:
        assert "Field" in it
        assert "Verbatim PDF Quote" in it
        assert "Page Number" in it
        assert "Source Verified" in it
        assert "Interpretation Status" in it

    # Check payment terms in Pack 09: text is on page 1, but interpretation is AMBIGUOUS
    payment_terms_item = next(
        (it for it in evidence_items if "Payment Credit" in it["Field"]), None
    )
    assert payment_terms_item is not None
    assert payment_terms_item["Source Verified"] is True
    assert payment_terms_item["Interpretation Status"] == "AMBIGUOUS"

    # Check standard item in Pack 01: text is on page 1 and interpretation is EXTRACTED
    rep_01 = engine.verify_document(Path("sample_data/supplier-pack-01.pdf"))
    evidence_01 = get_evidence_traceability_items(rep_01)
    price_item = next((it for it in evidence_01 if it["Field"] == "Unit Price"), None)
    assert price_item is not None
    assert price_item["Source Verified"] is True
    assert price_item["Interpretation Status"] == "EXTRACTED"
