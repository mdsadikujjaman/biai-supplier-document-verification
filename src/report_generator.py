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


def generate_individual_excel_report(report: DocumentVerificationReport) -> bytes:
    """Generates an executive, evidence-backed audit report in Excel (.xlsx) format for a single supplier pack.

    Worksheets:
    1. Verification Summary: High-level document audit metadata and decision.
    2. Extracted Details: Line items, financial sums, terms, and tax registration figures.
    3. Decision Findings: Specific policy compliance violations and review triggers.
    4. Financial Discrepancies: Arithmetic comparison between quoted and calculated amounts.
    5. Supporting Evidence: Verbatim citations, page numbers, source verification, and interpretation status.
    """
    import pandas as pd
    from src.app_helpers import (
        get_all_decision_reasons,
        get_evidence_traceability_items,
        get_extracted_summary_fields,
        get_financial_discrepancies,
    )

    output = io.BytesIO()

    # Sheet 1: Verification Summary
    summary_rows = [
        {"Property": "Document Name", "Value": report.document_name},
        {"Property": "Document SHA-256 Hash", "Value": report.document_hash},
        {"Property": "Supplier Name", "Value": report.supplier_name},
        {"Property": "Quotation Number", "Value": report.quotation_no},
        {"Property": "Matched PR Item(s)", "Value": report.matched_pr_item or "None"},
        {"Property": "Final System Decision", "Value": report.final_decision.value},
        {"Property": "Rejection Confirmed", "Value": "Yes" if report.rejection_confirmed else "No"},
        {"Property": "Primary Decision Finding", "Value": report.primary_reason},
        {"Property": "Total Decision Issues", "Value": len(report.all_decision_reasons) if report.all_decision_reasons else 1},
        {"Property": "Triggered Rules Count", "Value": len(report.triggered_rules)},
        {"Property": "Processing Time (ms)", "Value": f"{report.processing_time_ms:.1f}"},
        {"Property": "Audit Timestamp (UTC)", "Value": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())},
    ]
    df_summary = pd.DataFrame(summary_rows)

    # Sheet 2: Extracted Details
    extracted_fields = get_extracted_summary_fields(report)
    df_extracted = pd.DataFrame([
        {"Quotation Field / Clause": k, "Extracted Value / Status": v}
        for k, v in extracted_fields.items()
    ])

    # Sheet 3: Decision Findings
    all_reasons = get_all_decision_reasons(report)
    df_findings = pd.DataFrame([
        {"Finding #": idx, "Decision Finding / Reason Description": reason}
        for idx, reason in enumerate(all_reasons, start=1)
    ])

    # Sheet 4: Financial Discrepancies
    discrepancies = get_financial_discrepancies(report)
    if discrepancies:
        df_discrepancies = pd.DataFrame([
            {
                "Component": d["Component"],
                "Supplier-Quoted Amount": d["Quoted Amount"],
                "System-Recalculated Amount": d["Recalculated Amount"],
                "Absolute Difference": d["Difference"],
                "Calculation Explanation": d["Explanation"],
                "Evidence Quote": d.get("Evidence Quote", ""),
            }
            for d in discrepancies
        ])
    else:
        df_discrepancies = pd.DataFrame([
            {
                "Component": "All Components",
                "Supplier-Quoted Amount": "N/A",
                "System-Recalculated Amount": "N/A",
                "Absolute Difference": "0.00 BDT",
                "Calculation Explanation": "No financial or arithmetic discrepancies detected.",
                "Evidence Quote": "N/A",
            }
        ])

    # Sheet 5: Supporting Evidence
    evidence_items = get_evidence_traceability_items(report)
    if evidence_items:
        df_evidence = pd.DataFrame([
            {
                "Field / Clause": it["Field"],
                "Extracted Value": it["Extracted Value"],
                "Verbatim PDF Quote": it["Verbatim PDF Quote"] or "N/A",
                "Page Number": it["Page Number"],
                "Source Verified on Page": "Yes" if it.get("Source Verified") else "No",
                "Field Interpretation Status": it.get("Interpretation Status", "EXTRACTED"),
            }
            for it in evidence_items
        ])
    else:
        df_evidence = pd.DataFrame([
            {
                "Field / Clause": "N/A",
                "Extracted Value": "N/A",
                "Verbatim PDF Quote": "No evidence items recorded.",
                "Page Number": 1,
                "Source Verified on Page": "No",
                "Field Interpretation Status": "MISSING",
            }
        ])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Verification Summary", index=False)
        df_extracted.to_excel(writer, sheet_name="Extracted Details", index=False)
        df_findings.to_excel(writer, sheet_name="Decision Findings", index=False)
        df_discrepancies.to_excel(writer, sheet_name="Financial Discrepancies", index=False)
        df_evidence.to_excel(writer, sheet_name="Supporting Evidence", index=False)

    output.seek(0)
    return output.getvalue()


