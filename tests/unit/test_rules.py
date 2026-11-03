from decimal import Decimal
import pytest
from src.config import settings
from src.models.schemas import (
    ArithmeticAuditResult,
    ArithmeticDiscrepancy,
    ExtractedLineItem,
    ExtractedQuotation,
    ExtractedTerms,
    ExtractionStatus,
    FieldProvenance,
    ItemComparisonResult,
    PRComparisonReport,
    RuleCategory,
    RuleCheckResult,
    RuleStatus,
)
from src.rules import (
    CompanyRuleEngine,
    evaluate_matching_integrity,
    evaluate_reject_rule_1_price,
    evaluate_reject_rule_2_advance,
    evaluate_reject_rule_3_penalty,
    evaluate_reject_rule_4_tin_bin,
    evaluate_reject_rule_5_delivery_max,
    evaluate_review_rule_1_marginal_price,
    evaluate_review_rule_2_quantity_variance,
    evaluate_review_rule_3_payment_terms,
    evaluate_review_rule_4_delivery_borderline,
    evaluate_review_rule_5_vat_separation,
    evaluate_review_rule_6_arithmetic_errors,
    evaluate_review_rule_7_quotation_validity,
)


def make_dummy_quotation(
    advance_pct=Decimal("10.0"),
    has_penalty=True,
    penalty_pct=Decimal("1.0"),
    tin="123456789012",
    bin_no="1234567890123",
    delivery_days=24,
    credit_days=30,
    payment_unclear=False,
    vat_separated=True,
    vat_pct=Decimal("15.0"),
    validity_days=30,
) -> ExtractedQuotation:
    return ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier A", "Supplier A", 1),
        quotation_no=FieldProvenance[str].extracted("Q-001", "Q-001", 1),
        quotation_date=FieldProvenance[str].extracted("2026-11-01", "2026-11-01", 1),
        supplier_tin=FieldProvenance[str].extracted(tin, tin, 1) if tin else FieldProvenance[str].missing(),
        supplier_bin=FieldProvenance[str].extracted(bin_no, bin_no, 1) if bin_no else FieldProvenance[str].missing(),
        registration_raw_quote=FieldProvenance[str].extracted("TIN / BIN quote", "TIN / BIN quote", 1),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("A", "A", 1),
                description=FieldProvenance[str].extracted("Cotton twill fabric, 280 gsm", "Cotton twill fabric, 280 gsm", 1),
                quantity=FieldProvenance[Decimal].extracted(Decimal("12000"), "12,000", 1),
                unit=FieldProvenance[str].extracted("metre", "metre", 1),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("472.00"), "472.00", 1),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("5664000.00"), "5,664,000.00", 1),
            )
        ],
        subtotal=FieldProvenance[Decimal].extracted(Decimal("5664000.00"), "5,664,000.00", 1),
        vat_percentage=FieldProvenance[Decimal].extracted(vat_pct, f"{vat_pct}%", 1),
        vat_amount=FieldProvenance[Decimal].extracted(Decimal("849600.00"), "849,600.00", 1),
        vat_shown_separately=FieldProvenance[bool].extracted(vat_separated, "15% VAT", 1),
        total_amount=FieldProvenance[Decimal].extracted(Decimal("6513600.00"), "6,513,600.00", 1),
        terms=ExtractedTerms(
            advance_payment_percentage=FieldProvenance[Decimal].extracted(advance_pct, f"{advance_pct}%", 1),
            credit_days_after_delivery=FieldProvenance[int].extracted(credit_days, f"{credit_days} days", 1)
            if credit_days is not None
            else FieldProvenance[int].missing(),
            payment_terms_unclear=FieldProvenance[bool].extracted(payment_unclear, "unclear", 1),
            payment_terms_text=FieldProvenance[str].extracted("Payment within 30 days", "Payment within 30 days", 1),
            delivery_timeline_days=FieldProvenance[int].extracted(delivery_days, f"{delivery_days} days", 1),
            delivery_terms_text=FieldProvenance[str].extracted(f"Delivery: {delivery_days} days", f"{delivery_days} days", 1),
            has_late_delivery_penalty=FieldProvenance[bool].extracted(has_penalty, "Penalty clause", 1),
            late_penalty_percentage_per_week=FieldProvenance[Decimal].extracted(penalty_pct, f"{penalty_pct}%", 1)
            if penalty_pct is not None
            else FieldProvenance[Decimal].missing(),
            penalty_terms_text=FieldProvenance[str].extracted("Penalty quote", "Penalty quote", 1),
            quotation_validity_days=FieldProvenance[int].extracted(validity_days, f"{validity_days} days", 1),
            validity_terms_text=FieldProvenance[str].extracted(f"Validity: {validity_days} days", f"{validity_days} days", 1),
        ),
    )


