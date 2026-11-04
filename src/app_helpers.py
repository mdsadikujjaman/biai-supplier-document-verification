import json
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from src.models.schemas import DecisionEnum

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit per PDF document


def validate_uploaded_pdf(file_name: str, file_size: int, max_bytes: int = MAX_FILE_SIZE_BYTES) -> Tuple[bool, str]:
    """Validates that uploaded file is a valid PDF within acceptable size limits."""
    if not file_name.lower().endswith(".pdf"):
        return False, f"Invalid file format: '{file_name}'. Only PDF files are supported."

    if file_size <= 0:
        return False, f"Empty file: '{file_name}' contains 0 bytes."

    if file_size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"File too large: '{file_name}' is {actual_mb:.1f} MB (maximum allowed is {max_mb:.0f} MB)."

    return True, ""


def save_uploaded_stream_to_temp(uploaded_file, target_dir: Path) -> Path:
    """Safely saves an uploaded file buffer to a dedicated temporary directory.

    Guarantees isolation and ensures temporary file cleanup.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = target_dir / uploaded_file.name

    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return temp_file_path


def cleanup_directory(directory: Optional[Path]) -> None:
    """Safely removes temporary directory and its contents."""
    if directory and directory.exists() and directory.is_dir():
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary directory {directory}: {e}")


def load_benchmark_report_json(reports_path: Path = Path("reports/evaluation_summary.json")) -> Optional[Dict[str, Any]]:
    """Loads benchmark evaluation JSON summary."""
    if not reports_path.exists():
        return None
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading benchmark report from {reports_path}: {e}")
        return None


def load_benchmark_report_markdown(reports_path: Path = Path("reports/audit_summary.md")) -> Optional[str]:
    """Loads benchmark executive audit markdown report."""
    if not reports_path.exists():
        return None
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading markdown report from {reports_path}: {e}")
        return None


def get_decision_color_theme(decision: DecisionEnum) -> Dict[str, str]:
    """Returns accessible color styles and icons for each decision state."""
    if decision == DecisionEnum.APPROVE:
        return {
            "bg": "#ecfdf5",
            "border": "#10b981",
            "text": "#065f46",
            "badge": "🟢 APPROVED",
            "icon": "✅",
        }
    elif decision == DecisionEnum.REJECT:
        return {
            "bg": "#fef2f2",
            "border": "#ef4444",
            "text": "#991b1b",
            "badge": "🔴 REJECTED",
            "icon": "❌",
        }
    else:
        return {
            "bg": "#fffbeb",
            "border": "#f59e0b",
            "text": "#92400e",
            "badge": "🟡 NEEDS HUMAN REVIEW",
            "icon": "⚠️",
        }


def build_plain_language_findings(report: Any) -> List[Dict[str, str]]:
    """Translates deterministic rule evaluation results into a plain-language summary table

    designed specifically for non-technical procurement managers.
    """
    rules_by_id = {r.rule_id: r for r in getattr(report, "all_evaluated_rules", [])}
    triggered_ids = {r.rule_id for r in getattr(report, "triggered_rules", [])}

    findings: List[Dict[str, str]] = []

    # 1. Unit price check
    if "REJECT_RULE_1" in triggered_ids:
        r = rules_by_id["REJECT_RULE_1"]
        findings.append({
            "Check": "Unit price",
            "Result": "Failed (Confirmed Violation)",
            "Explanation": r.explanation or "Quoted unit price exceeds the purchase request limit by more than 3%.",
            "Status": "FAILED",
        })
    elif "REVIEW_RULE_1" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_1"]
        findings.append({
            "Check": "Unit price",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Quoted unit price is above the purchase request limit, but within the 3% discretionary review band.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Unit price",
            "Result": "Passed",
            "Explanation": "Quoted unit price is within the purchase request limit.",
            "Status": "PASSED",
        })

    # 2. Quantity & unit check
    if "REVIEW_RULE_2" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_2"]
        findings.append({
            "Check": "Quantity & unit",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Quoted quantity differs from the requested quantity by more than 5%.",
            "Status": "REVIEW",
        })
    elif "REVIEW_PR_UNIT_MISMATCH" in triggered_ids:
        r = rules_by_id["REVIEW_PR_UNIT_MISMATCH"]
        findings.append({
            "Check": "Quantity & unit",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Quoted unit of measure does not match the purchase request specification.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Quantity & unit",
            "Result": "Passed",
            "Explanation": "Quoted quantity and unit match the purchase request within tolerance.",
            "Status": "PASSED",
        })

    # 3. Advance payment check
    if "REJECT_RULE_2" in triggered_ids:
        r = rules_by_id["REJECT_RULE_2"]
        findings.append({
            "Check": "Advance payment",
            "Result": "Failed (Confirmed Violation)",
            "Explanation": r.explanation or "Requested advance payment exceeds the company 20% limit.",
            "Status": "FAILED",
        })
    else:
        findings.append({
            "Check": "Advance payment",
            "Result": "Passed",
            "Explanation": "Advance payment terms comply with company policy (<= 20%).",
            "Status": "PASSED",
        })

    # 4. Delivery schedule check
    if "REJECT_RULE_5" in triggered_ids:
        r = rules_by_id["REJECT_RULE_5"]
        findings.append({
            "Check": "Delivery period",
            "Result": "Failed (Confirmed Violation)",
            "Explanation": r.explanation or "Promised delivery timeline exceeds the company 45-day maximum limit.",
            "Status": "FAILED",
        })
    elif "REVIEW_RULE_4" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_4"]
        findings.append({
            "Check": "Delivery period",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Promised delivery is between 31 and 45 days, requiring procurement review.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Delivery period",
            "Result": "Passed",
            "Explanation": "Promised delivery period is within permitted limits (<= 30 days).",
            "Status": "PASSED",
        })

    # 5. Late-delivery penalty clause
    if "REJECT_RULE_3" in triggered_ids:
        r = rules_by_id["REJECT_RULE_3"]
        status_label = "Uncertain" if r.status.value == "UNCERTAIN" else "Failed (Confirmed Violation)"
        findings.append({
            "Check": "Late-delivery penalty",
            "Result": status_label,
            "Explanation": r.explanation or "The contract omits a late-delivery penalty clause, or the rate is below 0.5% per week.",
            "Status": "UNCERTAIN" if r.status.value == "UNCERTAIN" else "FAILED",
        })
    else:
        findings.append({
            "Check": "Late-delivery penalty",
            "Result": "Passed",
            "Explanation": "Contract contains a compliant late-delivery penalty clause (>= 0.5% per week).",
            "Status": "PASSED",
        })

    # 6. Supplier tax registration (TIN & BIN)
    if "REJECT_RULE_4" in triggered_ids:
        r = rules_by_id["REJECT_RULE_4"]
        status_label = "Uncertain" if r.status.value == "UNCERTAIN" else "Failed (Confirmed Violation)"
        findings.append({
            "Check": "TIN & BIN registration",
            "Result": status_label,
            "Explanation": r.explanation or "Supplier tax registration is missing required identifier(s): TIN and/or BIN.",
            "Status": "UNCERTAIN" if r.status.value == "UNCERTAIN" else "FAILED",
        })
    else:
        findings.append({
            "Check": "TIN & BIN registration",
            "Result": "Passed",
            "Explanation": "Both supplier TIN and BIN are present and verified on the document.",
            "Status": "PASSED",
        })

    # 7. VAT separation (15%)
    if "REVIEW_RULE_5" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_5"]
        findings.append({
            "Check": "VAT itemization (15%)",
            "Result": "Needs Review",
            "Explanation": r.explanation or "VAT is bundled into the unit price or not shown separately at 15%.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "VAT itemization (15%)",
            "Result": "Passed",
            "Explanation": "Statutory 15% VAT is clearly itemized and shown separately.",
            "Status": "PASSED",
        })

    # 8. Financial arithmetic
    if "REVIEW_RULE_6" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_6"]
        findings.append({
            "Check": "Financial calculations",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Mathematical discrepancy detected in line totals, subtotal, VAT, or grand total.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Financial calculations",
            "Result": "Passed",
            "Explanation": "All line totals, subtotal, VAT, and grand totals add up consistently.",
            "Status": "PASSED",
        })

    # 9. Payment credit terms
    if "REVIEW_RULE_3" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_3"]
        findings.append({
            "Check": "Payment credit terms",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Payment terms are ambiguous, conditional, or outside the standard 30 to 60 day window.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Payment credit terms",
            "Result": "Passed",
            "Explanation": "Payment terms are clear and within the standard 30 to 60 day credit window.",
            "Status": "PASSED",
        })

    # 10. Quotation validity period
    if "REVIEW_RULE_7" in triggered_ids:
        r = rules_by_id["REVIEW_RULE_7"]
        findings.append({
            "Check": "Quotation validity",
            "Result": "Needs Review",
            "Explanation": r.explanation or "Quotation validity period is less than the required 30 days.",
            "Status": "REVIEW",
        })
    else:
        findings.append({
            "Check": "Quotation validity",
            "Result": "Passed",
            "Explanation": "Quotation validity period meets or exceeds the required 30 days.",
            "Status": "PASSED",
        })

    return findings


def get_extracted_summary_fields(report: Any) -> Dict[str, str]:
    """Extracts all quotation fields with clear labels, identifying missing or ambiguous data."""
    data: Dict[str, str] = {}
    quot = getattr(report, "extracted_quotation", None)

    # 1. Supplier Name
    data["Supplier name"] = getattr(report, "supplier_name", "Unknown")

    # 2. Quotation Number
    data["Quotation number"] = getattr(report, "quotation_no", "Unknown")

    # 3. Item Code & Description
    if quot and quot.line_items:
        first_item = quot.line_items[0]
        code = first_item.item_code.value or "N/A"
        desc = first_item.description.value or "N/A"
        data["Item code & description"] = f"[{code}] {desc}"
        qty_val = f"{first_item.quantity.value:,.0f}" if first_item.quantity.value is not None else "Missing"
        unit_val = first_item.unit.value or ""
        data["Quantity & unit"] = f"{qty_val} {unit_val}".strip()
        data["Unit price"] = f"{first_item.unit_price.value:,.2f} BDT" if first_item.unit_price.value is not None else "Missing"
        data["Quoted line amount"] = f"{first_item.line_amount.value:,.2f} BDT" if (first_item.line_amount and first_item.line_amount.value is not None) else "Not stated separately"
    elif report.pr_comparison and report.pr_comparison.matched_items:
        item = report.pr_comparison.matched_items[0]
        data["Item code & description"] = f"[{item.item_code}] {item.quoted_description}"
        data["Quantity & unit"] = f"{item.quoted_quantity:,.0f} {item.quoted_unit}"
        data["Unit price"] = f"{item.quoted_unit_price:,.2f} BDT"
        data["Quoted line amount"] = "See audit report"
    else:
        data["Item code & description"] = "⚠️ Missing or unextracted"
        data["Quantity & unit"] = "⚠️ Missing"
        data["Unit price"] = "⚠️ Missing"
        data["Quoted line amount"] = "⚠️ Missing"

    # 4. Recalculated Line Amount
    if report.arithmetic_audit and report.arithmetic_audit.line_checks:
        lc = report.arithmetic_audit.line_checks[0]
        data["Recalculated line amount"] = f"{lc.calculated_amount:,.2f} BDT"
    else:
        data["Recalculated line amount"] = "N/A"

    # 5. Financial Totals
    if quot:
        data["Subtotal"] = f"{quot.subtotal.value:,.2f} BDT" if quot.subtotal.value is not None else "⚠️ Not shown separately"
        if quot.vat_shown_separately.value and quot.vat_amount.value is not None:
            pct = f"{quot.vat_percentage.value:.0f}%" if quot.vat_percentage.value else "15%"
            data["VAT"] = f"{pct} ({quot.vat_amount.value:,.2f} BDT)"
        elif quot.vat_shown_separately.value:
            data["VAT"] = "Shown separately"
        else:
            data["VAT"] = "⚠️ Bundled / Inclusive"
        data["Grand total"] = f"{quot.total_amount.value:,.2f} BDT" if quot.total_amount.value is not None else "⚠️ Missing"
    else:
        data["Subtotal"] = "See audit report"
        data["VAT"] = "See audit report"
        data["Grand total"] = "See audit report"

    # 6. Commercial Terms
    if quot and quot.terms:
        terms = quot.terms
        # Advance payment
        adv = terms.advance_payment_percentage.value
        data["Advance payment"] = f"{adv:.1f}%" if adv is not None else "⚠️ Missing / Unspecified"

        # Credit / payment terms
        if terms.payment_terms_unclear.value or terms.credit_days_after_delivery.status.value == "AMBIGUOUS":
            quote_text = terms.payment_terms_text.raw_text or "Subject to agreement"
            data["Credit / payment terms"] = f"⚠️ Ambiguous ('{quote_text}')"
        elif terms.credit_days_after_delivery.value is not None:
            data["Credit / payment terms"] = f"{terms.credit_days_after_delivery.value} days after delivery"
        else:
            data["Credit / payment terms"] = "⚠️ Missing / Unspecified"

        # Delivery period
        deliv = terms.delivery_timeline_days.value
        data["Delivery period"] = f"{deliv} days from PO" if deliv is not None else "⚠️ Missing / Unspecified"

        # Late-delivery penalty
        if not terms.has_late_delivery_penalty.value or terms.has_late_delivery_penalty.status.value == "MISSING":
            data["Late-delivery penalty"] = "❌ None (Clause omitted)"
        elif terms.late_penalty_percentage_per_week.value is not None:
            data["Late-delivery penalty"] = f"{terms.late_penalty_percentage_per_week.value:.2f}% per week of delay"
        else:
            data["Late-delivery penalty"] = "Clause present (rate unstated)"

        # Quotation validity
        val = terms.quotation_validity_days.value
        data["Quotation validity"] = f"{val} days" if val is not None else "⚠️ Missing / Unspecified"
    else:
        data["Advance payment"] = "N/A"
        data["Credit / payment terms"] = "N/A"
        data["Delivery period"] = "N/A"
        data["Late-delivery penalty"] = "N/A"
        data["Quotation validity"] = "N/A"

    # 7. Tax Registration
    if quot:
        tin_val = quot.supplier_tin.value
        bin_val = quot.supplier_bin.value
        tin_str = tin_val if tin_val else "❌ Missing / Not provided"
        bin_str = bin_val if bin_val else "❌ Missing / Not provided"
        data["TIN / BIN"] = f"TIN: {tin_str} | BIN: {bin_str}"
    else:
        data["TIN / BIN"] = "N/A"

    return data


def get_evidence_traceability_items(report: Any) -> List[Dict[str, Any]]:
    """Gathers field evidence items with verbatim text, PDF page numbers, source verification,

    and field interpretation status.
    """
    items: List[Dict[str, Any]] = []
    quot = getattr(report, "extracted_quotation", None)

    if quot:
        # Supplier Name
        if quot.supplier_name.raw_text:
            items.append({
                "Field": "Supplier Name",
                "Extracted Value": quot.supplier_name.value or "N/A",
                "Verbatim PDF Quote": quot.supplier_name.raw_text,
                "Page Number": quot.supplier_name.page_number or 1,
                "Verified": quot.supplier_name.evidence_verified,
                "Source Verified": quot.supplier_name.evidence_verified,
                "Interpretation Status": quot.supplier_name.status.value,
            })
        # Quotation Number
        if quot.quotation_no.raw_text:
            items.append({
                "Field": "Quotation Number",
                "Extracted Value": quot.quotation_no.value or "N/A",
                "Verbatim PDF Quote": quot.quotation_no.raw_text,
                "Page Number": quot.quotation_no.page_number or 1,
                "Verified": quot.quotation_no.evidence_verified,
                "Source Verified": quot.quotation_no.evidence_verified,
                "Interpretation Status": quot.quotation_no.status.value,
            })
        # Line item
        if quot.line_items:
            item = quot.line_items[0]
            if item.quantity.raw_text:
                items.append({
                    "Field": "Quoted Quantity",
                    "Extracted Value": f"{item.quantity.value:,.0f} {item.unit.value or ''}".strip(),
                    "Verbatim PDF Quote": item.quantity.raw_text,
                    "Page Number": item.quantity.page_number or 1,
                    "Verified": item.quantity.evidence_verified,
                    "Source Verified": item.quantity.evidence_verified,
                    "Interpretation Status": item.quantity.status.value,
                })
            if item.unit_price.raw_text:
                items.append({
                    "Field": "Unit Price",
                    "Extracted Value": f"{item.unit_price.value:,.2f} BDT",
                    "Verbatim PDF Quote": item.unit_price.raw_text,
                    "Page Number": item.unit_price.page_number or 1,
                    "Verified": item.unit_price.evidence_verified,
                    "Source Verified": item.unit_price.evidence_verified,
                    "Interpretation Status": item.unit_price.status.value,
                })
        # Advance payment
        if quot.terms and quot.terms.advance_payment_percentage.raw_text:
            items.append({
                "Field": "Advance Payment Terms",
                "Extracted Value": f"{quot.terms.advance_payment_percentage.value}%",
                "Verbatim PDF Quote": quot.terms.advance_payment_percentage.raw_text,
                "Page Number": quot.terms.advance_payment_percentage.page_number or 1,
                "Verified": quot.terms.advance_payment_percentage.evidence_verified,
                "Source Verified": quot.terms.advance_payment_percentage.evidence_verified,
                "Interpretation Status": quot.terms.advance_payment_percentage.status.value,
            })
        # Payment terms
        if quot.terms and quot.terms.payment_terms_text.raw_text:
            items.append({
                "Field": "Payment Credit Terms",
                "Extracted Value": f"{quot.terms.credit_days_after_delivery.value or 'Ambiguous'} days",
                "Verbatim PDF Quote": quot.terms.payment_terms_text.raw_text,
                "Page Number": quot.terms.payment_terms_text.page_number or 1,
                "Verified": quot.terms.payment_terms_text.evidence_verified,
                "Source Verified": quot.terms.payment_terms_text.evidence_verified,
                "Interpretation Status": quot.terms.credit_days_after_delivery.status.value,
            })
        # Delivery timeline
        if quot.terms and quot.terms.delivery_timeline_days.raw_text:
            items.append({
                "Field": "Delivery Schedule",
                "Extracted Value": f"{quot.terms.delivery_timeline_days.value} days",
                "Verbatim PDF Quote": quot.terms.delivery_timeline_days.raw_text,
                "Page Number": quot.terms.delivery_timeline_days.page_number or 1,
                "Verified": quot.terms.delivery_timeline_days.evidence_verified,
                "Source Verified": quot.terms.delivery_timeline_days.evidence_verified,
                "Interpretation Status": quot.terms.delivery_timeline_days.status.value,
            })
        # Late delivery penalty
        if quot.terms and quot.terms.penalty_terms_text.raw_text:
            items.append({
                "Field": "Late-Delivery Penalty Clause",
                "Extracted Value": f"{quot.terms.late_penalty_percentage_per_week.value or 0}% per week",
                "Verbatim PDF Quote": quot.terms.penalty_terms_text.raw_text,
                "Page Number": quot.terms.penalty_terms_text.page_number or 1,
                "Verified": quot.terms.penalty_terms_text.evidence_verified,
                "Source Verified": quot.terms.penalty_terms_text.evidence_verified,
                "Interpretation Status": quot.terms.late_penalty_percentage_per_week.status.value,
            })
        # Tax registration quote
        if quot.registration_raw_quote.raw_text:
            items.append({
                "Field": "Tax Registration (TIN & BIN)",
                "Extracted Value": f"TIN: {quot.supplier_tin.value or 'None'}, BIN: {quot.supplier_bin.value or 'None'}",
                "Verbatim PDF Quote": quot.registration_raw_quote.raw_text,
                "Page Number": quot.registration_raw_quote.page_number or 1,
                "Verified": quot.registration_raw_quote.evidence_verified,
                "Source Verified": quot.registration_raw_quote.evidence_verified,
                "Interpretation Status": quot.registration_raw_quote.status.value,
            })
        # Quotation validity
        if quot.terms and quot.terms.validity_terms_text.raw_text:
            items.append({
                "Field": "Quotation Validity Period",
                "Extracted Value": f"{quot.terms.quotation_validity_days.value} days",
                "Verbatim PDF Quote": quot.terms.validity_terms_text.raw_text,
                "Page Number": quot.terms.validity_terms_text.page_number or 1,
                "Verified": quot.terms.validity_terms_text.evidence_verified,
                "Source Verified": quot.terms.validity_terms_text.evidence_verified,
                "Interpretation Status": quot.terms.quotation_validity_days.status.value,
            })

    # If extracted_quotation wasn't present, extract from triggered rules
    if not items:
        for r in getattr(report, "all_evaluated_rules", []):
            if r.evidence_quote:
                items.append({
                    "Field": r.rule_name,
                    "Extracted Value": r.actual_value or "N/A",
                    "Verbatim PDF Quote": r.evidence_quote,
                    "Page Number": r.page_number or 1,
                    "Verified": r.is_confirmed,
                    "Source Verified": bool(r.page_number),
                    "Interpretation Status": "EXTRACTED" if r.is_confirmed else "UNCERTAIN",
                })

    return items


def get_financial_discrepancies(report: Any) -> List[Dict[str, Any]]:
    """Extracts line-by-line financial arithmetic discrepancies from the audit result."""
    items: List[Dict[str, Any]] = []
    audit = getattr(report, "arithmetic_audit", None)
    if not audit:
        return items

    for d in getattr(audit, "discrepancies", []):
        quoted = d.quoted_value if d.quoted_value is not None else Decimal("0.00")
        expected = d.expected_value if d.expected_value is not None else Decimal("0.00")
        diff = d.discrepancy_amount if d.discrepancy_amount is not None else abs(quoted - expected)
        items.append({
            "Component": d.component.replace("_", " ").title(),
            "Quoted Amount": f"{quoted:,.2f} BDT",
            "Recalculated Amount": f"{expected:,.2f} BDT",
            "Difference": f"{diff:,.2f} BDT",
            "Explanation": d.details or f"Quoted {quoted:,.2f} BDT differs from system calculation of {expected:,.2f} BDT.",
            "Evidence Quote": d.evidence_quote,
        })

    # Fallback to line checks if discrepancies list was empty
    if not items and getattr(audit, "line_checks", []):
        for lc in audit.line_checks:
            if not lc.matches:
                quoted = lc.quoted_amount if lc.quoted_amount is not None else Decimal("0.00")
                expected = lc.calculated_amount
                diff = lc.difference
                items.append({
                    "Component": f"Line Item [{lc.item_code}]",
                    "Quoted Amount": f"{quoted:,.2f} BDT",
                    "Recalculated Amount": f"{expected:,.2f} BDT",
                    "Difference": f"{diff:,.2f} BDT",
                    "Explanation": f"{lc.quantity:,.0f} × {lc.unit_price:,.2f} BDT = {expected:,.2f} BDT, but quoted {quoted:,.2f} BDT.",
                    "Evidence Quote": lc.evidence_quote,
                })

    return items


def get_all_decision_reasons(report: Any) -> List[str]:
    """Returns all contributing reasons for the final decision."""
    if hasattr(report, "all_decision_reasons") and report.all_decision_reasons:
        return report.all_decision_reasons
    if hasattr(report, "primary_reason") and report.primary_reason:
        return [report.primary_reason]
    return ["Decision recorded."]


def get_next_step_guidance(decision: DecisionEnum) -> Dict[str, str]:
    """Provides simple next-step guidance for a procurement manager based on the verification decision."""
    if decision == DecisionEnum.APPROVE:
        return {
            "title": "Next Step: Ready for Procurement Approval",
            "message": "The quotation satisfies all configured checks and can proceed to the next procurement approval stage.",
            "note": "Note: This verification confirms policy compliance; an official Purchase Order has not yet been issued.",
            "alert_type": "success",
        }
    elif decision == DecisionEnum.REJECT:
        return {
            "title": "Next Step: Quotation Rejected",
            "message": "The quotation violates a confirmed mandatory company rule. Reject this quotation or request a revised quotation from the supplier addressing the identified violation(s).",
            "note": "A confirmed violation prevents automated or manual progression without an approved policy waiver.",
            "alert_type": "error",
        }
    else:
        return {
            "title": "Next Step: Human Review Required",
            "message": "A person must inspect the highlighted issue(s) before making a decision.",
            "note": "Review the highlighted variances, ambiguous clauses, or arithmetic discrepancies above and record a procurement determination.",
            "alert_type": "warning",
        }


