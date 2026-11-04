import io
import json
from decimal import Decimal
from pathlib import Path
import openpyxl
import pytest

from src.decision_engine import DecisionEngine
from src.models.schemas import DecisionEnum
from src.report_generator import (
    generate_batch_csv_summary,
    generate_batch_excel_summary,
    generate_batch_json_summary,
    generate_batch_markdown_summary,
    generate_benchmark_excel_report,
    generate_individual_excel_report,
    generate_individual_json_report,
    generate_individual_markdown_report,
)


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine()


@pytest.fixture(scope="module")
def pack_reports(engine):
    return {
        "pack_01": engine.verify_document("sample_data/supplier-pack-01.pdf"),
        "pack_03": engine.verify_document("sample_data/supplier-pack-03.pdf"),
        "pack_08": engine.verify_document("sample_data/supplier-pack-08.pdf"),
        "pack_09": engine.verify_document("sample_data/supplier-pack-09.pdf"),
    }


# Test 1: Single-document Excel generation for clean approval (Pack 01)
def test_individual_excel_generation_clean_pack_01(pack_reports):
    rep = pack_reports["pack_01"]
    excel_bytes = generate_individual_excel_report(rep)

    assert excel_bytes is not None
    assert len(excel_bytes) > 2000

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    expected_sheets = [
        "Verification Summary",
        "Extracted Details",
        "Decision Findings",
        "Financial Discrepancies",
        "Supporting Evidence",
    ]
    assert wb.sheetnames == expected_sheets

    # Sheet 1: Summary
    ws_summary = wb["Verification Summary"]
    summary_dict = {row[0]: row[1] for row in ws_summary.iter_rows(values_only=True)}
    assert summary_dict["Document Name"] == "supplier-pack-01.pdf"
    assert summary_dict["Supplier Name"] == "Padma Textile Mills Ltd"
    assert summary_dict["Final System Decision"] == "APPROVE"

    # Sheet 2: Extracted Details
    ws_extracted = wb["Extracted Details"]
    extracted_dict = {row[0]: row[1] for row in ws_extracted.iter_rows(values_only=True)}
    assert "472.00 BDT" in str(extracted_dict.get("Unit price", ""))
    assert "12,000" in str(extracted_dict.get("Quantity & unit", ""))

    # Sheet 4: Discrepancies (Clean -> No discrepancies)
    ws_disc = wb["Financial Discrepancies"]
    disc_rows = list(ws_disc.iter_rows(values_only=True))
    assert len(disc_rows) >= 2
    assert "No financial or arithmetic discrepancies detected." in str(disc_rows[1])