def make_dummy_pr_comparison(
    item_code="A",
    quoted_price=Decimal("472.00"),
    max_price=Decimal("480.00"),
    quoted_qty=Decimal("12000"),
    requested_qty=Decimal("12000"),
    unit_match=True,
    desc_match=True,
) -> PRComparisonReport:
    price_var_pct = ((quoted_price - max_price) / max_price) * Decimal("100")
    qty_var_pct = ((quoted_qty - requested_qty) / requested_qty) * Decimal("100")
    ceiling = max_price * Decimal("1.03")

    item_res = ItemComparisonResult(
        item_code=item_code,
        pr_description="100% Cotton Fabric",
        quoted_description="100% Cotton Fabric",
        description_match=desc_match,
        pr_unit="metre",
        quoted_unit="metre",
        unit_match=unit_match,
        requested_quantity=requested_qty,
        quoted_quantity=quoted_qty,
        quantity_difference=quoted_qty - requested_qty,
        quantity_variance_pct=qty_var_pct,
        quantity_within_tolerance=abs(qty_var_pct) <= Decimal("5.0"),
        max_unit_price=max_price,
        quoted_unit_price=quoted_price,
        price_difference=quoted_price - max_price,
        price_variance_pct=price_var_pct,
        price_rejection_ceiling=ceiling,
        price_is_below_or_equal_max=quoted_price <= max_price,
        price_is_within_review_band=max_price < quoted_price <= ceiling,
        price_exceeds_rejection_ceiling=quoted_price > ceiling,
        evidence_quote=f"Item {item_code}",
        is_valid_match=True,
    )

    return PRComparisonReport(
        pr_number="PR-2026-114",
        matched_items=[item_res],
        unknown_item_codes=[],
        unmatched_pr_items=[],
        duplicate_item_codes=[],
        has_unit_mismatch=not unit_match,
        has_description_mismatch=not desc_match,
    )


# ==============================================================================
# REJECT RULE TESTS
# ==============================================================================


def test_reject_rule_1_price_thresholds():
    # Max price: 210.00. Ceiling: 210 * 1.03 = 216.30

    # 1. Price <= max: 200.00 -> PASS
    comp_pass = make_dummy_pr_comparison(quoted_price=Decimal("200.00"), max_price=Decimal("210.00"))
    res = evaluate_reject_rule_1_price(comp_pass)
    assert res.status == RuleStatus.PASS
    assert not res.triggered

    # 2. Price within marginal review band: 215.00 (+2.38% <= +3%) -> PASS for Reject Rule 1
    comp_review = make_dummy_pr_comparison(quoted_price=Decimal("215.00"), max_price=Decimal("210.00"))
    res = evaluate_reject_rule_1_price(comp_review)
    assert res.status == RuleStatus.PASS
    assert not res.triggered

    # 3. Exact boundary: 216.30 (+3.00%) -> PASS (not > 3%)
    comp_boundary = make_dummy_pr_comparison(quoted_price=Decimal("216.30"), max_price=Decimal("210.00"))
    res = evaluate_reject_rule_1_price(comp_boundary)
    assert res.status == RuleStatus.PASS

    # 4. Price > 3% ceiling: 229.00 (+9.05%) -> FAIL, confirmed
    comp_fail = make_dummy_pr_comparison(quoted_price=Decimal("229.00"), max_price=Decimal("210.00"))
    res = evaluate_reject_rule_1_price(comp_fail)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert res.is_confirmed
    assert "229.00" in res.actual_value


def test_reject_rule_2_advance_payment():
    # Policy: max 20%

    # 1. 10% advance -> PASS
    q_pass = make_dummy_quotation(advance_pct=Decimal("10.0"))
    res = evaluate_reject_rule_2_advance(q_pass)
    assert res.status == RuleStatus.PASS
    assert not res.triggered

    # 2. Exactly 20% advance -> PASS (boundary condition)
    q_boundary = make_dummy_quotation(advance_pct=Decimal("20.0"))
    res = evaluate_reject_rule_2_advance(q_boundary)
    assert res.status == RuleStatus.PASS

    # 3. 20.1% advance -> FAIL
    q_boundary_fail = make_dummy_quotation(advance_pct=Decimal("20.1"))
    res = evaluate_reject_rule_2_advance(q_boundary_fail)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    # 4. 40% advance -> FAIL, confirmed
    q_fail = make_dummy_quotation(advance_pct=Decimal("40.0"))
    res = evaluate_reject_rule_2_advance(q_fail)
    assert res.status == RuleStatus.FAIL
    assert res.is_confirmed
    assert res.actual_value == "40.0%"


