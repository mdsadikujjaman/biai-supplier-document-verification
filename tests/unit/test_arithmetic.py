from decimal import Decimal
import pytest
from src.arithmetic import ArithmeticVerifier, round_currency
from src.config import settings
from src.extractor import DeterministicExtractionProvider, ExtractionEngine
from src.ingestion import DocumentIngestionEngine
from src.models.schemas import (
    ExtractedLineItem,
    ExtractedQuotation,
    ExtractedTerms,
    FieldProvenance,
)


@pytest.fixture
def ingestor():
    return DocumentIngestionEngine()


@pytest.fixture
def extractor():
    return ExtractionEngine(provider=DeterministicExtractionProvider())


@pytest.fixture
def verifier():
    return ArithmeticVerifier()


def test_round_currency_half_up():
    assert round_currency(Decimal("10.004")) == Decimal("10.00")
    assert round_currency(Decimal("10.005")) == Decimal("10.01")
    assert round_currency(Decimal("10.006")) == Decimal("10.01")


def test_arithmetic_pack_01_clean(ingestor, extractor, verifier):
    """Pack 01 has clean, consistent calculations across all components."""
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-01.pdf")
    quot, _ = extractor.extract(doc)
    audit = verifier.verify(quot)

    assert audit.all_passed
    assert audit.line_calculations_match
    assert audit.subtotal_matches_lines
    assert audit.vat_matches_subtotal_15pct
    assert audit.total_matches_sum
    assert audit.vat_shown_separately
    assert audit.calculated_subtotal == Decimal("5664000.00")
    assert audit.calculated_vat == Decimal("849600.00")
    assert audit.calculated_total == Decimal("6513600.00")
    assert len(audit.discrepancies) == 0


def test_arithmetic_pack_09_discrepancy(ingestor, extractor, verifier):
    """Pack 09 contains an arithmetic mismatch on the line total:

    50,000 * 6.40 = 320,000.00 BDT, but document quoted 322,000.00 BDT.
    """
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-09.pdf")
    quot, _ = extractor.extract(doc)
    audit = verifier.verify(quot)

    # Line item calculation failed
    assert not audit.line_calculations_match
    assert not audit.all_passed

    # Verify line check discrepancy
    assert len(audit.discrepancies) >= 1
    line_disc = [d for d in audit.discrepancies if d.component == "LINE_AMOUNT"][0]
    assert line_disc.expected_value == Decimal("320000.00")
    assert line_disc.quoted_value == Decimal("322000.00")
    assert line_disc.discrepancy_amount == Decimal("2000.00")
    assert "322,000.00" in line_disc.evidence_quote


def test_arithmetic_pack_10_bundled_vat(ingestor, extractor, verifier):
    """Pack 10 has bundled VAT ('Unit price (BDT, VAT included)').

    VAT is not shown separately at 15%.
    """
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-10.pdf")
    quot, _ = extractor.extract(doc)
    audit = verifier.verify(quot)

    assert not audit.vat_shown_separately
    assert not audit.all_passed
    assert any("bundled" in msg.lower() or "not shown separately" in msg.lower() for msg in audit.discrepancy_details)


def test_synthetic_incorrect_line_amount(verifier):
    """Synthetic quotation with wrong line item amount."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier A", "Supplier A"),
        quotation_no=FieldProvenance[str].extracted("QT-01", "QT-01"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("A", "A"),
                description=FieldProvenance[str].extracted("Fabric", "Fabric"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("100"), "100"),
                unit=FieldProvenance[str].extracted("metre", "metre"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("50.00"), "50.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("6000.00"), "6,000.00"),  # 100 * 50 = 5000, not 6000
            )
        ],
        subtotal=FieldProvenance[Decimal].extracted(Decimal("6000.00"), "6000.00"),
        vat_percentage=FieldProvenance[Decimal].extracted(Decimal("15"), "15%"),
        vat_amount=FieldProvenance[Decimal].extracted(Decimal("900.00"), "900.00"),
        vat_shown_separately=FieldProvenance[bool].extracted(True, "VAT 15%"),
        total_amount=FieldProvenance[Decimal].extracted(Decimal("6900.00"), "6900.00"),
        terms=ExtractedTerms(),
    )
    audit = verifier.verify(quot)
    assert not audit.line_calculations_match
    assert audit.discrepancies[0].expected_value == Decimal("5000.00")
    assert audit.discrepancies[0].quoted_value == Decimal("6000.00")


def test_synthetic_incorrect_vat_calculation(verifier):
    """Synthetic quotation where VAT percentage does not match quoted amount."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier B", "Supplier B"),
        quotation_no=FieldProvenance[str].extracted("QT-02", "QT-02"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("B", "B"),
                description=FieldProvenance[str].extracted("Zippers", "Zippers"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("1000"), "1000"),
                unit=FieldProvenance[str].extracted("piece", "piece"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("10.00"), "10.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("10000.00"), "10,000.00"),
            )
        ],
        subtotal=FieldProvenance[Decimal].extracted(Decimal("10000.00"), "10000.00"),
        vat_percentage=FieldProvenance[Decimal].extracted(Decimal("15"), "15%"),
        vat_amount=FieldProvenance[Decimal].extracted(Decimal("2500.00"), "2500.00"),  # Expected: 15% of 10000 = 1500, quoted: 2500
        vat_shown_separately=FieldProvenance[bool].extracted(True, "VAT 15%"),
        total_amount=FieldProvenance[Decimal].extracted(Decimal("12500.00"), "12500.00"),
        terms=ExtractedTerms(),
    )
    audit = verifier.verify(quot)
    assert not audit.vat_matches_subtotal_15pct
    assert any(d.component == "VAT" for d in audit.discrepancies)


def test_synthetic_incorrect_grand_total(verifier):
    """Synthetic quotation where subtotal + VAT does not equal total."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier C", "Supplier C"),
        quotation_no=FieldProvenance[str].extracted("QT-03", "QT-03"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("C", "C"),
                description=FieldProvenance[str].extracted("Thread", "Thread"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("100"), "100"),
                unit=FieldProvenance[str].extracted("cone", "cone"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("100.00"), "100.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("10000.00"), "10000.00"),
            )
        ],
        subtotal=FieldProvenance[Decimal].extracted(Decimal("10000.00"), "10000.00"),
        vat_percentage=FieldProvenance[Decimal].extracted(Decimal("15"), "15%"),
        vat_amount=FieldProvenance[Decimal].extracted(Decimal("1500.00"), "1500.00"),
        vat_shown_separately=FieldProvenance[bool].extracted(True, "VAT 15%"),
        total_amount=FieldProvenance[Decimal].extracted(Decimal("15000.00"), "15000.00"),  # Expected: 10000 + 1500 = 11500, quoted 15000
        terms=ExtractedTerms(),
    )
    audit = verifier.verify(quot)
    assert not audit.total_matches_sum
    assert any(d.component == "TOTAL" for d in audit.discrepancies)

