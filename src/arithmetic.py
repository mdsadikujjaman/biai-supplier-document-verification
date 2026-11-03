from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import List, Optional
from src.config import settings
from src.interfaces.base import BaseArithmeticVerifier
from src.models.schemas import (
    ArithmeticAuditResult,
    ArithmeticDiscrepancy,
    ExtractedQuotation,
    LineItemArithmeticCheck,
)

logger = logging.getLogger(__name__)

# Currency precision rounding constant
PENNY = Decimal("0.01")


def round_currency(val: Decimal) -> Decimal:
    """Explicit half-up currency rounding to 2 decimal places."""
    return val.quantize(PENNY, rounding=ROUND_HALF_UP)


class ArithmeticVerifier(BaseArithmeticVerifier):
    """Deterministic mathematical consistency verification engine.

    Uses Python Decimal with explicit half-up currency rounding.
    Verifies line item totals, subtotal sums, VAT calculation, and grand total.
    Never alters or corrects supplier quoted values.
    """

    def __init__(self, currency_tolerance: Optional[Decimal] = None):
        self.tolerance = currency_tolerance or settings.currency_tolerance

    def verify(self, quotation: ExtractedQuotation) -> ArithmeticAuditResult:
        line_checks: List[LineItemArithmeticCheck] = []
        discrepancies: List[ArithmeticDiscrepancy] = []
        discrepancy_details: List[str] = []

        line_calculations_match = True
        calc_line_amounts: List[Decimal] = []

        # 1. Recalculate each line item
        for idx, item in enumerate(quotation.line_items):
            code = item.item_code.value or f"Item_{idx+1}"
            qty = item.quantity.value
            price = item.unit_price.value
            quoted_amt = item.line_amount.value if item.line_amount else None
            evidence = item.line_amount.raw_text if item.line_amount and item.line_amount.raw_text else ""

            if qty is not None and price is not None:
                calc_amt = round_currency(qty * price)
                calc_line_amounts.append(calc_amt)

                if quoted_amt is not None:
                    diff = abs(calc_amt - quoted_amt)
                    matches = diff <= self.tolerance
                    if not matches:
                        line_calculations_match = False
                        msg = (
                            f"Line item {code} calculation mismatch: {qty} x {price} = {calc_amt:,.2f} BDT, "
                            f"but document quoted {quoted_amt:,.2f} BDT (difference: {quoted_amt - calc_amt:+,.2f} BDT)."
                        )
                        discrepancies.append(
                            ArithmeticDiscrepancy(
                                component="LINE_AMOUNT",
                                expected_value=calc_amt,
                                quoted_value=quoted_amt,
                                discrepancy_amount=quoted_amt - calc_amt,
                                evidence_quote=evidence,
                                details=msg,
                            )
                        )
                        discrepancy_details.append(msg)
                else:
                    matches = True  # Quoted amount not shown on line
            else:
                calc_amt = Decimal("0.00")
                matches = False

            line_checks.append(
                LineItemArithmeticCheck(
                    item_code=code,
                    quantity=qty or Decimal("0"),
                    unit_price=price or Decimal("0.00"),
                    calculated_amount=calc_amt,
                    quoted_amount=quoted_amt,
                    difference=quoted_amt - calc_amt if quoted_amt is not None else Decimal("0.00"),
                    matches=matches,
                    evidence_quote=evidence,
                )
            )

        # 2. Recalculate Subtotal
        calculated_subtotal = round_currency(sum(calc_line_amounts)) if calc_line_amounts else None
        quoted_subtotal = quotation.subtotal.value if quotation.subtotal else None
        subtotal_evidence = quotation.subtotal.raw_text if quotation.subtotal and quotation.subtotal.raw_text else ""

        if quoted_subtotal is not None and calculated_subtotal is not None:
            subtotal_diff = abs(calculated_subtotal - quoted_subtotal)
            subtotal_matches = subtotal_diff <= self.tolerance
            if not subtotal_matches:
                msg = (
                    f"Subtotal mismatch: sum of line items is {calculated_subtotal:,.2f} BDT, "
                    f"but quoted subtotal is {quoted_subtotal:,.2f} BDT (difference: {quoted_subtotal - calculated_subtotal:+,.2f} BDT)."
                )
                discrepancies.append(
                    ArithmeticDiscrepancy(
                        component="SUBTOTAL",
                        expected_value=calculated_subtotal,
                        quoted_value=quoted_subtotal,
                        discrepancy_amount=quoted_subtotal - calculated_subtotal,
                        evidence_quote=subtotal_evidence,
                        details=msg,
                    )
                )
                discrepancy_details.append(msg)
        elif quoted_subtotal is None and calculated_subtotal is not None:
            # Subtotal omitted (e.g. Pack 10)
            subtotal_matches = False
            msg = "Subtotal is not shown separately in the quotation."
            discrepancy_details.append(msg)
        else:
            subtotal_matches = True

        # 3. Recalculate VAT
        vat_shown_separately = bool(quotation.vat_shown_separately.value) if quotation.vat_shown_separately and quotation.vat_shown_separately.value is not None else False
        quoted_vat = quotation.vat_amount.value if quotation.vat_amount else None
        vat_evidence = quotation.vat_amount.raw_text if quotation.vat_amount and quotation.vat_amount.raw_text else ""

        if vat_shown_separately:
            vat_pct = quotation.vat_percentage.value or Decimal("15")
            vat_rate = vat_pct / Decimal("100")

            # VAT calculated on subtotal
            base_for_vat = quoted_subtotal if quoted_subtotal is not None else calculated_subtotal
            if base_for_vat is not None:
                calculated_vat = round_currency(base_for_vat * vat_rate)
            else:
                calculated_vat = None

            if quoted_vat is not None and calculated_vat is not None:
                vat_diff = abs(calculated_vat - quoted_vat)
                vat_matches = vat_diff <= self.tolerance
                if not vat_matches:
                    msg = (
                        f"VAT amount mismatch: expected {vat_pct}% of {base_for_vat:,.2f} is {calculated_vat:,.2f} BDT, "
                        f"but quoted VAT is {quoted_vat:,.2f} BDT (difference: {quoted_vat - calculated_vat:+,.2f} BDT)."
                    )
                    discrepancies.append(
                        ArithmeticDiscrepancy(
                            component="VAT",
                            expected_value=calculated_vat,
                            quoted_value=quoted_vat,
                            discrepancy_amount=quoted_vat - calculated_vat,
                            evidence_quote=vat_evidence,
                            details=msg,
                        )
                    )
                    discrepancy_details.append(msg)
            else:
                vat_matches = False
        else:
            calculated_vat = None
            vat_matches = False
            msg = "VAT is not shown separately at 15% (bundled or omitted in document)."
            discrepancy_details.append(msg)

        # 4. Recalculate Grand Total
        quoted_total = quotation.total_amount.value if quotation.total_amount else None
        total_evidence = quotation.total_amount.raw_text if quotation.total_amount and quotation.total_amount.raw_text else ""

        if vat_shown_separately:
            base_subtotal = quoted_subtotal if quoted_subtotal is not None else calculated_subtotal
            base_vat = quoted_vat if quoted_vat is not None else calculated_vat
            if base_subtotal is not None and base_vat is not None:
                calculated_total = round_currency(base_subtotal + base_vat)
            else:
                calculated_total = None
        else:
            # Bundled tax: total expected to equal sum of lines
            calculated_total = calculated_subtotal

        if quoted_total is not None and calculated_total is not None:
            total_diff = abs(calculated_total - quoted_total)
            total_matches = total_diff <= self.tolerance
            if not total_matches:
                msg = (
                    f"Grand total mismatch: expected {calculated_total:,.2f} BDT, "
                    f"but quoted total is {quoted_total:,.2f} BDT (difference: {quoted_total - calculated_total:+,.2f} BDT)."
                )
                discrepancies.append(
                    ArithmeticDiscrepancy(
                        component="TOTAL",
                        expected_value=calculated_total,
                        quoted_value=quoted_total,
                        discrepancy_amount=quoted_total - calculated_total,
                        evidence_quote=total_evidence,
                        details=msg,
                    )
                )
                discrepancy_details.append(msg)
        else:
            total_matches = False

        return ArithmeticAuditResult(
            line_calculations_match=line_calculations_match,
            subtotal_matches_lines=subtotal_matches,
            vat_matches_subtotal_15pct=vat_matches,
            total_matches_sum=total_matches,
            vat_shown_separately=vat_shown_separately,
            calculated_subtotal=calculated_subtotal,
            calculated_vat=calculated_vat,
            calculated_total=calculated_total,
            quoted_subtotal=quoted_subtotal,
            quoted_vat=quoted_vat,
            quoted_total=quoted_total,
            line_checks=line_checks,
            discrepancies=discrepancies,
            discrepancy_details=discrepancy_details,
        )