def generate_batch_excel_summary(reports: List[DocumentVerificationReport]) -> bytes:
    """Exports batch verification reports into an Excel (.xlsx) workbook with multiple worksheets.

    Worksheets:
    1. Verification Summary: One row per audited document.
    2. Extracted Quotations: Key commercial, pricing, and terms figures across documents.
    3. Decision Findings: Specific violations and review triggers per document.
    4. Financial Discrepancies: Arithmetic discrepancies across all audited documents.
    5. Supporting Evidence: Verbatim citations and layout verification per document.
    """
    import pandas as pd
    from src.app_helpers import (
        get_all_decision_reasons,
        get_evidence_traceability_items,
        get_extracted_summary_fields,
        get_financial_discrepancies,
    )

    output = io.BytesIO()

    # Sheet 1: Verification Summary
    summary_data = []
    for r in reports:
        all_reasons_str = " | ".join(r.all_decision_reasons) if r.all_decision_reasons else r.primary_reason
        summary_data.append({
            "Document Name": r.document_name,
            "Supplier Name": r.supplier_name,
            "Quotation No": r.quotation_no,
            "Matched PR Item": r.matched_pr_item or "N/A",
            "Final Decision": r.final_decision.value,
            "Rejection Confirmed": "Yes" if r.rejection_confirmed else "No",
            "Primary Reason": r.primary_reason,
            "All Decision Reasons": all_reasons_str,
            "Triggered Rules Count": len(r.triggered_rules),
            "Math Discrepancies Count": len(r.arithmetic_audit.discrepancies),
            "Processing Time (ms)": r.processing_time_ms,
        })
    df_summary = pd.DataFrame(summary_data)

    # Sheet 2: Extracted Quotations
    extracted_rows = []
    for r in reports:
        fields = get_extracted_summary_fields(r)
        extracted_rows.append({
            "Document Name": r.document_name,
            "Supplier Name": r.supplier_name,
            "Quotation No": r.quotation_no,
            "Item Code & Description": fields.get("Item code & description", "N/A"),
            "Quantity & Unit": fields.get("Quantity & unit", "N/A"),
            "Unit Price": fields.get("Unit price", "N/A"),
            "Quoted Line Amount": fields.get("Quoted line amount", "N/A"),
            "Recalculated Line Amount": fields.get("Recalculated line amount", "N/A"),
            "Subtotal": fields.get("Subtotal", "N/A"),
            "VAT": fields.get("VAT", "N/A"),
            "Grand Total": fields.get("Grand total", "N/A"),
            "Advance Payment": fields.get("Advance payment", "N/A"),
            "Credit Terms": fields.get("Credit / payment terms", "N/A"),
            "Delivery Period": fields.get("Delivery period", "N/A"),
            "Late Penalty": fields.get("Late-delivery penalty", "N/A"),
            "Quotation Validity": fields.get("Quotation validity", "N/A"),
            "TIN / BIN": fields.get("TIN / BIN", "N/A"),
        })
    df_extracted = pd.DataFrame(extracted_rows)

    # Sheet 3: Decision Findings
    findings_data = []
    for r in reports:
        reasons = get_all_decision_reasons(r)
        for idx, reason in enumerate(reasons, start=1):
            findings_data.append({
                "Document Name": r.document_name,
                "Supplier Name": r.supplier_name,
                "Quotation No": r.quotation_no,
                "Final Decision": r.final_decision.value,
                "Finding Index": idx,
                "Reason Description": reason,
            })
    df_findings = pd.DataFrame(findings_data)

    # Sheet 4: Financial Discrepancies
    discrepancies_data = []
    for r in reports:
        discs = get_financial_discrepancies(r)
        for d in discs:
            discrepancies_data.append({
                "Document Name": r.document_name,
                "Supplier Name": r.supplier_name,
                "Component": d["Component"],
                "Supplier-Quoted Amount": d["Quoted Amount"],
                "System-Recalculated Amount": d["Recalculated Amount"],
                "Absolute Difference": d["Difference"],
                "Calculation Explanation": d["Explanation"],
                "Evidence Quote": d.get("Evidence Quote", ""),
            })
    df_discrepancies = pd.DataFrame(discrepancies_data)

    # Sheet 5: Supporting Evidence
    evidence_data = []
    for r in reports:
        ev_items = get_evidence_traceability_items(r)
        for it in ev_items:
            evidence_data.append({
                "Document Name": r.document_name,
                "Supplier Name": r.supplier_name,
                "Field / Clause": it["Field"],
                "Extracted Value": it["Extracted Value"],
                "Verbatim PDF Quote": it["Verbatim PDF Quote"] or "N/A",
                "Page Number": it["Page Number"],
                "Source Verified on Page": "Yes" if it.get("Source Verified") else "No",
                "Field Interpretation Status": it.get("Interpretation Status", "EXTRACTED"),
            })
    df_evidence = pd.DataFrame(evidence_data)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not df_summary.empty:
            df_summary.to_excel(writer, sheet_name="Verification Summary", index=False)
        else:
            pd.DataFrame({"Message": ["No reports to display."]}).to_excel(writer, sheet_name="Verification Summary", index=False)

        if not df_extracted.empty:
            df_extracted.to_excel(writer, sheet_name="Extracted Quotations", index=False)
        else:
            pd.DataFrame({"Message": ["No extracted details available."]}).to_excel(writer, sheet_name="Extracted Quotations", index=False)

        if not df_findings.empty:
            df_findings.to_excel(writer, sheet_name="Decision Findings", index=False)
        else:
            pd.DataFrame({"Message": ["No decision findings recorded."]}).to_excel(writer, sheet_name="Decision Findings", index=False)

        if not df_discrepancies.empty:
            df_discrepancies.to_excel(writer, sheet_name="Financial Discrepancies", index=False)
        else:
            pd.DataFrame({"Message": ["No financial discrepancies detected across batch."]}).to_excel(writer, sheet_name="Financial Discrepancies", index=False)

        if not df_evidence.empty:
            df_evidence.to_excel(writer, sheet_name="Supporting Evidence", index=False)
        else:
            pd.DataFrame({"Message": ["No supporting evidence records available."]}).to_excel(writer, sheet_name="Supporting Evidence", index=False)

    output.seek(0)
    return output.getvalue()


