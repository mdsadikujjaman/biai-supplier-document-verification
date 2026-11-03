from decimal import Decimal
import pytest
from src.comparator import PurchaseRequestComparator
from src.config import settings
from src.extractor import DeterministicExtractionProvider, ExtractionEngine
from src.ingestion import DocumentIngestionEngine
from src.models.schemas import (
    ExtractedLineItem,
    ExtractedQuotation,
    ExtractedTerms,
    FieldProvenance,
)
from src.pr_loader import PurchaseRequestLoader


@pytest.fixture
def pr():
    loader = PurchaseRequestLoader()
    return loader.load(settings.pr_file_path)


@pytest.fixture
def comparator():
    return PurchaseRequestComparator()


@pytest.fixture
def ingestor():
    return DocumentIngestionEngine()


@pytest.fixture
def extractor():
    return ExtractionEngine(provider=DeterministicExtractionProvider())


def test_compare_pack_01_exact_match(ingestor, extractor, pr, comparator):
    """Pack 01 matches Item A in PR, price <= max, quantity within tolerance."""
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-01.pdf")
    quot, _ = extractor.extract(doc)
    comp = comparator.compare(quot, pr)

    assert len(comp.matched_items) == 1
    match = comp.matched_items[0]
    assert match.item_code == "A"
    assert match.is_valid_match
    assert match.description_match
    assert match.unit_match
    assert match.quantity_within_tolerance
    assert match.quantity_variance_pct == Decimal("0.00")
    assert match.price_is_below_or_equal_max
    assert not match.price_exceeds_rejection_ceiling
    assert match.quoted_unit_price == Decimal("472.00")
    assert match.max_unit_price == Decimal("480.00")


def test_compare_pack_03_price_exceeds_rejection_ceiling(ingestor, extractor, pr, comparator):
    """Pack 03 quotes Item C at 229.00 BDT vs max 210.00 BDT (+9.05% > +3% ceiling)."""
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-03.pdf")
    quot, _ = extractor.extract(doc)
    comp = comparator.compare(quot, pr)

    assert len(comp.matched_items) == 1
    match = comp.matched_items[0]
    assert match.item_code == "C"
    assert match.is_valid_match
    assert not match.price_is_below_or_equal_max
    assert match.price_exceeds_rejection_ceiling
    assert match.price_variance_pct == Decimal("9.05")


def test_compare_pack_04_price_within_review_band(ingestor, extractor, pr, comparator):
    """Pack 04 quotes Item D at 6.65 BDT vs max 6.50 BDT (+2.31% <= +3% ceiling)."""
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-04.pdf")
    quot, _ = extractor.extract(doc)
    comp = comparator.compare(quot, pr)

    assert len(comp.matched_items) == 1
    match = comp.matched_items[0]
    assert match.item_code == "D"
    assert match.is_valid_match
    assert not match.price_is_below_or_equal_max
    assert match.price_is_within_review_band
    assert not match.price_exceeds_rejection_ceiling
    assert match.price_variance_pct == Decimal("2.31")


def test_compare_pack_07_quantity_shortfall(ingestor, extractor, pr, comparator):
    """Pack 07 quotes 16,500 pieces vs requested 20,000 pieces (-17.5% > 5% tolerance)."""
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-07.pdf")
    quot, _ = extractor.extract(doc)
    comp = comparator.compare(quot, pr)

    assert len(comp.matched_items) == 1
    match = comp.matched_items[0]
    assert match.item_code == "B"
    assert match.is_valid_match
    assert not match.quantity_within_tolerance
    assert match.quantity_variance_pct == Decimal("-17.50")
    assert match.quantity_difference == Decimal("-3500")


def test_unknown_item_code(pr, comparator):
    """Quotation with item code 'Z' not in PR."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier Z", "Supplier Z"),
        quotation_no=FieldProvenance[str].extracted("QT-Z", "QT-Z"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("Z", "Z"),
                description=FieldProvenance[str].extracted("Unknown Item", "Unknown Item"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("100"), "100"),
                unit=FieldProvenance[str].extracted("piece", "piece"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("50.00"), "50.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("5000.00"), "5000.00"),
            )
        ],
        total_amount=FieldProvenance[Decimal].extracted(Decimal("5750.00"), "5750.00"),
        terms=ExtractedTerms(),
    )
    comp = comparator.compare(quot, pr)
    assert "Z" in comp.unknown_item_codes
    assert len(comp.matched_items) == 0


def test_duplicate_item_codes(pr, comparator):
    """Quotation with duplicate line items for code 'A'."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier Dup", "Supplier Dup"),
        quotation_no=FieldProvenance[str].extracted("QT-DUP", "QT-DUP"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("A", "A"),
                description=FieldProvenance[str].extracted("Cotton twill fabric, 280 gsm", "Cotton twill"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("6000"), "6000"),
                unit=FieldProvenance[str].extracted("metre", "metre"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("470.00"), "470.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("2820000.00"), "2820000.00"),
            ),
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("A", "A"),
                description=FieldProvenance[str].extracted("Cotton twill fabric, 280 gsm", "Cotton twill"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("6000"), "6000"),
                unit=FieldProvenance[str].extracted("metre", "metre"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("470.00"), "470.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("2820000.00"), "2820000.00"),
            ),
        ],
        total_amount=FieldProvenance[Decimal].extracted(Decimal("5640000.00"), "5640000.00"),
        terms=ExtractedTerms(),
    )
    comp = comparator.compare(quot, pr)
    assert "A" in comp.duplicate_item_codes


def test_unit_and_description_mismatch(pr, comparator):
    """Item code matches 'A', but unit is 'piece' (instead of metre) and description is 'Steel bolts'."""
    quot = ExtractedQuotation(
        supplier_name=FieldProvenance[str].extracted("Supplier Mismatch", "Supplier Mismatch"),
        quotation_no=FieldProvenance[str].extracted("QT-MIS", "QT-MIS"),
        quotation_date=FieldProvenance[str].extracted("2026-10-01", "2026-10-01"),
        line_items=[
            ExtractedLineItem(
                item_code=FieldProvenance[str].extracted("A", "A"),
                description=FieldProvenance[str].extracted("Steel bolts, heavy duty", "Steel bolts"),
                quantity=FieldProvenance[Decimal].extracted(Decimal("12000"), "12000"),
                unit=FieldProvenance[str].extracted("piece", "piece"),
                unit_price=FieldProvenance[Decimal].extracted(Decimal("400.00"), "400.00"),
                line_amount=FieldProvenance[Decimal].extracted(Decimal("4800000.00"), "4800000.00"),
            )
        ],
        total_amount=FieldProvenance[Decimal].extracted(Decimal("5520000.00"), "5520000.00"),
        terms=ExtractedTerms(),
    )
    comp = comparator.compare(quot, pr)
    assert len(comp.matched_items) == 1
    match = comp.matched_items[0]
    assert not match.is_valid_match
    assert not match.description_match
    assert not match.unit_match
    assert comp.has_unit_mismatch
    assert comp.has_description_mismatch

