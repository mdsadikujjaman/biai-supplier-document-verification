from decimal import Decimal
from pathlib import Path
import pytest
from src.extractor import ExtractionEngine
from src.ingestion import DocumentIngestionEngine
from src.models.schemas import ExtractionStatus


@pytest.fixture(scope="module")
def extracted_packs():
    ingestor = DocumentIngestionEngine()
    extractor = ExtractionEngine()
    results = {}
    for idx in range(1, 11):
        filename = f"supplier-pack-{idx:02d}.pdf"
        doc = ingestor.ingest(Path("sample_data") / filename)
        quotation, uncertainties = extractor.extract(doc)
        results[filename] = (quotation, uncertainties, doc)
    return results


def test_regression_pack_01_padma_textiles(extracted_packs):
    """Regression test: verifies exact pricing, supplier name, and page provenance for Pack 01."""
    quotation, uncertainties, doc = extracted_packs["supplier-pack-01.pdf"]

    assert quotation.supplier_name.value == "Padma Textile Mills Ltd"
    assert quotation.supplier_name.page_number == 1
    assert quotation.quotation_no.value == "QT-2026-901"

    assert len(quotation.line_items) == 1
    item = quotation.line_items[0]
    assert item.item_code.value == "A"
    assert item.description.value == "Cotton twill fabric, 280 gsm"
    assert item.quantity.value == Decimal("12000")
    assert item.unit.value == "metre"

    # Critical price check: must be 472.00 BDT, NOT 42.00 BDT
    assert item.unit_price.value == Decimal("472.00")
    assert item.unit_price.raw_text == "472.00"
    assert item.unit_price.page_number == 1
    assert item.unit_price.evidence_verified is True
    assert item.unit_price.status == ExtractionStatus.EXTRACTED

    # Line Amount & Totals
    assert item.line_amount.value == Decimal("5664000.00")
    assert quotation.subtotal.value == Decimal("5664000.00")
    assert quotation.vat_amount.value == Decimal("849600.00")
    assert quotation.total_amount.value == Decimal("6513600.00")


def test_regression_pack_02_jamuna_trims(extracted_packs):
    """Regression test: verifies exact pricing, supplier name, and page provenance for Pack 02."""
    quotation, uncertainties, doc = extracted_packs["supplier-pack-02.pdf"]

    assert quotation.supplier_name.value == "Jamuna Trims and Accessories"
    assert quotation.supplier_name.page_number == 1
    assert quotation.quotation_no.value == "QT-2026-902"

    assert len(quotation.line_items) == 1
    item = quotation.line_items[0]
    assert item.item_code.value == "B"
    assert item.description.value == "Metal zipper, 18 cm"
    assert item.quantity.value == Decimal("20000")
    assert item.unit.value == "piece"

    # Critical price check: must be 36.00 BDT, NOT 18.50 BDT
    assert item.unit_price.value == Decimal("36.00")
    assert item.unit_price.raw_text == "36.00"
    assert item.unit_price.page_number == 1
    assert item.unit_price.evidence_verified is True
    assert item.unit_price.status == ExtractionStatus.EXTRACTED

    # Line Amount & Totals
    assert item.line_amount.value == Decimal("720000.00")
    assert quotation.subtotal.value == Decimal("720000.00")
    assert quotation.vat_amount.value == Decimal("108000.00")
    assert quotation.total_amount.value == Decimal("828000.00")


@pytest.mark.parametrize(
    "filename,expected_supplier,expected_item,expected_qty,expected_price",
    [
        ("supplier-pack-01.pdf", "Padma Textile Mills Ltd", "A", Decimal("12000"), Decimal("472.00")),
        ("supplier-pack-02.pdf", "Jamuna Trims and Accessories", "B", Decimal("20000"), Decimal("36.00")),
        ("supplier-pack-03.pdf", "Karnaphuli Yarn Traders", "C", Decimal("800"), Decimal("229.00")),
        ("supplier-pack-04.pdf", "Surma Packaging Industries", "D", Decimal("50000"), Decimal("6.65")),
        ("supplier-pack-05.pdf", "Meghna Carton Works", "E", Decimal("3000"), Decimal("92.00")),
        ("supplier-pack-06.pdf", "Teesta Fabrics Ltd", "A", Decimal("12000"), Decimal("465.00")),
        ("supplier-pack-07.pdf", "Rupsha Zipper Factory", "B", Decimal("16500"), Decimal("35.00")),
        ("supplier-pack-08.pdf", "Bhairab Thread and Co", "C", Decimal("800"), Decimal("205.00")),
        ("supplier-pack-09.pdf", "Dhaleshwari Poly Pack", "D", Decimal("50000"), Decimal("6.40")),
        ("supplier-pack-10.pdf", "Kushiyara Box Industries", "E", Decimal("3000"), Decimal("94.00")),
    ],
)
def test_all_ten_packs_verified_prices(extracted_packs, filename, expected_supplier, expected_item, expected_qty, expected_price):
    """Verifies that all 10 sample supplier packs match their ground truth figures from the physical PDFs."""
    quotation, _, doc = extracted_packs[filename]

    assert quotation.supplier_name.value == expected_supplier
    assert len(quotation.line_items) == 1
    item = quotation.line_items[0]

    assert item.item_code.value == expected_item
    assert item.quantity.value == expected_qty
    assert item.unit_price.value == expected_price
    assert item.unit_price.evidence_verified is True
    assert item.unit_price.page_number == 1