def test_reject_rule_3_late_delivery_penalty():
    # 1. Valid penalty >= 0.5% (e.g. 1.0%/week) -> PASS
    q_pass = make_dummy_quotation(has_penalty=True, penalty_pct=Decimal("1.0"))
    res = evaluate_reject_rule_3_penalty(q_pass)
    assert res.status == RuleStatus.PASS
    assert not res.triggered

    # 2. Boundary: exactly 0.5%/week -> PASS
    q_boundary = make_dummy_quotation(has_penalty=True, penalty_pct=Decimal("0.50"))
    res = evaluate_reject_rule_3_penalty(q_boundary)
    assert res.status == RuleStatus.PASS

    # 3. Insufficient rate: 0.49%/week -> FAIL
    q_insufficient = make_dummy_quotation(has_penalty=True, penalty_pct=Decimal("0.49"))
    res = evaluate_reject_rule_3_penalty(q_insufficient)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert "0.49% per week" in res.actual_value

    # 4. Penalty clause missing entirely -> FAIL, confirmed
    q_missing = make_dummy_quotation(has_penalty=False, penalty_pct=None)
    q_missing.terms.has_late_delivery_penalty.status = ExtractionStatus.MISSING
    res = evaluate_reject_rule_3_penalty(q_missing)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert res.is_confirmed

    # 5. Unreadable document guard -> UNCERTAIN, NOT confirmed rejection
    q_unreadable = make_dummy_quotation()
    q_unreadable.terms.has_late_delivery_penalty.status = ExtractionStatus.UNREADABLE
    res = evaluate_reject_rule_3_penalty(q_unreadable)
    assert res.status == RuleStatus.UNCERTAIN
    assert not res.triggered
    assert not res.is_confirmed


def test_reject_rule_4_tin_bin():
    # 1. Both TIN and BIN present -> PASS
    q_pass = make_dummy_quotation(tin="123456789012", bin_no="1234567890123")
    res = evaluate_reject_rule_4_tin_bin(q_pass)
    assert res.status == RuleStatus.PASS
    assert not res.triggered

    # 2. TIN missing -> FAIL
    q_tin_missing = make_dummy_quotation(tin=None, bin_no="1234567890123")
    res = evaluate_reject_rule_4_tin_bin(q_tin_missing)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert "TIN" in res.actual_value

    # 3. BIN missing -> FAIL
    q_bin_missing = make_dummy_quotation(tin="123456789012", bin_no=None)
    res = evaluate_reject_rule_4_tin_bin(q_bin_missing)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert "BIN" in res.actual_value

    # 4. Both missing -> FAIL
    q_both_missing = make_dummy_quotation(tin=None, bin_no=None)
    res = evaluate_reject_rule_4_tin_bin(q_both_missing)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert res.is_confirmed

    # 5. Unreadable document guard -> UNCERTAIN, never silent rejection
    q_unreadable = make_dummy_quotation()
    q_unreadable.supplier_tin.status = ExtractionStatus.UNREADABLE
    res = evaluate_reject_rule_4_tin_bin(q_unreadable)
    assert res.status == RuleStatus.UNCERTAIN
    assert not res.triggered


def test_reject_rule_5_delivery_timeline():
    # 1. <= 45 days (e.g. 24 days, 45 days) -> PASS
    q_pass = make_dummy_quotation(delivery_days=24)
    res = evaluate_reject_rule_5_delivery_max(q_pass)
    assert res.status == RuleStatus.PASS

    q_boundary = make_dummy_quotation(delivery_days=45)
    res = evaluate_reject_rule_5_delivery_max(q_boundary)
    assert res.status == RuleStatus.PASS

    # 2. 46 days -> FAIL
    q_46 = make_dummy_quotation(delivery_days=46)
    res = evaluate_reject_rule_5_delivery_max(q_46)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    # 3. 60 days -> FAIL, confirmed
    q_60 = make_dummy_quotation(delivery_days=60)
    res = evaluate_reject_rule_5_delivery_max(q_60)
    assert res.status == RuleStatus.FAIL
    assert res.is_confirmed
    assert "60 days" in res.actual_value


# ==============================================================================
# HUMAN REVIEW RULE TESTS
# ==============================================================================


