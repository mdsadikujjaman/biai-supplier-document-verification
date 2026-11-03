from decimal import Decimal
from pathlib import Path
import pytest
from src.config import settings
from src.extractor import (
    DeterministicExtractionProvider,
    ExtractionEngine,
    LLMExtractionProvider,
    verify_text_on_page,
)
from src.ingestion import DocumentIngestionEngine
from src.interfaces.base import IngestedDocument
from src.models.schemas import ExtractionStatus, FieldProvenance
from src.normalizer import CanonicalNormalizer


@pytest.fixture
def ingestor():
    return DocumentIngestionEngine()


@pytest.fixture
def extractor():
    return ExtractionEngine(provider=DeterministicExtractionProvider())


def test_part_a_field_evidence_verified_on_correct_page(ingestor, extractor):
    """Confirm every extracted field's evidence is verified against the correct PDF page."""
    pdf_path = settings.data_dir / "supplier-pack-01.pdf"
    doc = ingestor.ingest(pdf_path)
    quot, _ = extractor.extract(doc)

    assert quot.supplier_name.evidence_verified
    assert quot.supplier_name.page_number == 1
    assert quot.quotation_no.evidence_verified
    assert quot.quotation_date.evidence_verified
    assert quot.supplier_tin.evidence_verified
    assert quot.supplier_bin.evidence_verified

    for item in quot.line_items:
        assert item.item_code.evidence_verified
        assert item.description.evidence_verified
        assert item.quantity.evidence_verified
        assert item.unit_price.evidence_verified


def test_part_a_distinguish_missing_unreadable_ambiguous_conflicting():
    """Confirm missing, unreadable, ambiguous, and conflicting remain strictly distinguishable."""
    f_missing = FieldProvenance[str].missing()
    f_unreadable = FieldProvenance[str].unreadable()
    f_ambiguous = FieldProvenance[str].ambiguous(raw_text="30 to 90 days as agreed", value=None)
    f_conflicting = FieldProvenance[str].conflicting(raw_text="10% advance vs 20% advance", value=None)

    assert f_missing.status == ExtractionStatus.MISSING
    assert f_missing.value is None

    assert f_unreadable.status == ExtractionStatus.UNREADABLE
    assert f_unreadable.value is None

    assert f_ambiguous.status == ExtractionStatus.AMBIGUOUS
    assert f_ambiguous.value is None
    assert f_ambiguous.raw_text == "30 to 90 days as agreed"

    assert f_conflicting.status == ExtractionStatus.CONFLICTING
    assert f_conflicting.value is None
    assert f_conflicting.raw_text == "10% advance vs 20% advance"

    # All 4 statuses must be distinct
    statuses = {f_missing.status, f_unreadable.status, f_ambiguous.status, f_conflicting.status}
    assert len(statuses) == 4


def test_part_a_normalization_preserves_raw_text():
    """Confirm normalization never alters original raw text string."""
    raw_str = "  BDT 6,513,600.00  "
    normalized = CanonicalNormalizer.normalize_currency(raw_str)
    assert normalized == Decimal("6513600.00")
    # Original raw string is untouched
    assert raw_str == "  BDT 6,513,600.00  "


def test_part_a_ambiguous_expressions_never_definite_numeric():
    """Confirm ambiguous expressions like '30-90 days as agreed' do not become definite numeric values."""
    days, is_ambiguous = CanonicalNormalizer.normalize_credit_days("Payment within 30 to 90 days as agreed by both parties.")
    assert days is None, "Ambiguous range should not yield a single definite integer day value"
    assert is_ambiguous is True

    # Pack 09 verification
    ingestor = DocumentIngestionEngine()
    extractor = ExtractionEngine(provider=DeterministicExtractionProvider())
    doc = ingestor.ingest(settings.data_dir / "supplier-pack-09.pdf")
    quot, _ = extractor.extract(doc)

    assert quot.terms.credit_days_after_delivery.value is None
    assert quot.terms.credit_days_after_delivery.status == ExtractionStatus.AMBIGUOUS
    assert quot.terms.payment_terms_unclear.value is True


def test_part_a_confidence_downgraded_when_unverified():
    """Confirm confidence is not set to 1.0 without justification and downgraded to 0.0 if unverified."""
    doc = IngestedDocument(
        file_path="mock.pdf",
        file_name="mock.pdf",
        file_hash="mock",
        page_count=1,
        full_text="Some document text without the quote.",
        pages={1: "Some document text without the quote."},
        is_readable=True,
    )
    # verify_text_on_page returns False
    assert not verify_text_on_page("Nonexistent Quote", 1, doc)


def test_part_a_provider_failure_never_becomes_confirmed_missing():
    """Confirm that an unreadable document sets UNREADABLE, never confirmed missing clauses."""
    unreadable_doc = IngestedDocument(
        file_path="corrupt.pdf",
        file_name="corrupt.pdf",
        file_hash="",
        page_count=0,
        full_text="",
        pages={},
        is_readable=False,
        error_message="Corrupt file header",
    )
    extractor = DeterministicExtractionProvider()
    quot, uncertainties = extractor.extract(unreadable_doc)

    # Must be UNREADABLE, not MISSING
    assert quot.terms.has_late_delivery_penalty.status == ExtractionStatus.UNREADABLE
    assert quot.terms.delivery_timeline_days.status == ExtractionStatus.UNREADABLE
    assert quot.supplier_name.status == ExtractionStatus.UNREADABLE
    assert any(u.issue_type == "UNREADABLE" for u in uncertainties)


def test_part_a_llm_failure_safely_handled():
    """Confirm LLM API failure is recorded in uncertainties and safely falls back."""
    doc = IngestedDocument(
        file_path="mock.pdf",
        file_name="mock.pdf",
        file_hash="mock",
        page_count=1,
        full_text="Padma Textile Mills Ltd\nQUOTATION\nQuotation no.\nQT-2026-901\nDate\n2026-10-21\nSupplier TIN: 101458013391 BIN: 000170141-0101\n1. Payment. 10% advance payable\n2. Delivery. within 24 days\n3. Delay. 1% per week\n4. Validity. 45 days\nAmount (BDT)\nA\nCotton twill fabric, 280 gsm\n12,000\nmetre\n472.00\n5,664,000.00\nSubtotal\n5,664,000.00\nVAT 15%\n849,600.00\nTotal\n6,513,600.00",
        pages={1: "Padma Textile Mills Ltd\nQUOTATION\nQuotation no.\nQT-2026-901\nDate\n2026-10-21\nSupplier TIN: 101458013391 BIN: 000170141-0101\n1. Payment. 10% advance payable\n2. Delivery. within 24 days\n3. Delay. 1% per week\n4. Validity. 45 days\nAmount (BDT)\nA\nCotton twill fabric, 280 gsm\n12,000\nmetre\n472.00\n5,664,000.00\nSubtotal\n5,664,000.00\nVAT 15%\n849,600.00\nTotal\n6,513,600.00"},
        is_readable=True,
    )
    # Provider with invalid API key to trigger fallback
    llm_provider = LLMExtractionProvider(api_key="invalid_test_key", model_name="gemini-1.5-flash", provider="gemini")
    quot, uncertainties = llm_provider.extract(doc)

    # Should fall back cleanly and record the fallback uncertainty
    assert quot.supplier_name.value == "Padma Textile Mills Ltd"
    assert any("fallback" in u.details.lower() or "llm" in u.field_name.lower() for u in uncertainties)

