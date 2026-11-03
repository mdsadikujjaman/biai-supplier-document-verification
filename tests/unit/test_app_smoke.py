import json
import os
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
from src.models.schemas import DecisionEnum, RuleStatus
from src.report_generator import (
    generate_batch_csv_summary,
    generate_batch_json_summary,
    generate_batch_markdown_summary,
    generate_individual_json_report,
    generate_individual_markdown_report,
)


class MockUploadedFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data
        self.size = len(data)

    def getbuffer(self):
        return self._data


def test_smoke_upload_validation_and_cleanup():
    """Smoke test: validates PDF format, size checks, temp saving, and cleanup."""
    temp_dir = Path(tempfile.mkdtemp(prefix="smoke_test_"))
    try:
        # 1. Valid PDF simulation
        mock_pdf = MockUploadedFile("test_quote.pdf", b"%PDF-1.4 sample content")
        is_valid, err = validate_uploaded_pdf(mock_pdf.name, mock_pdf.size)
        assert is_valid is True
        assert err == ""

        saved_path = save_uploaded_stream_to_temp(mock_pdf, temp_dir)
        assert saved_path.exists()
        assert saved_path.read_bytes() == b"%PDF-1.4 sample content"

        # 2. Corrupted / Non-PDF simulation
        mock_docx = MockUploadedFile("test_doc.docx", b"word doc content")
        is_valid, err = validate_uploaded_pdf(mock_docx.name, mock_docx.size)
        assert is_valid is False
        assert "Only PDF files are supported" in err

        # 3. Empty PDF simulation
        mock_empty = MockUploadedFile("empty.pdf", b"")
        is_valid, err = validate_uploaded_pdf(mock_empty.name, mock_empty.size)
        assert is_valid is False
        assert "Empty file" in err

        # 4. Oversized PDF simulation (>20MB)
        mock_oversized = MockUploadedFile("large.pdf", b"x" * (21 * 1024 * 1024))
        is_valid, err = validate_uploaded_pdf(mock_oversized.name, mock_oversized.size)
        assert is_valid is False
        assert "File too large" in err
    finally:
        cleanup_directory(temp_dir)
        assert not temp_dir.exists()


def test_smoke_all_ten_sample_packs_batch():
    """Smoke test: executes batch processing on all 10 sample supplier packs."""
    engine = DecisionEngine()
    sample_files = [Path(f"sample_data/supplier-pack-{i:02d}.pdf") for i in range(1, 11)]

    reports = engine.verify_all(sample_files)
    assert len(reports) == 10

    # Ensure all 10 documents produce expected decision status
    decisions = [r.final_decision for r in reports]
    assert decisions.count(DecisionEnum.APPROVE) == 2
    assert decisions.count(DecisionEnum.REJECT) == 5
    assert decisions.count(DecisionEnum.NEEDS_HUMAN_REVIEW) == 3

    # Ensure evidence quotes and page numbers are present for each
    for rep in reports:
        assert rep.document_name.startswith("supplier-pack-")
        assert len(rep.document_hash) == 64
        assert rep.supplier_name and rep.supplier_name != "Unknown"
        assert rep.quotation_no and rep.quotation_no != "Unknown"
        assert rep.processing_time_ms > 0

        # Check all evaluated rules have valid structure
        assert len(rep.all_evaluated_rules) >= 12
        for r in rep.all_evaluated_rules:
            assert r.rule_id
            assert r.status in (RuleStatus.PASS, RuleStatus.FAIL, RuleStatus.UNCERTAIN, RuleStatus.NOT_APPLICABLE)


def test_smoke_download_generators():
    """Smoke test: confirms Markdown, JSON, and CSV exports generate valid formatted strings."""
    engine = DecisionEngine()
    reports = engine.verify_all([
        Path("sample_data/supplier-pack-01.pdf"),
        Path("sample_data/supplier-pack-02.pdf"),
        Path("sample_data/supplier-pack-03.pdf"),
    ])

    # 1. Individual Markdown and JSON
    ind_md = generate_individual_markdown_report(reports[0])
    assert "# Supplier Quotation Verification Audit Report" in ind_md
    assert "Padma Textile Mills Ltd" in ind_md
    assert "472.00 BDT" in ind_md

    ind_json = generate_individual_json_report(reports[0])
    parsed_json = json.loads(ind_json)
    assert parsed_json["document_name"] == "supplier-pack-01.pdf"
    assert parsed_json["final_decision"] == "APPROVE"

    # 2. Batch CSV, Markdown, and JSON
    batch_csv = generate_batch_csv_summary(reports)
    assert "Document Name,Document SHA256" in batch_csv
    assert "supplier-pack-01.pdf" in batch_csv
    assert "Padma Textile Mills Ltd" in batch_csv

    batch_md = generate_batch_markdown_summary(reports)
    assert "# Batch Supplier Verification Summary" in batch_md
    assert "**Total Documents Audited:** `3`" in batch_md

    batch_json = generate_batch_json_summary(reports)
    parsed_batch = json.loads(batch_json)
    assert parsed_batch["total_documents"] == 3


def test_smoke_deterministic_offline_operation(monkeypatch):
    """Smoke test: confirms the system operates 100% offline without any API keys."""
    # Ensure no API keys exist in the environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    engine = DecisionEngine()
    rep1 = engine.verify_document("sample_data/supplier-pack-01.pdf")
    assert rep1.final_decision == DecisionEnum.APPROVE

    rep3 = engine.verify_document("sample_data/supplier-pack-03.pdf")
    assert rep3.final_decision == DecisionEnum.REJECT


def test_smoke_corrupted_pdf_handling(tmp_path):
    """Smoke test: confirms corrupted PDFs produce clean human-review reports without crashing."""
    corrupt_file = tmp_path / "corrupted_pack.pdf"
    corrupt_file.write_bytes(b"Corrupted binary header %PDF-000 not valid")

    engine = DecisionEngine()
    report = engine.verify_document(corrupt_file)

    assert report.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW
    assert "Manual human" in report.primary_reason or "requires human review" in report.primary_reason
    assert report.rejection_confirmed is False