def test_review_rule_1_marginal_price():
    # Max price: 6.50. Ceiling: 6.50 * 1.03 = 6.695

    # 1. Price <= max (6.40) -> PASS
    comp_below = make_dummy_pr_comparison(quoted_price=Decimal("6.40"), max_price=Decimal("6.50"))
    res = evaluate_review_rule_1_marginal_price(comp_below)
    assert res.status == RuleStatus.PASS

    # 2. Marginal review bracket: 6.65 (+2.31%) -> FAIL (triggers review)
    comp_marginal = make_dummy_pr_comparison(quoted_price=Decimal("6.65"), max_price=Decimal("6.50"))
    res = evaluate_review_rule_1_marginal_price(comp_marginal)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    # 3. Price > 3% ceiling (6.75) -> Handled by Reject Rule 1, Review Rule 1 is PASS
    comp_reject = make_dummy_pr_comparison(quoted_price=Decimal("6.75"), max_price=Decimal("6.50"))
    res = evaluate_review_rule_1_marginal_price(comp_reject)
    assert res.status == RuleStatus.PASS


def test_review_rule_2_quantity_variance():
    # Requested: 20,000. Tolerance: ±5% (19,000 to 21,000)

    # 1. Exactly requested (20,000) -> PASS
    comp_exact = make_dummy_pr_comparison(quoted_qty=Decimal("20000"), requested_qty=Decimal("20000"))
    res = evaluate_review_rule_2_quantity_variance(comp_exact)
    assert res.status == RuleStatus.PASS

    # 2. Within ±5% (19,500, -2.5%) -> PASS
    comp_within = make_dummy_pr_comparison(quoted_qty=Decimal("19500"), requested_qty=Decimal("20000"))
    res = evaluate_review_rule_2_quantity_variance(comp_within)
    assert res.status == RuleStatus.PASS

    # 3. Outside tolerance: 16,500 (-17.50%) -> FAIL (triggers review)
    comp_outside = make_dummy_pr_comparison(quoted_qty=Decimal("16500"), requested_qty=Decimal("20000"))
    res = evaluate_review_rule_2_quantity_variance(comp_outside)
    assert res.status == RuleStatus.FAIL
    assert res.triggered
    assert "-17.50%" in res.actual_value


def test_review_rule_3_payment_terms():
    # 1. 30 days credit -> PASS
    q_pass = make_dummy_quotation(credit_days=30, payment_unclear=False)
    res = evaluate_review_rule_3_payment_terms(q_pass)
    assert res.status == RuleStatus.PASS

    # 2. Ambiguous terms (unclear flag) -> FAIL
    q_unclear = make_dummy_quotation(credit_days=None, payment_unclear=True)
    res = evaluate_review_rule_3_payment_terms(q_unclear)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    # 3. Outside 30-60 days (e.g. 15 days or 90 days) -> FAIL
    q_15 = make_dummy_quotation(credit_days=15)
    res = evaluate_review_rule_3_payment_terms(q_15)
    assert res.status == RuleStatus.FAIL

    q_90 = make_dummy_quotation(credit_days=90)
    res = evaluate_review_rule_3_payment_terms(q_90)
    assert res.status == RuleStatus.FAIL


def test_review_rule_4_delivery_borderline():
    # Review window: 31 to 45 days

    # 1. <= 30 days (fast track) -> PASS
    q_fast = make_dummy_quotation(delivery_days=24)
    res = evaluate_review_rule_4_delivery_borderline(q_fast)
    assert res.status == RuleStatus.PASS

    # 2. In 31 to 45 days (e.g. 35 days, 45 days) -> FAIL (triggers review)
    q_borderline = make_dummy_quotation(delivery_days=35)
    res = evaluate_review_rule_4_delivery_borderline(q_borderline)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    q_45 = make_dummy_quotation(delivery_days=45)
    res = evaluate_review_rule_4_delivery_borderline(q_45)
    assert res.status == RuleStatus.FAIL


