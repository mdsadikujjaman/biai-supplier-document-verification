import csv
from decimal import Decimal
import io
import json
import time
from typing import List, Optional

from src.models.schemas import (
    DecisionEnum,
    DocumentVerificationReport,
    RuleCategory,
    RuleStatus,
)


def generate_individual_markdown_report(report: DocumentVerificationReport) -> str:
    """Generates an executive, evidence-backed audit report in Markdown for a single supplier pack."""
    decision_badge = {
        DecisionEnum.APPROVE: "🟢 **APPROVE**",
        DecisionEnum.REJECT: "🔴 **REJECT**",
        DecisionEnum.NEEDS_HUMAN_REVIEW: "🟡 **NEEDS HUMAN REVIEW**",
    }.get(report.final_decision, str(report.final_decision))

    lines = [
        f"# Supplier Quotation Verification Audit Report",
        f"",
        f"**Document Name:** `{report.document_name}`  ",
        f"**Document SHA-256 Hash:** `{report.document_hash}`  ",
        f"**Audit Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Processing Time:** `{report.processing_time_ms:.1f} ms`  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Verification Decision",
        f"",
        f"- **Supplier Name:** {report.supplier_name}",
        f"- **Quotation Number:** {report.quotation_no}",
        f"- **Matched PR Item(s):** `{report.matched_pr_item or 'None'}`",
        f"- **Final System Decision:** {decision_badge}",
        f"- **Rejection Confirmed:** `{'Yes' if report.rejection_confirmed else 'No'}`",
        f"- **Primary Finding:** {report.primary_reason}",
        f"",
        f"---",
        f"",
        f"## 2. Triggered Violations & Review Findings",
        f"",
    ]

    if report.triggered_rules:
        lines.append("| Rule ID | Rule Name | Category | Status | Actual Value | Expected Condition | Evidence Quote | Page |")
        lines.append("| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: |")
        for r in report.triggered_rules:
            page_str = str(r.page_number) if r.page_number else "N/A"
            lines.append(
                f"| `{r.rule_id}` | {r.rule_name} | `{r.category.value}` | **{r.status.value}** | "
                f"`{r.actual_value or 'N/A'}` | `{r.expected_condition or 'N/A'}` | \"{r.evidence_quote or 'N/A'}\" | {page_str} |"
            )
    else:
        lines.append("*No policy violations or review triggers were activated.*")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Financial & Arithmetic Audit",
        f"",
        f"- **Line Items Calculation Matches:** `{'✅ PASS' if report.arithmetic_audit.line_calculations_match else '❌ DISCREPANCY'}`",
        f"- **Subtotal Matches Sum of Lines:** `{'✅ PASS' if report.arithmetic_audit.subtotal_matches_lines else '❌ DISCREPANCY'}`",
        f"- **VAT Calculated at 15% Matches:** `{'✅ PASS' if report.arithmetic_audit.vat_matches_subtotal_15pct else '❌ DISCREPANCY'}`",
        f"- **Total Amount Matches Sum:** `{'✅ PASS' if report.arithmetic_audit.total_matches_sum else '❌ DISCREPANCY'}`",
        f"- **VAT Shown Separately at 15%:** `{'✅ Yes' if report.arithmetic_audit.vat_shown_separately else '⚠️ No / Bundled'}`",
        f"",
    ])

    if report.arithmetic_audit.line_checks:
        lines.append("### Line Item Calculations")
        lines.append("| Item Code | Quantity | Quoted Unit Price | Quoted Line Total | Recalculated Amount | Difference | Match |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for lc in report.arithmetic_audit.line_checks:
            match_str = "✅ PASS" if lc.matches else "❌ DISCREPANCY"
            diff_str = f"{lc.difference:,.2f}" if lc.difference else "0.00"
            quoted_str = f"{lc.quoted_amount:,.2f}" if lc.quoted_amount else "N/A"
            lines.append(
                f"| `{lc.item_code}` | {lc.quantity:,.0f} | {lc.unit_price:,.2f} BDT | {quoted_str} BDT | "
                f"{lc.calculated_amount:,.2f} BDT | {diff_str} BDT | {match_str} |"
            )
        lines.append("")

    if report.arithmetic_audit.discrepancies:
        lines.append("### Arithmetic Discrepancies")
        for d in report.arithmetic_audit.discrepancies:
            lines.append(f"- **{d.component}:** Expected `{d.expected_value:,.2f}` BDT, Quoted `{d.quoted_value:,.2f}` BDT. Discrepancy: `{d.discrepancy_amount:,.2f}` BDT. Quote: \"{d.evidence_quote}\"")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 4. Purchase Request Alignment Audit",
        f"",
    ])

    if report.pr_comparison and report.pr_comparison.matched_items:
        lines.append("| Item Code | PR Req Qty | Quoted Qty | Qty Variance | PR Max Price | Quoted Price | Price Variance | Ceiling (+3%) | Alignment |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for item in report.pr_comparison.matched_items:
            align_str = "✅ COMPLIANT"
            if item.price_exceeds_rejection_ceiling:
                align_str = "🔴 EXCEEDS +3% CEILING"
            elif item.price_is_within_review_band:
                align_str = "🟡 REVIEW BAND (<= +3%)"
            elif not item.quantity_within_tolerance:
                align_str = "🟡 QTY VARIANCE (> 5%)"

            lines.append(
                f"| `{item.item_code}` | {item.requested_quantity:,.0f} {item.pr_unit} | {item.quoted_quantity:,.0f} {item.quoted_unit} | "
                f"{item.quantity_variance_pct:+,.2f}% | {item.max_unit_price:,.2f} BDT | {item.quoted_unit_price:,.2f} BDT | "
                f"{item.price_variance_pct:+,.2f}% | {item.price_rejection_ceiling:,.2f} BDT | {align_str} |"
            )
        lines.append("")
    else:
        lines.append("*No matched PR line items found or comparison was not generated.*")

    lines.extend([
        f"---",
        f"",
        f"## 5. Complete Company Business Rules Matrix",
        f"",
        f"| Rule ID | Rule Name | Category | Status | Actual Value | Expected Condition | Evidence Quotation |",
        f"| :--- | :--- | :--- | :---: | :--- | :--- | :--- |",
    ])

    for r in report.all_evaluated_rules:
        status_badge = "✅ PASS" if r.status == RuleStatus.PASS else ("❌ FAIL" if r.status == RuleStatus.FAIL else f"⚠️ {r.status.value}")
        lines.append(
            f"| `{r.rule_id}` | {r.rule_name} | `{r.category.value}` | {status_badge} | "
            f"`{r.actual_value or 'N/A'}` | `{r.expected_condition or 'N/A'}` | \"{r.evidence_quote or 'N/A'}\" |"
        )

    if report.extraction_uncertainties:
        lines.extend([
            f"",
            f"---",
            f"",
            f"## 6. Extraction Uncertainties & Ambiguities",
            f"",
        ])
        for u in report.extraction_uncertainties:
            lines.append(f"- **Field:** `{u.field_name}` | **Issue:** `{u.issue_type}` | **Details:** {u.details}")

    return "\n".join(lines)


def generate_individual_json_report(report: DocumentVerificationReport) -> str:
    """Serializes a DocumentVerificationReport into pretty-printed JSON."""
    return report.model_dump_json(indent=2)


def generate_batch_csv_summary(reports: List[DocumentVerificationReport]) -> str:
    """Exports batch verification results as a clean CSV table string."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Document Name",
        "Document SHA256",
        "Supplier Name",
        "Quotation Number",
        "Matched PR Item",
        "Final Decision",
        "Rejection Confirmed",
        "Primary Finding",
        "Triggered Rules Count",
        "Arithmetic Discrepancies Count",
        "Extraction Uncertainties Count",
        "Processing Time (ms)",
    ])

    for r in reports:
        writer.writerow([
            r.document_name,
            r.document_hash,
            r.supplier_name,
            r.quotation_no,
            r.matched_pr_item or "N/A",
            r.final_decision.value,
            "Yes" if r.rejection_confirmed else "No",
            r.primary_reason,
            len(r.triggered_rules),
            len(r.arithmetic_audit.discrepancies),
            len(r.extraction_uncertainties),
            f"{r.processing_time_ms:.1f}",
        ])

    return output.getvalue()


def generate_batch_markdown_summary(reports: List[DocumentVerificationReport]) -> str:
    """Generates a batch verification summary in Markdown format."""
    total = len(reports)
    approved = sum(1 for r in reports if r.final_decision == DecisionEnum.APPROVE)
    rejected = sum(1 for r in reports if r.final_decision == DecisionEnum.REJECT)
    reviews = sum(1 for r in reports if r.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW)

    lines = [
        "# Batch Supplier Verification Summary",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Total Documents Audited:** `{total}`  ",
        f"**Approved:** `{approved}` | **Rejected:** `{rejected}` | **Needs Human Review:** `{reviews}`  ",
        "",
        "| Document Name | Supplier Name | Quotation No | Matched Item | Final Decision | Primary Reason | Latency (ms) |",
        "| :--- | :--- | :---: | :---: | :---: | :--- | :---: |",
    ]

    for r in reports:
        status_badge = {
            DecisionEnum.APPROVE: "🟢 APPROVE",
            DecisionEnum.REJECT: "🔴 REJECT",
            DecisionEnum.NEEDS_HUMAN_REVIEW: "🟡 NEEDS REVIEW",
        }.get(r.final_decision, str(r.final_decision))

        lines.append(
            f"| `{r.document_name}` | {r.supplier_name} | `{r.quotation_no}` | "
            f"`{r.matched_pr_item or 'N/A'}` | **{status_badge}** | {r.primary_reason} | {r.processing_time_ms:.1f} |"
        )

    return "\n".join(lines)


def generate_batch_json_summary(reports: List[DocumentVerificationReport]) -> str:
    """Exports batch reports into a single JSON object array."""
    raw_list = [r.model_dump(mode="json") for r in reports]
    return json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_documents": len(reports),
        "reports": raw_list,
    }, indent=2)

