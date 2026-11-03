from pathlib import Path
import pytest
from src.app_helpers import (
    cleanup_directory,
    get_decision_color_theme,
    load_benchmark_report_json,
    load_benchmark_report_markdown,
    validate_uploaded_pdf,
)
from src.models.schemas import DecisionEnum


def test_validate_uploaded_pdf_valid():
    is_valid, err = validate_uploaded_pdf("supplier_quotation.pdf", 1024 * 50)
    assert is_valid is True
    assert err == ""


def test_validate_uploaded_pdf_non_pdf():
    is_valid, err = validate_uploaded_pdf("quotation.docx", 1024 * 50)
    assert is_valid is False
    assert "Only PDF files are supported" in err


def test_validate_uploaded_pdf_empty():
    is_valid, err = validate_uploaded_pdf("empty.pdf", 0)
    assert is_valid is False
    assert "Empty file" in err


def test_validate_uploaded_pdf_oversized():
    # 25 MB exceeds default 20 MB limit
    is_valid, err = validate_uploaded_pdf("huge.pdf", 25 * 1024 * 1024)
    assert is_valid is False
    assert "File too large" in err


def test_load_benchmark_reports():
    json_data = load_benchmark_report_json(Path("reports/evaluation_summary.json"))
    assert json_data is not None
    assert "benchmark_summary" in json_data
    assert json_data["benchmark_summary"]["accuracy_percentage"] == 100.0

    md_text = load_benchmark_report_markdown(Path("reports/audit_summary.md"))
    assert md_text is not None
    assert "# Supplier Document Verification System – Evaluation & Benchmark Report" in md_text


def test_get_decision_color_theme():
    t_app = get_decision_color_theme(DecisionEnum.APPROVE)
    assert "APPROVED" in t_app["badge"]

    t_rej = get_decision_color_theme(DecisionEnum.REJECT)
    assert "REJECTED" in t_rej["badge"]

    t_rev = get_decision_color_theme(DecisionEnum.NEEDS_HUMAN_REVIEW)
    assert "HUMAN REVIEW" in t_rev["badge"]


def test_cleanup_directory(tmp_path):
    sub = tmp_path / "temp_test_dir"
    sub.mkdir()
    (sub / "test.txt").write_text("sample")
    assert sub.exists()

    cleanup_directory(sub)
    assert not sub.exists()