def generate_benchmark_excel_report(bench_data: dict) -> bytes:
    """Exports benchmark evaluation metrics into an Excel (.xlsx) workbook."""
    import pandas as pd

    output = io.BytesIO()

    # Sheet 1: Benchmark Summary
    summary = bench_data.get("benchmark_summary", {})
    summary_rows = [
        {"Metric": "Total Documents Evaluated", "Value": summary.get("total_documents", 0)},
        {"Metric": "Passed Documents", "Value": summary.get("passed_documents", 0)},
        {"Metric": "Failed Documents", "Value": summary.get("failed_documents", 0)},
        {"Metric": "Accuracy Percentage", "Value": f"{summary.get('accuracy_percentage', 0.0):.1f}%"},
        {"Metric": "False Approvals (Safety-Critical)", "Value": summary.get("false_approvals", 0)},
        {"Metric": "False Rejections", "Value": summary.get("false_rejections", 0)},
        {"Metric": "Mean Processing Latency (ms)", "Value": f"{summary.get('mean_latency_ms', 0.0):.2f}"},
    ]
    df_summary = pd.DataFrame(summary_rows)

    # Sheet 2: Document Results
    docs = bench_data.get("document_results", [])
    doc_rows = []
    for d in docs:
        doc_rows.append({
            "Document": d.get("document_name", "N/A"),
            "Supplier Name": d.get("supplier_name", "N/A"),
            "Expected Decision": d.get("expected_decision", "N/A"),
            "Actual Decision": d.get("actual_decision", "N/A"),
            "Passed": "YES" if d.get("passed") else "NO",
            "Latency (ms)": f"{d.get('processing_time_ms', 0.0):.2f}",
            "Primary Finding": d.get("primary_reason", "N/A"),
            "Ground Truth Notes": d.get("notes", "N/A"),
        })
    df_docs = pd.DataFrame(doc_rows)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Benchmark Summary", index=False)
        df_docs.to_excel(writer, sheet_name="Document Evaluations", index=False)

    output.seek(0)
    return output.getvalue()



