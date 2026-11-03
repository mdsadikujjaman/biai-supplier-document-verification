from decimal import Decimal
from pathlib import Path
import pytest
from src.decision_engine import DecisionEngine
from src.models.schemas import (
    ArithmeticAuditResult,
    ArithmeticDiscrepancy,
    DecisionEnum,
    ExtractedLineItem,
    ExtractedQuotation,
    ExtractedTerms,
    ExtractionStatus,
    ExtractionUncertainty,
    FieldProvenance,
    ItemComparisonResult,
    PRComparisonReport,
    RuleCategory,
    RuleCheckResult,
    RuleStatus,
)


def test_synthesize_decision_confirmed_rejection_precedence():
    engine = DecisionEngine()

    reject_rule = RuleCheckResult(
        rule_id="REJECT_RULE_1",
        rule_name="Unit price exceeds PR maximum by > 3%",
        category=RuleCategory.REJECT,
        status=RuleStatus.FAIL,
        triggered=True,
        is_confirmed=True,
        explanation="Price exceeds ceiling",
    )
    review_rule = RuleCheckResult(
        rule_id="REVIEW_RULE_5",
        rule_name="VAT is not shown separately at 15%",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.FAIL,
        triggered=True,
        is_confirmed=True,
        explanation="VAT bundled",
    )

    decision, reason, confirmed = engine._synthesize_decision(
        all_rules=[reject_rule, review_rule],
        extraction_uncertainties=[],
        math_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114", matched_items=[
            ItemComparisonResult(
                item_code="A",
                pr_description="Fabric",
                quoted_description="Fabric",
                description_match=True,
                pr_unit="metre",
                quoted_unit="metre",
                unit_match=True,
                requested_quantity=Decimal("50000"),
                quoted_quantity=Decimal("50000"),
                quantity_difference=Decimal("0"),
                quantity_variance_pct=Decimal("0"),
                quantity_within_tolerance=True,
                max_unit_price=Decimal("45.00"),
                quoted_unit_price=Decimal("50.00"),
                price_difference=Decimal("5.00"),
                price_variance_pct=Decimal("11.11"),
                price_rejection_ceiling=Decimal("46.35"),
                price_is_below_or_equal_max=False,
                price_is_within_review_band=False,
                price_exceeds_rejection_ceiling=True,
                evidence_quote="Item A",
                is_valid_match=True,
            )
        ]),
        is_readable=True,
    )

    assert decision == DecisionEnum.REJECT
    assert confirmed is True
    assert "Confirmed violation" in reason


def test_synthesize_decision_review_condition():
    engine = DecisionEngine()

    review_rule = RuleCheckResult(
        rule_id="REVIEW_RULE_1",
        rule_name="Unit price above maximum by <= 3%",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.FAIL,
        triggered=True,
        is_confirmed=True,
        explanation="Price in marginal review band",
    )

    decision, reason, confirmed = engine._synthesize_decision(
        all_rules=[review_rule],
        extraction_uncertainties=[],
        math_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114", matched_items=[
            ItemComparisonResult(
                item_code="D",
                pr_description="Thread",
                quoted_description="Thread",
                description_match=True,
                pr_unit="cone",
                quoted_unit="cone",
                unit_match=True,
                requested_quantity=Decimal("50000"),
                quoted_quantity=Decimal("50000"),
                quantity_difference=Decimal("0"),
                quantity_variance_pct=Decimal("0"),
                quantity_within_tolerance=True,
                max_unit_price=Decimal("6.50"),
                quoted_unit_price=Decimal("6.65"),
                price_difference=Decimal("0.15"),
                price_variance_pct=Decimal("2.31"),
                price_rejection_ceiling=Decimal("6.695"),
                price_is_below_or_equal_max=False,
                price_is_within_review_band=True,
                price_exceeds_rejection_ceiling=False,
                evidence_quote="Item D",
                is_valid_match=True,
            )
        ]),
        is_readable=True,
    )

    assert decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert confirmed is False
    assert "Review required" in reason


def test_synthesize_decision_extraction_uncertainty():
    engine = DecisionEngine()

    unc = ExtractionUncertainty(
        field_name="credit_days",
        issue_type="AMBIGUOUS",
        details="Payment terms stated as 30-90 days as agreed",
    )

    decision, reason, confirmed = engine._synthesize_decision(
        all_rules=[],
        extraction_uncertainties=[unc],
        math_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114", matched_items=[]),
        is_readable=True,
    )

    assert decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert "Extraction uncertainty" in reason


def test_synthesize_decision_unreadable_document():
    engine = DecisionEngine()

    decision, reason, confirmed = engine._synthesize_decision(
        all_rules=[],
        extraction_uncertainties=[],
        math_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114", matched_items=[]),
        is_readable=False,
    )

    assert decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert "unreadable" in reason.lower()


def test_synthesize_decision_approve():
    engine = DecisionEngine()

    pass_rule = RuleCheckResult(
        rule_id="REJECT_RULE_1",
        rule_name="Price check",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
    )

    decision, reason, confirmed = engine._synthesize_decision(
        all_rules=[pass_rule],
        extraction_uncertainties=[],
        math_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114", matched_items=[
            ItemComparisonResult(
                item_code="A",
                pr_description="Cotton twill fabric, 280 gsm",
                quoted_description="Cotton twill fabric, 280 gsm",
                description_match=True,
                pr_unit="metre",
                quoted_unit="metre",
                unit_match=True,
                requested_quantity=Decimal("12000"),
                quoted_quantity=Decimal("12000"),
                quantity_difference=Decimal("0"),
                quantity_variance_pct=Decimal("0"),
                quantity_within_tolerance=True,
                max_unit_price=Decimal("480.00"),
                quoted_unit_price=Decimal("472.00"),
                price_difference=Decimal("-8.00"),
                price_variance_pct=Decimal("-1.67"),
                price_rejection_ceiling=Decimal("494.40"),
                price_is_below_or_equal_max=True,
                price_is_within_review_band=False,
                price_exceeds_rejection_ceiling=False,
                evidence_quote="Item A",
                is_valid_match=True,
            )
        ]),
        is_readable=True,
    )

    assert decision == DecisionEnum.APPROVE
    assert confirmed is False
    assert "All company rules passed" in reason


def test_verify_nonexistent_file():
    engine = DecisionEngine()
    report = engine.verify_document("sample_data/non_existent_file.pdf")

    assert report.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert "File not found" in report.primary_reason
    assert report.document_hash == "FILE_NOT_FOUND"


def test_check_essential_information():
    engine = DecisionEngine()
    uncertainties = []

    # Quotation missing supplier name, quotation number, total amount, and line item details
    bad_quotation = ExtractedQuotation(
        supplier_name=FieldProvenance[str].missing(),
        quotation_no=FieldProvenance[str].missing(),
        quotation_date=FieldProvenance[str].missing(),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].missing(),
                description=FieldProvenance[str].missing(),
                quantity=FieldProvenance[Decimal].missing(),
                unit=FieldProvenance[str].missing(),
                unit_price=FieldProvenance[Decimal].missing(),
            )
        ],
        total_amount=FieldProvenance[Decimal].missing(),
        terms=ExtractedTerms(),
    )

    engine._check_essential_information(bad_quotation, uncertainties)
    assert len(uncertainties) == 4
    field_names = [u.field_name for u in uncertainties]
    assert "supplier_name" in field_names
    assert "quotation_no" in field_names
    assert "line_items" in field_names
    assert "total_amount" in field_names