# Test 2: Single-document Excel generation with financial discrepancies (Pack 09)
def test_individual_excel_financial_discrepancies_pack_09(pack_reports):
    rep_09 = pack_reports["pack_09"]
    excel_bytes = generate_individual_excel_report(rep_09)

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws_disc = wb["Financial Discrepancies"]
    header = [cell for cell in next(ws_disc.iter_rows(max_row=1, values_only=True))]
    assert "Supplier-Quoted Amount" in header
    assert "System-Recalculated Amount" in header
    assert "Absolute Difference" in header
    assert "Calculation Explanation" in header

    # Inspect discrepancy row
    data_rows = list(ws_disc.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 1
    found_2000_diff = any("2,000" in str(row) for row in data_rows)
    assert found_2000_diff is True

    # Sheet 3: Decision findings should capture both reasons
    ws_findings = wb["Decision Findings"]
    findings_texts = [str(row[1]) for row in ws_findings.iter_rows(min_row=2, values_only=True)]
    assert any("322,000" in text and "320,000" in text for text in findings_texts)
    assert any("30–90" in text or "30-90" in text for text in findings_texts)


# Test 3: Missing and ambiguous fields represented safely in single-document Excel (Pack 08 & Pack 09)
def test_individual_excel_missing_and_ambiguous_fields(pack_reports):
    # Pack 08 has missing TIN/BIN
    rep_08 = pack_reports["pack_08"]
    wb_08 = openpyxl.load_workbook(io.BytesIO(generate_individual_excel_report(rep_08)))
    ws_ext_08 = wb_08["Extracted Details"]
    ext_dict_08 = {row[0]: row[1] for row in ws_ext_08.iter_rows(values_only=True)}
    assert "Missing" in str(ext_dict_08.get("TIN / BIN", ""))

    # Pack 09 has ambiguous payment credit terms in evidence sheet
    rep_09 = pack_reports["pack_09"]
    wb_09 = openpyxl.load_workbook(io.BytesIO(generate_individual_excel_report(rep_09)))
    ws_ev_09 = wb_09["Supporting Evidence"]
    ev_rows = list(ws_ev_09.iter_rows(min_row=2, values_only=True))
    credit_row = next((r for r in ev_rows if "Credit" in str(r[0])), None)
    assert credit_row is not None
    # Source Verified = Yes, Interpretation Status = AMBIGUOUS
    assert credit_row[4] == "Yes"
    assert credit_row[5] == "AMBIGUOUS"


# Test 4: Multi-document batch Excel generation
def test_batch_excel_generation_multi_document(pack_reports):
    reports = list(pack_reports.values())
    batch_bytes = generate_batch_excel_summary(reports)

    assert batch_bytes is not None
    assert len(batch_bytes) > 4000

    wb = openpyxl.load_workbook(io.BytesIO(batch_bytes))
    expected_sheets = [
        "Verification Summary",
        "Extracted Quotations",
        "Decision Findings",
        "Financial Discrepancies",
        "Supporting Evidence",
    ]
    assert wb.sheetnames == expected_sheets

    # Sheet 1: All documents present in summary
    ws_summary = wb["Verification Summary"]
    doc_names = [row[0] for row in ws_summary.iter_rows(min_row=2, values_only=True)]
    assert "supplier-pack-01.pdf" in doc_names
    assert "supplier-pack-03.pdf" in doc_names
    assert "supplier-pack-08.pdf" in doc_names
    assert "supplier-pack-09.pdf" in doc_names

    # Sheet 2: Extracted quotations
    ws_ext = wb["Extracted Quotations"]
    ext_doc_names = [row[0] for row in ws_ext.iter_rows(min_row=2, values_only=True)]
    assert len(ext_doc_names) == 4

    # Sheet 4: Financial Discrepancies includes Pack 09
    ws_disc = wb["Financial Discrepancies"]
    disc_docs = [row[0] for row in ws_disc.iter_rows(min_row=2, values_only=True)]
    assert "supplier-pack-09.pdf" in disc_docs


# Test 5: Benchmark Excel generation
def test_benchmark_excel_generation():
    dummy_bench_data = {
        "benchmark_summary": {
            "total_documents": 10,
            "passed_documents": 10,
            "failed_documents": 0,
            "accuracy_percentage": 100.0,
            "false_approvals": 0,
            "false_rejections": 0,
            "mean_latency_ms": 6.25,
        },
        "document_results": [
            {
                "document_name": "supplier-pack-01.pdf",
                "supplier_name": "Padma Textile Mills Ltd",
                "expected_decision": "APPROVE",
                "actual_decision": "APPROVE",
                "passed": True,
                "processing_time_ms": 5.8,
                "primary_reason": "All rules passed.",
                "notes": "Pack 01 baseline match",
            }
        ],
    }

    bench_bytes = generate_benchmark_excel_report(dummy_bench_data)
    assert bench_bytes is not None
    assert len(bench_bytes) > 2000

    wb = openpyxl.load_workbook(io.BytesIO(bench_bytes))
    assert "Benchmark Summary" in wb.sheetnames
    assert "Document Evaluations" in wb.sheetnames

    ws_sum = wb["Benchmark Summary"]
    metrics_dict = {row[0]: row[1] for row in ws_sum.iter_rows(values_only=True)}
    assert metrics_dict["Accuracy Percentage"] == "100.0%"
    assert metrics_dict["Total Documents Evaluated"] == 10


# Test 6: Existing Markdown, JSON, and CSV exports continue to work
def test_existing_exports_unbroken(pack_reports):
    reports = list(pack_reports.values())
    rep = reports[0]

    # Individual Markdown
    md_ind = generate_individual_markdown_report(rep)
    assert "# Supplier Quotation Verification Audit Report" in md_ind
    assert rep.supplier_name in md_ind

    # Individual JSON
    json_ind = generate_individual_json_report(rep)
    parsed_json = json.loads(json_ind)
    assert parsed_json["document_name"] == rep.document_name
    assert parsed_json["final_decision"] == rep.final_decision.value

    # Batch CSV
    csv_batch = generate_batch_csv_summary(reports)
    lines = csv_batch.strip().split("\n")
    assert len(lines) == 5  # Header + 4 docs

    # Batch Markdown
    md_batch = generate_batch_markdown_summary(reports)
    assert "# Batch Supplier Verification Summary" in md_batch
    assert "**Total Documents Audited:** `4`" in md_batch

    # Batch JSON
    json_batch = generate_batch_json_summary(reports)
    parsed_batch = json.loads(json_batch)
    assert parsed_batch["total_documents"] == 4