def test_review_rule_5_vat_separation():
    # 1. 15% VAT shown separately -> PASS
    q_pass = make_dummy_quotation(vat_separated=True, vat_pct=Decimal("15.0"))
    math_pass = ArithmeticAuditResult(vat_shown_separately=True)
    res = evaluate_review_rule_5_vat_separation(q_pass, math_pass)
    assert res.status == RuleStatus.PASS

    # 2. VAT bundled / inclusive -> FAIL
    q_bundled = make_dummy_quotation(vat_separated=False)
    math_bundled = ArithmeticAuditResult(vat_shown_separately=False)
    res = evaluate_review_rule_5_vat_separation(q_bundled, math_bundled)
    assert res.status == RuleStatus.FAIL
    assert res.triggered

    # 3. Non-standard VAT (e.g. 10%) -> FAIL
    q_diff_vat = make_dummy_quotation(vat_separated=True, vat_pct=Decimal("10.0"))
    res = evaluate_review_rule_5_vat_separation(q_diff_vat, math_pass)
    assert res.status == RuleStatus.FAIL


def test_review_rule_6_arithmetic_errors():
    # 1. Clean math -> PASS
    math_clean = ArithmeticAuditResult(
        line_calculations_match=True,
        subtotal_matches_lines=True,
        vat_matches_subtotal_15pct=True,
        total_matches_sum=True,
        vat_shown_separately=True,
    )
    res = evaluate_review_rule_6_arithmetic_errors(math_clean)
    assert res.status == RuleStatus.PASS

    # 2. Discrepancy detected -> FAIL
    math_bad = ArithmeticAuditResult(
        line_calculations_match=True,
        subtotal_matches_lines=False,
        vat_matches_subtotal_15pct=True,
        total_matches_sum=True,
        vat_shown_separately=True,
        discrepancies=[
            ArithmeticDiscrepancy(
                component="SUBTOTAL",
                expected_value=Decimal("320000"),
                quoted_value=Decimal("322000"),
                discrepancy_amount=Decimal("2000"),
                evidence_quote="Subtotal: 322,000",
                details="Recalculated subtotal does not match quoted subtotal",
            )
        ],
        discrepancy_details=["Subtotal discrepancy: 2,000 BDT"],
    )
    res = evaluate_review_rule_6_arithmetic_errors(math_bad)
    assert res.status == RuleStatus.FAIL
    assert res.triggered


def test_review_rule_7_quotation_validity():
    # Policy: >= 30 days

    # 1. >= 30 days -> PASS
    q_30 = make_dummy_quotation(validity_days=30)
    res = evaluate_review_rule_7_quotation_validity(q_30)
    assert res.status == RuleStatus.PASS

    q_60 = make_dummy_quotation(validity_days=60)
    res = evaluate_review_rule_7_quotation_validity(q_60)
    assert res.status == RuleStatus.PASS

    # 2. < 30 days (e.g. 15 days) -> FAIL
    q_15 = make_dummy_quotation(validity_days=15)
    res = evaluate_review_rule_7_quotation_validity(q_15)
    assert res.status == RuleStatus.FAIL
    assert res.triggered


def test_matching_integrity_checks():
    # 1. Normal match -> returns None (no error)
    comp_normal = make_dummy_pr_comparison()
    assert evaluate_matching_integrity(comp_normal) is None

    # 2. Unknown item code -> FAIL
    comp_unknown = make_dummy_pr_comparison()
    comp_unknown.unknown_item_codes = ["ITEM-Z"]
    res = evaluate_matching_integrity(comp_unknown)
    assert res is not None
    assert res.status == RuleStatus.FAIL
    assert "ITEM-Z" in res.explanation

    # 3. Duplicate item code -> FAIL
    comp_dup = make_dummy_pr_comparison()
    comp_dup.duplicate_item_codes = ["A"]
    res = evaluate_matching_integrity(comp_dup)
    assert res is not None
    assert res.status == RuleStatus.FAIL
    assert "duplicate" in res.rule_name.lower()

    # 4. Unit mismatch -> FAIL
    comp_unit = make_dummy_pr_comparison(unit_match=False)
    res = evaluate_matching_integrity(comp_unit)
    assert res is not None
    assert res.status == RuleStatus.FAIL

    # 5. Description mismatch -> FAIL
    comp_desc = make_dummy_pr_comparison(desc_match=False)
    res = evaluate_matching_integrity(comp_desc)
    assert res is not None
    assert res.status == RuleStatus.FAIL


def test_company_rule_engine_evaluate_all():
    engine = CompanyRuleEngine()
    quotation = make_dummy_quotation()
    pr_comparison = make_dummy_pr_comparison()
    math_audit = ArithmeticAuditResult()

    results = engine.evaluate_all(quotation, pr_comparison, math_audit)
    # Should evaluate integrity + 5 reject rules + 7 review rules = 12 rules (since integrity passes cleanly)
    assert len(results) == 12
    # All should pass for clean dummy quotation
    for r in results:
        assert r.status == RuleStatus.PASS
        assert not r.triggered

