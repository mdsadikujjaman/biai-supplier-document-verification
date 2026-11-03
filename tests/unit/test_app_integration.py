import importlib
import json
from pathlib import Path
import tempfile
import pytest
from src.app_helpers import (
    cleanup_directory,
    get_decision_color_theme,
    load_benchmark_report_json,
    load_benchmark_report_markdown,
    save_uploaded_stream_to_temp,
    validate_uploaded_pdf,
)
from src.decision_engine import DecisionEngine
from src.models.schemas import DecisionEnum
from src.report_generator import (
    generate_batch_csv_summary,
    generate_batch_json_summary,
    generate_batch_markdown_summary,
    generate_individual_json_report,
    generate_individual_markdown_report,
)


def test_app_module_importable():
    """Confirms app.py has valid syntax and imports all modules cleanly."""
    import app
    assert hasattr(app, "init_session_state")


def test_corrupted_pdf_handling(tmp_path):
    """Verifies that a corrupted or malformed PDF does not crash the verification pipeline."""
    corrupt_pdf = tmp_path / "corrupt_quotation.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4\nInvalid corrupted binary content here")

    engine = DecisionEngine()
    report = engine.verify_document(corrupt_pdf)

    # Must route to NEEDS_HUMAN_REVIEW and never crash
    assert report.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert "Manual human" in report.primary_reason or "requires human review" in report.primary_reason
    assert report.rejection_confirmed is False


def test_empty_pdf_handling(tmp_path):
    """Verifies that an empty PDF (0 bytes) is handled safely by the engine."""
    empty_pdf = tmp_path / "empty_quotation.pdf"
    empty_pdf.write_bytes(b"")

    engine = DecisionEngine()
    report = engine.verify_document(empty_pdf)

    assert report.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert report.rejection_confirmed is False


def test_batch_processing_and_export():
    """Tests batch processing of multiple files and subsequent export formatting."""
    engine = DecisionEngine()
    sample_files = [
        Path("sample_data/supplier-pack-01.pdf"),
        Path("sample_data/supplier-pack-02.pdf"),
        Path("sample_data/supplier-pack-03.pdf"),
    ]

    reports = engine.verify_all(sample_files)
    assert len(reports) == 3

    # Decisions must match expected ground truth
    assert reports[0].final_decision == DecisionEnum.APPROVE
    assert reports[1].final_decision == DecisionEnum.APPROVE
    assert reports[2].final_decision == DecisionEnum.REJECT

    # Test Batch Exports
    csv_out = generate_batch_csv_summary(reports)
    assert "supplier-pack-01.pdf" in csv_out
    assert "APPROVE" in csv_out
    assert "REJECT" in csv_out

    md_out = generate_batch_markdown_summary(reports)
    assert "**Total Documents Audited:** `3`" in md_out

    json_out = generate_batch_json_summary(reports)
    parsed = json.loads(json_out)
    assert parsed["total_documents"] == 3


def test_session_state_isolation():
    """Verifies that individual verification reports remain isolated and do not contaminate each other."""
    engine = DecisionEngine()
    rep_app = engine.verify_document("sample_data/supplier-pack-01.pdf")
    rep_rej = engine.verify_document("sample_data/supplier-pack-03.pdf")

    assert rep_app.final_decision == DecisionEnum.APPROVE
    assert rep_rej.final_decision == DecisionEnum.REJECT

    # Ensure metadata and audit instances are distinct
    assert rep_app.document_name != rep_rej.document_name
    assert rep_app.supplier_name != rep_rej.supplier_name
    assert rep_app.document_hash != rep_rej.document_hash
    assert rep_app.rejection_confirmed is False
    assert rep_rej.rejection_confirmed is True
