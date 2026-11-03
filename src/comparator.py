from decimal import Decimal
import logging
from typing import List, Optional
from src.config import settings
from src.models.schemas import (
    ExtractedQuotation,
    ItemComparisonResult,
    PRComparisonReport,
    PurchaseRequest,
)

logger = logging.getLogger(__name__)


def is_description_compatible(pr_desc: str, quoted_desc: str) -> bool:
    """Validate that quoted item description is consistent with PR item description.

    Performs case-insensitive token overlap check to detect severe contradictions
    (e.g., matching item A but quoting carton boxes).
    """
    pr_tokens = set(re_clean_tokens(pr_desc))
    quoted_tokens = set(re_clean_tokens(quoted_desc))

    # If key core tokens (excluding punctuation/stopwords) overlap significantly
    overlap = pr_tokens.intersection(quoted_tokens)
    return len(overlap) >= 1


def re_clean_tokens(text: str) -> List[str]:
    import re
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    stopwords = {"and", "or", "in", "the", "for", "a", "an", "cm", "gsm"}
    return [t for t in cleaned.split() if t and t not in stopwords]


def is_unit_compatible(pr_unit: str, quoted_unit: str) -> bool:
    """Validate that measurement units match or are standardized synonyms."""
    pr_u = pr_unit.strip().lower()
    qu_u = quoted_unit.strip().lower()

    if pr_u == qu_u:
        return True

    # Common unit synonyms
    synonyms = {
        "metre": {"metre", "meter", "m"},
        "piece": {"piece", "pc", "pcs"},
        "cone": {"cone", "cones"},
    }
    for base, syns in synonyms.items():
        if pr_u in syns and qu_u in syns:
            return True

    return False


class PurchaseRequestComparator:
    """Compares extracted supplier quotations against the official Purchase Request benchmark.

    Evaluates item matching, description compatibility, unit conformity,
    quantity variances (±5% tolerance), and unit price variances (+3% threshold).
    All calculations are executed strictly with Decimal.
    """

    def __init__(
        self,
        price_rejection_threshold: Optional[Decimal] = None,
        quantity_tolerance: Optional[Decimal] = None,
    ):
        self.price_threshold = price_rejection_threshold or settings.price_rejection_threshold
        self.qty_tolerance = quantity_tolerance or settings.quantity_tolerance_threshold

    def compare(self, quotation: ExtractedQuotation, pr: PurchaseRequest) -> PRComparisonReport:
        matched_items: List[ItemComparisonResult] = []
        unknown_item_codes: List[str] = []
        duplicate_item_codes: List[str] = []
        comparison_notes: List[str] = []

        seen_codes = set()
        has_unit_mismatch = False
        has_description_mismatch = False

        for idx, line in enumerate(quotation.line_items):
            code = (line.item_code.value or "").strip().upper()
            quoted_desc = (line.description.value or "").strip()
            quoted_unit = (line.unit.value or "").strip()
            quoted_qty = line.quantity.value or Decimal("0")
            quoted_price = line.unit_price.value or Decimal("0.00")
            evidence = line.item_code.raw_text or f"Item {code}"

            if not code or code not in pr.items:
                unknown_item_codes.append(code or f"UNKNOWN_INDEX_{idx+1}")
                note = f"Quotation item '{code}' does not match any line item in Purchase Request {pr.pr_number}."
                comparison_notes.append(note)
                continue

            if code in seen_codes:
                duplicate_item_codes.append(code)
                note = f"Duplicate quotation line for item code '{code}' detected."
                comparison_notes.append(note)

            seen_codes.add(code)
            pr_item = pr.items[code]

            # Validate Description & Unit
            desc_match = is_description_compatible(pr_item.description, quoted_desc)
            if not desc_match:
                has_description_mismatch = True
                comparison_notes.append(
                    f"Item {code} description mismatch: PR expects '{pr_item.description}', "
                    f"but supplier quoted '{quoted_desc}'."
                )

            unit_match = is_unit_compatible(pr_item.unit, quoted_unit)
            if not unit_match:
                has_unit_mismatch = True
                comparison_notes.append(
                    f"Item {code} unit mismatch: PR expects '{pr_item.unit}', "
                    f"but supplier quoted '{quoted_unit}'."
                )

            is_valid_match = desc_match and unit_match

            # Quantity calculations
            req_qty = pr_item.quantity_requested
            qty_diff = quoted_qty - req_qty
            qty_variance_pct = ((qty_diff / req_qty) * Decimal("100")).quantize(Decimal("0.01"))
            within_qty_tol = pr_item.min_quantity_tolerance <= quoted_qty <= pr_item.max_quantity_tolerance

            if not within_qty_tol:
                comparison_notes.append(
                    f"Item {code} quantity variance of {qty_variance_pct:+,.2f}% "
                    f"(quoted {quoted_qty:,.0f} vs requested {req_qty:,.0f}) exceeds ±5% tolerance."
                )

            # Price calculations
            max_price = pr_item.maximum_unit_price
            price_diff = quoted_price - max_price
            price_variance_pct = ((price_diff / max_price) * Decimal("100")).quantize(Decimal("0.01"))
            ceiling = pr_item.price_rejection_ceiling

            price_is_below_or_equal_max = quoted_price <= max_price
            price_is_within_review_band = max_price < quoted_price <= ceiling
            price_exceeds_rejection_ceiling = quoted_price > ceiling

            if price_exceeds_rejection_ceiling:
                comparison_notes.append(
                    f"Item {code} unit price {quoted_price:,.2f} BDT is {price_variance_pct:+,.2f}% "
                    f"above max price {max_price:,.2f} BDT, exceeding the +3% ceiling ({ceiling:,.2f} BDT)."
                )
            elif price_is_within_review_band:
                comparison_notes.append(
                    f"Item {code} unit price {quoted_price:,.2f} BDT is {price_variance_pct:+,.2f}% "
                    f"above max price {max_price:,.2f} BDT, within the +3% discretionary review band."
                )

            item_result = ItemComparisonResult(
                item_code=code,
                pr_description=pr_item.description,
                quoted_description=quoted_desc,
                description_match=desc_match,
                pr_unit=pr_item.unit,
                quoted_unit=quoted_unit,
                unit_match=unit_match,
                requested_quantity=req_qty,
                quoted_quantity=quoted_qty,
                quantity_difference=qty_diff,
                quantity_variance_pct=qty_variance_pct,
                quantity_within_tolerance=within_qty_tol,
                max_unit_price=max_price,
                quoted_unit_price=quoted_price,
                price_difference=price_diff,
                price_variance_pct=price_variance_pct,
                price_rejection_ceiling=ceiling,
                price_is_below_or_equal_max=price_is_below_or_equal_max,
                price_is_within_review_band=price_is_within_review_band,
                price_exceeds_rejection_ceiling=price_exceeds_rejection_ceiling,
                evidence_quote=evidence,
                is_valid_match=is_valid_match,
            )
            matched_items.append(item_result)

        unmatched_pr = [code for code in pr.items if code not in seen_codes]

        return PRComparisonReport(
            pr_number=pr.pr_number,
            matched_items=matched_items,
            unknown_item_codes=unknown_item_codes,
            unmatched_pr_items=unmatched_pr,
            duplicate_item_codes=duplicate_item_codes,
            has_unit_mismatch=has_unit_mismatch,
            has_description_mismatch=has_description_mismatch,
            comparison_notes=comparison_notes,
        )
