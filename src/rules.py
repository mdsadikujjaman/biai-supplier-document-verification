from decimal import Decimal
import logging
from typing import List, Optional, Tuple
from src.config import settings
from src.models.schemas import (
    ArithmeticAuditResult,
    ExtractedQuotation,
    ExtractionStatus,
    ExtractionUncertainty,
    PRComparisonReport,
    RuleCategory,
    RuleCheckResult,
    RuleStatus,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# REJECT RULES (1 to 5)
# ==============================================================================


def evaluate_reject_rule_1_price(pr_comparison: PRComparisonReport) -> RuleCheckResult:
    """Reject Rule 1: Unit price is more than 3% above the maximum unit price in PR."""
    for item in pr_comparison.matched_items:
        if item.price_exceeds_rejection_ceiling:
            return RuleCheckResult(
                rule_id="REJECT_RULE_1",
                rule_name="Unit price exceeds PR maximum by > 3%",
                category=RuleCategory.REJECT,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=(
                    f"Quoted unit price ({item.quoted_unit_price:,.2f} BDT) for item {item.item_code} "
                    f"is {item.price_variance_pct:+,.2f}% above maximum price ({item.max_unit_price:,.2f} BDT), "
                    f"exceeding the +3% ceiling ({item.price_rejection_ceiling:,.2f} BDT)."
                ),
                actual_value=f"{item.quoted_unit_price} BDT ({item.price_variance_pct:+,.2f}%)",
                expected_condition=f"<= {item.price_rejection_ceiling} BDT (+3% of max)",
                evidence_quote=item.evidence_quote,
                page_number=1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REJECT_RULE_1",
        rule_name="Unit price exceeds PR maximum by > 3%",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
        triggered=False,
        is_confirmed=False,
        explanation="All quoted unit prices are within the maximum allowable +3% ceiling.",
        actual_value="Within acceptable threshold",
        expected_condition="Unit price <= max_price * 1.03",
    )


def evaluate_reject_rule_2_advance(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Reject Rule 2: Advance payment is more than 20%."""
    adv_prov = quotation.terms.advance_payment_percentage

    if adv_prov.status == ExtractionStatus.EXTRACTED and adv_prov.value is not None:
        if adv_prov.value > settings.max_advance_payment_pct:
            return RuleCheckResult(
                rule_id="REJECT_RULE_2",
                rule_name="Advance payment exceeds 20%",
                category=RuleCategory.REJECT,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=adv_prov.evidence_verified,
                explanation=f"Quoted advance payment is {adv_prov.value}%, exceeding the maximum permitted 20%.",
                actual_value=f"{adv_prov.value}%",
                expected_condition="Advance payment <= 20%",
                evidence_quote=adv_prov.raw_text or "",
                page_number=adv_prov.page_number or 1,
                confidence=adv_prov.confidence,
            )

    return RuleCheckResult(
        rule_id="REJECT_RULE_2",
        rule_name="Advance payment exceeds 20%",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
        triggered=False,
        is_confirmed=False,
        explanation="Advance payment terms do not exceed 20%.",
        actual_value=f"{adv_prov.value or 0}%",
        expected_condition="Advance payment <= 20%",
    )


def evaluate_reject_rule_3_penalty(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Reject Rule 3: The contract has no late-delivery penalty clause.

    Also incorporates Other Notes: late-delivery penalty must be at least 0.5% per week.
    """
    has_penalty_prov = quotation.terms.has_late_delivery_penalty
    penalty_rate_prov = quotation.terms.late_penalty_percentage_per_week

    # Unreadable file guard: an unreadable document must never become a confirmed missing clause
    if has_penalty_prov.status == ExtractionStatus.UNREADABLE:
        return RuleCheckResult(
            rule_id="REJECT_RULE_3",
            rule_name="Late-delivery penalty clause missing or insufficient",
            category=RuleCategory.REJECT,
            status=RuleStatus.UNCERTAIN,
            triggered=False,
            is_confirmed=False,
            explanation="Document is unreadable; penalty clause presence cannot be confirmed.",
            actual_value="Unreadable",
            expected_condition="Late delivery penalty >= 0.5% per week",
        )

    # 1. Clause completely missing
    if not has_penalty_prov.value or has_penalty_prov.status == ExtractionStatus.MISSING:
        return RuleCheckResult(
            rule_id="REJECT_RULE_3",
            rule_name="Late-delivery penalty clause missing or insufficient",
            category=RuleCategory.REJECT,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="The contract omits any late-delivery penalty clause entirely.",
            actual_value="No penalty clause present",
            expected_condition="Late-delivery penalty clause required (>= 0.5% per week)",
            evidence_quote="Absence of penalty clause in Terms and Conditions",
            page_number=1,
            confidence=1.0,
        )

    # 2. Clause present, but penalty rate is less than 0.5% per week
    if penalty_rate_prov.value is not None and penalty_rate_prov.value < settings.min_late_penalty_pct_per_week:
        return RuleCheckResult(
            rule_id="REJECT_RULE_3",
            rule_name="Late-delivery penalty clause missing or insufficient",
            category=RuleCategory.REJECT,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=penalty_rate_prov.evidence_verified,
            explanation=(
                f"Quoted late-delivery penalty rate ({penalty_rate_prov.value}%/week) "
                f"is below the minimum policy requirement of 0.5% per week."
            ),
            actual_value=f"{penalty_rate_prov.value}% per week",
            expected_condition="Penalty rate >= 0.5% per week",
            evidence_quote=penalty_rate_prov.raw_text or "",
            page_number=penalty_rate_prov.page_number or 1,
            confidence=penalty_rate_prov.confidence,
        )

    return RuleCheckResult(
        rule_id="REJECT_RULE_3",
        rule_name="Late-delivery penalty clause missing or insufficient",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
        triggered=False,
        is_confirmed=False,
        explanation="Contract includes a valid late-delivery penalty clause satisfying policy.",
        actual_value=f"{penalty_rate_prov.value or 0}% per week",
        expected_condition="Penalty rate >= 0.5% per week",
    )


def evaluate_reject_rule_4_tin_bin(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Reject Rule 4: The supplier's TIN or BIN is missing."""
    tin_prov = quotation.supplier_tin
    bin_prov = quotation.supplier_bin

    # Unreadable file guard
    if tin_prov.status == ExtractionStatus.UNREADABLE:
        return RuleCheckResult(
            rule_id="REJECT_RULE_4",
            rule_name="Supplier TIN or BIN missing",
            category=RuleCategory.REJECT,
            status=RuleStatus.UNCERTAIN,
            triggered=False,
            is_confirmed=False,
            explanation="Document is unreadable; tax registration could not be evaluated.",
            actual_value="Unreadable",
            expected_condition="Both TIN and BIN present on quotation",
        )

    # Check if both or either TIN/BIN is missing
    tin_missing = not tin_prov.value or tin_prov.status in (ExtractionStatus.MISSING, ExtractionStatus.AMBIGUOUS)
    bin_missing = not bin_prov.value or bin_prov.status in (ExtractionStatus.MISSING, ExtractionStatus.AMBIGUOUS)

    if tin_missing or bin_missing:
        reg_quote = quotation.registration_raw_quote.raw_text or "Missing registration details"
        missing_parts = []
        if tin_missing:
            missing_parts.append("TIN")
        if bin_missing:
            missing_parts.append("BIN")

        return RuleCheckResult(
            rule_id="REJECT_RULE_4",
            rule_name="Supplier TIN or BIN missing",
            category=RuleCategory.REJECT,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation=f"Supplier tax registration is missing required identifier(s): {', '.join(missing_parts)}.",
            actual_value=f"Missing: {', '.join(missing_parts)}",
            expected_condition="Both TIN and BIN must be provided",
            evidence_quote=reg_quote,
            page_number=quotation.registration_raw_quote.page_number or 1,
            confidence=1.0,
        )

    return RuleCheckResult(
        rule_id="REJECT_RULE_4",
        rule_name="Supplier TIN or BIN missing",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
        triggered=False,
        is_confirmed=False,
        explanation="Both supplier TIN and BIN are present and verified.",
        actual_value=f"TIN: {tin_prov.value}, BIN: {bin_prov.value}",
        expected_condition="Both TIN and BIN present",
    )


def evaluate_reject_rule_5_delivery_max(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Reject Rule 5: Delivery is promised later than 45 days after the purchase order."""
    del_prov = quotation.terms.delivery_timeline_days

    if del_prov.status == ExtractionStatus.UNREADABLE:
        return RuleCheckResult(
            rule_id="REJECT_RULE_5",
            rule_name="Delivery promised later than 45 days",
            category=RuleCategory.REJECT,
            status=RuleStatus.UNCERTAIN,
            triggered=False,
            is_confirmed=False,
            explanation="Delivery schedule could not be determined due to unreadable document.",
            actual_value="Unreadable",
            expected_condition="Delivery <= 45 days after PO",
        )

    if del_prov.status == ExtractionStatus.EXTRACTED and del_prov.value is not None:
        if del_prov.value > settings.max_delivery_days:
            return RuleCheckResult(
                rule_id="REJECT_RULE_5",
                rule_name="Delivery promised later than 45 days",
                category=RuleCategory.REJECT,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=del_prov.evidence_verified,
                explanation=f"Promised delivery timeline of {del_prov.value} days exceeds the 45-day limit.",
                actual_value=f"{del_prov.value} days",
                expected_condition="Delivery <= 45 days of PO",
                evidence_quote=del_prov.raw_text or "",
                page_number=del_prov.page_number or 1,
                confidence=del_prov.confidence,
            )

    return RuleCheckResult(
        rule_id="REJECT_RULE_5",
        rule_name="Delivery promised later than 45 days",
        category=RuleCategory.REJECT,
        status=RuleStatus.PASS,
        triggered=False,
        is_confirmed=False,
        explanation="Promised delivery timeline is within 45 days of PO.",
        actual_value=f"{del_prov.value or 'N/A'} days",
        expected_condition="Delivery <= 45 days",
    )


# ==============================================================================
# HUMAN REVIEW RULES (1 to 7)
# ==============================================================================


def evaluate_review_rule_1_marginal_price(pr_comparison: PRComparisonReport) -> RuleCheckResult:
    """Review Rule 1: Unit price is above the maximum, but by no more than 3%."""
    for item in pr_comparison.matched_items:
        if item.price_is_within_review_band:
            return RuleCheckResult(
                rule_id="REVIEW_RULE_1",
                rule_name="Unit price above maximum by <= 3%",
                category=RuleCategory.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=(
                    f"Quoted unit price ({item.quoted_unit_price:,.2f} BDT) for item {item.item_code} "
                    f"is {item.price_variance_pct:+,.2f}% above PR maximum ({item.max_unit_price:,.2f} BDT), "
                    f"which falls into the <= 3% discretionary review bracket."
                ),
                actual_value=f"{item.quoted_unit_price:,.2f} BDT (+{item.price_variance_pct}%)",
                expected_condition=f"<= {item.max_unit_price:,.2f} BDT",
                evidence_quote=item.evidence_quote,
                page_number=1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_1",
        rule_name="Unit price above maximum by <= 3%",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="Unit price is not within the marginal +3% review bracket.",
    )


def evaluate_review_rule_2_quantity_variance(pr_comparison: PRComparisonReport) -> RuleCheckResult:
    """Review Rule 2: Quantity differs from the quantity requested by more than 5%."""
    for item in pr_comparison.matched_items:
        if not item.quantity_within_tolerance:
            return RuleCheckResult(
                rule_id="REVIEW_RULE_2",
                rule_name="Quantity differs from requested by > 5%",
                category=RuleCategory.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=(
                    f"Quoted quantity ({item.quoted_quantity:,.0f} {item.quoted_unit}) differs by "
                    f"{item.quantity_variance_pct:+,.2f}% from requested ({item.requested_quantity:,.0f} {item.pr_unit}), "
                    f"exceeding the allowable 5% tolerance band."
                ),
                actual_value=f"{item.quoted_quantity:,.0f} {item.quoted_unit} ({item.quantity_variance_pct:+,.2f}%)",
                expected_condition=f"Within ±5% of {item.requested_quantity:,.0f}",
                evidence_quote=item.evidence_quote,
                page_number=1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_2",
        rule_name="Quantity differs from requested by > 5%",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="Quoted quantities are within the ±5% tolerance band.",
    )


def evaluate_review_rule_3_payment_terms(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Review Rule 3: Payment terms are unclear, or outside 30 to 60 days after delivery."""
    terms = quotation.terms
    credit_days_prov = terms.credit_days_after_delivery
    unclear_prov = terms.payment_terms_unclear

    # Check for ambiguity, unclarity, or missing payment credit term
    if unclear_prov.value or credit_days_prov.status == ExtractionStatus.AMBIGUOUS:
        return RuleCheckResult(
            rule_id="REVIEW_RULE_3",
            rule_name="Payment terms unclear or outside 30 to 60 days",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="Payment credit terms are ambiguous, conditional, or subject to later agreement.",
            actual_value="Ambiguous / Conditional terms",
            expected_condition="Clear credit term between 30 and 60 days after delivery",
            evidence_quote=terms.payment_terms_text.raw_text or "",
            page_number=terms.payment_terms_text.page_number or 1,
            confidence=1.0,
        )

    if credit_days_prov.value is not None:
        if credit_days_prov.value < settings.min_credit_days_review or credit_days_prov.value > settings.max_credit_days_review:
            return RuleCheckResult(
                rule_id="REVIEW_RULE_3",
                rule_name="Payment terms unclear or outside 30 to 60 days",
                category=RuleCategory.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=f"Quoted credit period of {credit_days_prov.value} days is outside the standard 30 to 60 day window.",
                actual_value=f"{credit_days_prov.value} days",
                expected_condition="Credit period between 30 and 60 days",
                evidence_quote=terms.payment_terms_text.raw_text or "",
                page_number=terms.payment_terms_text.page_number or 1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_3",
        rule_name="Payment terms unclear or outside 30 to 60 days",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="Payment credit terms are clear and within the standard 30 to 60 day window.",
        actual_value=f"{credit_days_prov.value or 'N/A'} days",
        expected_condition="30 to 60 days",
    )


def evaluate_review_rule_4_delivery_borderline(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Review Rule 4: Delivery is promised in 31 to 45 days."""
    del_prov = quotation.terms.delivery_timeline_days

    if del_prov.value is not None and del_prov.status == ExtractionStatus.EXTRACTED:
        if settings.min_delivery_days_review <= del_prov.value <= settings.max_delivery_days:
            return RuleCheckResult(
                rule_id="REVIEW_RULE_4",
                rule_name="Delivery promised in 31 to 45 days",
                category=RuleCategory.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=f"Promised delivery timeline of {del_prov.value} days falls in the 31 to 45 day review bracket.",
                actual_value=f"{del_prov.value} days",
                expected_condition="<= 30 days (fast-track approval)",
                evidence_quote=del_prov.raw_text or "",
                page_number=del_prov.page_number or 1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_4",
        rule_name="Delivery promised in 31 to 45 days",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="Delivery timeline is not within the 31 to 45 day review window.",
    )


def evaluate_review_rule_5_vat_separation(
    quotation: ExtractedQuotation, math_audit: ArithmeticAuditResult
) -> RuleCheckResult:
    """Review Rule 5: VAT is not shown separately at 15%."""
    vat_shown = quotation.vat_shown_separately.value and math_audit.vat_shown_separately
    vat_pct = quotation.vat_percentage.value

    if not vat_shown:
        return RuleCheckResult(
            rule_id="REVIEW_RULE_5",
            rule_name="VAT is not shown separately at 15%",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="VAT is bundled into unit price or omitted rather than shown separately at 15%.",
            actual_value="Bundled / Not shown separately",
            expected_condition="VAT shown separately at 15%",
            evidence_quote=quotation.total_amount.raw_text or "VAT inclusive pricing",
            page_number=quotation.total_amount.page_number or 1,
            confidence=1.0,
        )

    if vat_pct is not None and vat_pct != Decimal("15"):
        return RuleCheckResult(
            rule_id="REVIEW_RULE_5",
            rule_name="VAT is not shown separately at 15%",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation=f"VAT rate is {vat_pct}%, differing from the standard 15% requirement.",
            actual_value=f"{vat_pct}%",
            expected_condition="15%",
            evidence_quote=quotation.vat_percentage.raw_text or "",
            page_number=quotation.vat_percentage.page_number or 1,
            confidence=1.0,
        )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_5",
        rule_name="VAT is not shown separately at 15%",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="VAT is clearly and separately displayed at the required 15% rate.",
        actual_value="15% separated",
        expected_condition="15% separated",
    )


def evaluate_review_rule_6_arithmetic_errors(math_audit: ArithmeticAuditResult) -> RuleCheckResult:
    """Review Rule 6: The numbers do not add up (for example line total or subtotal is wrong)."""
    if not math_audit.all_passed:
        disc_summary = "; ".join(math_audit.discrepancy_details)
        first_quote = math_audit.discrepancies[0].evidence_quote if math_audit.discrepancies else ""

        return RuleCheckResult(
            rule_id="REVIEW_RULE_6",
            rule_name="Financial numbers do not add up",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation=f"Mathematical discrepancy detected: {disc_summary}",
            actual_value="Calculations inconsistent with document figures",
            expected_condition="Line amounts, subtotals, VAT, and grand totals must add up",
            evidence_quote=first_quote,
            page_number=1,
            confidence=1.0,
        )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_6",
        rule_name="Financial numbers do not add up",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="All line item amounts, subtotals, VAT, and grand totals add up consistently.",
        actual_value="All calculations verified",
        expected_condition="Exact mathematical consistency",
    )


def evaluate_review_rule_7_quotation_validity(quotation: ExtractedQuotation) -> RuleCheckResult:
    """Review Rule 7: The quotation is valid for less than 30 days."""
    val_prov = quotation.terms.quotation_validity_days

    if val_prov.status == ExtractionStatus.EXTRACTED and val_prov.value is not None:
        if val_prov.value < settings.min_quotation_validity_days:
            return RuleCheckResult(
                rule_id="REVIEW_RULE_7",
                rule_name="Quotation valid for less than 30 days",
                category=RuleCategory.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                triggered=True,
                is_confirmed=True,
                explanation=f"Quotation validity of {val_prov.value} days is less than the required 30 days.",
                actual_value=f"{val_prov.value} days",
                expected_condition="Validity >= 30 days",
                evidence_quote=val_prov.raw_text or "",
                page_number=val_prov.page_number or 1,
                confidence=1.0,
            )

    return RuleCheckResult(
        rule_id="REVIEW_RULE_7",
        rule_name="Quotation valid for less than 30 days",
        category=RuleCategory.HUMAN_REVIEW,
        status=RuleStatus.PASS,
        triggered=False,
        explanation="Quotation validity period meets or exceeds 30 days.",
        actual_value=f"{val_prov.value or 'N/A'} days",
        expected_condition="Validity >= 30 days",
    )


# ==============================================================================
# INTEGRITY / MATCHING AUDIT
# ==============================================================================


def evaluate_matching_integrity(pr_comparison: PRComparisonReport) -> Optional[RuleCheckResult]:
    """Ensures quotation has a valid, unambiguous PR item match without discrepancies."""
    if pr_comparison.unknown_item_codes:
        return RuleCheckResult(
            rule_id="REVIEW_PR_MATCH_UNKNOWN",
            rule_name="Unknown item code in quotation",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation=f"Quotation contains item codes not found in PR: {', '.join(pr_comparison.unknown_item_codes)}",
            actual_value=f"Unknown codes: {', '.join(pr_comparison.unknown_item_codes)}",
            expected_condition="All items must match PR",
        )

    if pr_comparison.duplicate_item_codes:
        return RuleCheckResult(
            rule_id="REVIEW_PR_MATCH_DUPLICATE",
            rule_name="Duplicate item codes in quotation",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation=f"Quotation contains duplicate line items for code(s): {', '.join(pr_comparison.duplicate_item_codes)}",
            actual_value="Duplicate item codes",
            expected_condition="Single line item per item code",
        )

    if pr_comparison.has_unit_mismatch:
        return RuleCheckResult(
            rule_id="REVIEW_PR_UNIT_MISMATCH",
            rule_name="Measurement unit mismatch with PR",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="Quoted measurement unit does not match PR specification.",
            actual_value="Unit mismatch",
            expected_condition="Quoted unit must match PR unit",
        )

    if pr_comparison.has_description_mismatch:
        return RuleCheckResult(
            rule_id="REVIEW_PR_DESC_MISMATCH",
            rule_name="Item description mismatch with PR",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="Quoted item description contradicts PR specification.",
            actual_value="Description mismatch",
            expected_condition="Description must be compatible with PR",
        )

    if not pr_comparison.matched_items:
        return RuleCheckResult(
            rule_id="REVIEW_PR_NO_MATCH",
            rule_name="No matching PR items found",
            category=RuleCategory.HUMAN_REVIEW,
            status=RuleStatus.FAIL,
            triggered=True,
            is_confirmed=True,
            explanation="No line item in the quotation matched any item in the Purchase Request.",
            actual_value="0 matched items",
            expected_condition="At least one valid matched item required",
        )

    return None


class CompanyRuleEngine:
    """Deterministic business rule evaluation engine implementing company-rules.md."""

    def __init__(self, verification_settings=settings):
        self.settings = verification_settings

    def evaluate_all(
        self,
        quotation: ExtractedQuotation,
        pr_comparison: PRComparisonReport,
        math_audit: ArithmeticAuditResult,
    ) -> List[RuleCheckResult]:
        """Evaluates all rules sequentially: integrity, reject rules (1-5), and review rules (1-7)."""
        results: List[RuleCheckResult] = []

        # 1. Matching Integrity
        integrity_check = evaluate_matching_integrity(pr_comparison)
        if integrity_check is not None:
            results.append(integrity_check)

        # 2. Reject Rules (1 to 5)
        results.append(evaluate_reject_rule_1_price(pr_comparison))
        results.append(evaluate_reject_rule_2_advance(quotation))
        results.append(evaluate_reject_rule_3_penalty(quotation))
        results.append(evaluate_reject_rule_4_tin_bin(quotation))
        results.append(evaluate_reject_rule_5_delivery_max(quotation))

        # 3. Human Review Rules (1 to 7)
        results.append(evaluate_review_rule_1_marginal_price(pr_comparison))
        results.append(evaluate_review_rule_2_quantity_variance(pr_comparison))
        results.append(evaluate_review_rule_3_payment_terms(quotation))
        results.append(evaluate_review_rule_4_delivery_borderline(quotation))
        results.append(evaluate_review_rule_5_vat_separation(quotation, math_audit))
        results.append(evaluate_review_rule_6_arithmetic_errors(math_audit))
        results.append(evaluate_review_rule_7_quotation_validity(quotation))

        return results

