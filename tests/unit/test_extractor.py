from decimal import Decimal
from pathlib import Path
import pytest
from src.config import settings
from src.extractor import DeterministicExtractionProvider, ExtractionEngine, verify_text_on_page
from src.ingestion import DocumentIngestionEngine
from src.models.schemas import ExtractionStatus


@pytest.fixture
def ingestor():
    return DocumentIngestionEngine()


@pytest.fixture
def extractor():
    return ExtractionEngine(provider=DeterministicExtractionProvider())


def test_extract_all_ten_packs(ingestor, extractor):
    """Verify that all 10 supplier packs are cleanly extracted with verified evidence."""
    expected_data = [
        {"pack": 1, "supplier": "Padma Textile Mills Ltd", "item": "A", "qty": Decimal("12000"), "price": Decimal("472.00"), "penalty": True, "del_days": 24},
        {"pack": 2, "supplier": "Jamuna Trims and Accessories", "item": "B", "qty": Decimal("20000"), "price": Decimal("36.00"), "penalty": True, "del_days": 21},
        {"pack": 3, "supplier": "Karnaphuli Yarn Traders", "item": "C", "qty": Decimal("800"), "price": Decimal("229.00"), "penalty": True, "del_days": 20},
        {"pack": 4, "supplier": "Surma Packaging Industries", "item": "D", "qty": Decimal("50000"), "price": Decimal("6.65"), "penalty": True, "del_days": 28},
        {"pack": 5, "supplier": "Meghna Carton Works", "item": "E", "qty": Decimal("3000"), "price": Decimal("92.00"), "penalty": True, "del_days": 25},
        {"pack": 6, "supplier": "Teesta Fabrics Ltd", "item": "A", "qty": Decimal("12000"), "price": Decimal("465.00"), "penalty": False, "del_days": 27},
        {"pack": 7, "supplier": "Rupsha Zipper Factory", "item": "B", "qty": Decimal("16500"), "price": Decimal("35.00"), "penalty": True, "del_days": 22},
        {"pack": 8, "supplier": "Bhairab Thread and Co", "item": "C", "qty": Decimal("800"), "price": Decimal("205.00"), "penalty": True, "del_days": 18},
        {"pack": 9, "supplier": "Dhaleshwari Poly Pack", "item": "D", "qty": Decimal("50000"), "price": Decimal("6.40"), "penalty": True, "del_days": 28},
        {"pack": 10, "supplier": "Kushiyara Box Industries", "item": "E", "qty": Decimal("3000"), "price": Decimal("94.00"), "penalty": True, "del_days": 60},
    ]

    for item in expected_data:
        p_idx = item["pack"]
        pdf_path = settings.data_dir / f"supplier-pack-{p_idx:02d}.pdf"
        doc = ingestor.ingest(pdf_path)
        assert doc.is_readable

        quot, uncertainties = extractor.extract(doc)

        # 1. Supplier Name & Provenance
        assert quot.supplier_name.value == item["supplier"]
        assert quot.supplier_name.evidence_verified
        assert quot.supplier_name.page_number == 1

        # 2. Line Item verification
        assert len(quot.line_items) == 1
        line = quot.line_items[0]
        assert line.item_code.value == item["item"]
        assert line.quantity.value == item["qty"]
        assert line.unit_price.value == item["price"]
        assert line.quantity.evidence_verified
        assert line.unit_price.evidence_verified

        # 3. Delivery days
        assert quot.terms.delivery_timeline_days.value == item["del_days"]
        assert quot.terms.delivery_terms_text.evidence_verified

        # 4. Penalty existence check
        assert quot.terms.has_late_delivery_penalty.value == item["penalty"]


def test_pack_06_missing_penalty_clause(ingestor, extractor):
    """Pack 06 omits the late-delivery penalty clause entirely."""
    pdf_path = settings.data_dir / "supplier-pack-06.pdf"
    doc = ingestor.ingest(pdf_path)
    quot, _ = extractor.extract(doc)

    assert not quot.terms.has_late_delivery_penalty.value
    assert quot.terms.penalty_terms_text.status == ExtractionStatus.MISSING
    assert quot.terms.late_penalty_percentage_per_week.status == ExtractionStatus.MISSING


def test_pack_08_missing_registration_and_evasion(ingestor, extractor):
    """Pack 08 provides an evasive statement instead of TIN/BIN."""
    pdf_path = settings.data_dir / "supplier-pack-08.pdf"
    doc = ingestor.ingest(pdf_path)
    quot, uncertainties = extractor.extract(doc)

    assert quot.supplier_tin.status == ExtractionStatus.MISSING
    assert quot.supplier_bin.status == ExtractionStatus.MISSING
    assert any(u.field_name == "supplier_tin_bin" for u in uncertainties)
    assert any("evasive" in u.details.lower() for u in uncertainties)


def test_pack_09_week_duration_and_ambiguous_payment(ingestor, extractor):
    """Pack 09 uses '4 weeks' for delivery and conditional payment terms."""
    pdf_path = settings.data_dir / "supplier-pack-09.pdf"
    doc = ingestor.ingest(pdf_path)
    quot, _ = extractor.extract(doc)

    # 4 weeks = 28 days
    assert quot.terms.delivery_timeline_days.value == 28
    # Payment terms flagged unclear
    assert quot.terms.payment_terms_unclear.value is True


def test_pack_10_bundled_vat_and_60_days(ingestor, extractor):
    """Pack 10 bundles VAT into unit price and has 60-day delivery."""
    pdf_path = settings.data_dir / "supplier-pack-10.pdf"
    doc = ingestor.ingest(pdf_path)
    quot, _ = extractor.extract(doc)

    assert quot.terms.delivery_timeline_days.value == 60
    assert not quot.vat_shown_separately.value
    assert quot.subtotal.status == ExtractionStatus.MISSING
    assert quot.vat_amount.status == ExtractionStatus.MISSING


def test_evidence_verification_failure_on_fabricated_quote(ingestor):
    """Test that a fabricated or non-existent quote fails evidence verification."""
    pdf_path = settings.data_dir / "supplier-pack-01.pdf"
    doc = ingestor.ingest(pdf_path)

    # Valid quote
    assert verify_text_on_page("Padma Textile Mills Ltd", 1, doc)

    # Fabricated quote not in document
    assert not verify_text_on_page("Fabricated Nonexistent Supplier 123", 1, doc)

    # Wrong page number
    assert not verify_text_on_page("Padma Textile Mills Ltd", 2, doc)

