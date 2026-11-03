from pathlib import Path
import pytest
from src.config import settings
from src.ingestion import DocumentIngestionEngine
from src.pr_loader import PurchaseRequestLoader


def test_pr_loader():
    loader = PurchaseRequestLoader()
    pr = loader.load(settings.pr_file_path)

    assert pr.pr_number == "PR-2026-114"
    assert len(pr.items) == 5
    assert set(pr.items.keys()) == {"A", "B", "C", "D", "E"}

    item_c = pr.items["C"]
    assert item_c.description == "Polyester sewing thread, cone"
    assert item_c.unit == "cone"
    assert item_c.quantity_requested == 800
    assert item_c.maximum_unit_price == 210.00


def test_ingest_all_ten_sample_packs():
    ingestor = DocumentIngestionEngine()
    sample_files = sorted(list(settings.data_dir.glob("supplier-pack-*.pdf")))

    assert len(sample_files) == 10, f"Expected 10 packs, found {len(sample_files)}"

    for pdf_path in sample_files:
        doc = ingestor.ingest(pdf_path)
        assert doc.is_readable, f"Pack {pdf_path.name} failed readability check: {doc.error_message}"
        assert doc.page_count == 1
        assert len(doc.file_hash) == 64  # SHA-256
        assert len(doc.pages) == 1
        assert len(doc.full_text) > 100
        assert "QUOTATION" in doc.full_text


def test_ingest_missing_file():
    ingestor = DocumentIngestionEngine()
    doc = ingestor.ingest(Path("sample_data/non_existent.pdf"))
    assert not doc.is_readable
    assert "File not found" in (doc.error_message or "")


def test_ingest_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.pdf"
    empty_file.touch()

    ingestor = DocumentIngestionEngine()
    doc = ingestor.ingest(empty_file)
    assert not doc.is_readable
    assert "empty" in (doc.error_message or "").lower()

