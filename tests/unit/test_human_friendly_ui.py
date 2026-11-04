from decimal import Decimal
from pathlib import Path
import pytest

from src.app_helpers import (
    build_plain_language_findings,
    get_evidence_traceability_items,
    get_extracted_summary_fields,
    get_next_step_guidance,
)
from src.decision_engine import DecisionEngine
from src.models.schemas import DecisionEnum


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine(
        pr_path="sample_data/purchase-request.csv",
    )


def test_next_step_guidance():
    guide_app = get_next_step_guidance(DecisionEnum.APPROVE)
    assert guide_app["alert_type"] == "success"
    assert "Procurement Approval" in guide_app["title"]
    assert "Purchase Order has not yet been issued" in guide_app["note"]

    guide_rej = get_next_step_guidance(DecisionEnum.REJECT)
    assert guide_rej["alert_type"] == "error"
    assert "Quotation Rejected" in guide_rej["title"]
    assert "mandatory company rule" in guide_rej["message"]

    guide_rev = get_next_step_guidance(DecisionEnum.NEEDS_HUMAN_REVIEW)
    assert guide_rev["alert_type"] == "warning"
    assert "Human Review Required" in guide_rev["title"]
    assert "must inspect" in guide_rev["message"]


def test_plain_language_findings_approve(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-01.pdf"))
    assert rep.final_decision == DecisionEnum.APPROVE

    findings = build_plain_language_findings(rep)
    assert len(findings) == 10
    
    # Check names
    check_names = [f["Check"] for f in findings]
    assert "Unit price" in check_names
    assert "Quantity & unit" in check_names
    assert "Advance payment" in check_names
    assert "Delivery period" in check_names
    assert "Late-delivery penalty" in check_names
    assert "TIN & BIN registration" in check_names
    assert "VAT itemization (15%)" in check_names
    assert "Financial calculations" in check_names
    assert "Payment credit terms" in check_names
    assert "Quotation validity" in check_names

    # All checks should pass for an approved pack
    for f in findings:
        assert f["Result"] == "Passed", f"Check {f['Check']} failed: {f['Explanation']}"
        assert f["Status"] == "PASSED"


def test_plain_language_findings_reject_price(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-03.pdf"))
    assert rep.final_decision == DecisionEnum.REJECT

    findings = build_plain_language_findings(rep)
    price_check = next(f for f in findings if f["Check"] == "Unit price")
    assert price_check["Result"] == "Failed (Confirmed Violation)"
    assert price_check["Status"] == "FAILED"
    assert "exceed" in price_check["Explanation"].lower()


def test_plain_language_findings_reject_advance_payment(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-05.pdf"))
    assert rep.final_decision == DecisionEnum.REJECT

    findings = build_plain_language_findings(rep)
    adv_check = next(f for f in findings if f["Check"] == "Advance payment")
    assert adv_check["Result"] == "Failed (Confirmed Violation)"
    assert adv_check["Status"] == "FAILED"
    assert "20%" in adv_check["Explanation"]


def test_plain_language_findings_reject_missing_tin_bin(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-08.pdf"))
    assert rep.final_decision == DecisionEnum.REJECT

    findings = build_plain_language_findings(rep)
    tin_check = next(f for f in findings if f["Check"] == "TIN & BIN registration")
    assert tin_check["Result"] == "Failed (Confirmed Violation)"
    assert tin_check["Status"] == "FAILED"
    assert "missing" in tin_check["Explanation"].lower()


def test_plain_language_findings_review_band_price(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-04.pdf"))
    assert rep.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW

    findings = build_plain_language_findings(rep)
    price_check = next(f for f in findings if f["Check"] == "Unit price")
    assert price_check["Result"] == "Needs Review"
    assert price_check["Status"] == "REVIEW"


def test_plain_language_findings_review_quantity_variance(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-07.pdf"))
    assert rep.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW

    findings = build_plain_language_findings(rep)
    qty_check = next(f for f in findings if f["Check"] == "Quantity & unit")
    assert qty_check["Result"] == "Needs Review"
    assert qty_check["Status"] == "REVIEW"
    assert "differs" in qty_check["Explanation"].lower() or "5%" in qty_check["Explanation"]


def test_plain_language_findings_review_arithmetic_and_terms(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-09.pdf"))
    assert rep.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW

    findings = build_plain_language_findings(rep)
    math_check = next(f for f in findings if f["Check"] == "Financial calculations")
    assert math_check["Result"] == "Needs Review"
    assert math_check["Status"] == "REVIEW"

    terms_check = next(f for f in findings if f["Check"] == "Payment credit terms")
    assert terms_check["Result"] == "Needs Review"
    assert terms_check["Status"] == "REVIEW"


def test_get_extracted_summary_fields_complete(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-01.pdf"))
    fields = get_extracted_summary_fields(rep)

    assert "Supplier name" in fields
    assert "Padma" in fields["Supplier name"]
    assert "Quotation number" in fields
    assert "QT-2026-901" in fields["Quotation number"]
    assert "Item code & description" in fields
    assert "[A]" in fields["Item code & description"]
    assert "Quantity & unit" in fields
    assert "12,000" in fields["Quantity & unit"]
    assert "Unit price" in fields
    assert "472.00 BDT" in fields["Unit price"]
    assert "Subtotal" in fields
    assert "5,664,000.00 BDT" in fields["Subtotal"]
    assert "VAT" in fields
    assert "15%" in fields["VAT"]
    assert "Grand total" in fields
    assert "6,513,600.00 BDT" in fields["Grand total"]
    assert "Advance payment" in fields
    assert "10.0%" in fields["Advance payment"]
    assert "Credit / payment terms" in fields
    assert "45 days" in fields["Credit / payment terms"]
    assert "Delivery period" in fields
    assert "24 days" in fields["Delivery period"]
    assert "Late-delivery penalty" in fields
    assert "1.00% per week" in fields["Late-delivery penalty"]
    assert "TIN / BIN" in fields
    assert "TIN:" in fields["TIN / BIN"] and "BIN:" in fields["TIN / BIN"]


def test_get_extracted_summary_fields_missing_or_ambiguous(engine):
    rep_missing_tin = engine.verify_document(Path("sample_data/supplier-pack-08.pdf"))
    fields_8 = get_extracted_summary_fields(rep_missing_tin)
    assert "Missing" in fields_8["TIN / BIN"]

    rep_ambig_terms = engine.verify_document(Path("sample_data/supplier-pack-09.pdf"))
    fields_9 = get_extracted_summary_fields(rep_ambig_terms)
    assert "Ambiguous" in fields_9["Credit / payment terms"]

    rep_missing_penalty = engine.verify_document(Path("sample_data/supplier-pack-06.pdf"))
    fields_6 = get_extracted_summary_fields(rep_missing_penalty)
    assert "None" in fields_6["Late-delivery penalty"] or "omitted" in fields_6["Late-delivery penalty"]


def test_get_evidence_traceability_items(engine):
    rep = engine.verify_document(Path("sample_data/supplier-pack-01.pdf"))
    items = get_evidence_traceability_items(rep)
    assert len(items) >= 5

    fields_recorded = [it["Field"] for it in items]
    assert "Supplier Name" in fields_recorded
    assert "Quotation Number" in fields_recorded
    assert "Unit Price" in fields_recorded

    for it in items:
        assert "Field" in it
        assert "Extracted Value" in it
        assert "Verbatim PDF Quote" in it
        assert "Page Number" in it
        assert it["Page Number"] >= 1
        assert "Verified" in it
