from decimal import Decimal
import pytest
from pydantic import ValidationError
from src.models.schemas import (
    DecisionEnum,
    FieldProvenance,
    PurchaseRequest,
    PurchaseRequestItem,
    RuleCategory,
)


def test_field_provenance_valid():
    prov = FieldProvenance[Decimal](
        value=Decimal("472.00"),
        raw_text="Unit price (BDT) 472.00",
        page_number=1,
        confidence=0.98,
    )
    assert prov.value == Decimal("472.00")
    assert prov.raw_text == "Unit price (BDT) 472.00"
    assert prov.page_number == 1
    assert prov.confidence == 0.98


def test_field_provenance_confidence_bounds():
    with pytest.raises(ValidationError):
        FieldProvenance[str](value="Test", raw_text="Test", confidence=1.5)

    with pytest.raises(ValidationError):
        FieldProvenance[str](value="Test", raw_text="Test", confidence=-0.1)


def test_field_provenance_extra_forbid():
    with pytest.raises(ValidationError):
        FieldProvenance[str](
            value="Test",
            raw_text="Test",
            unexpected_field="invalid",  # Extra field forbidden
        )


def test_purchase_request_item_tolerances():
    item_a = PurchaseRequestItem(
        item_code="A",
        description="Cotton twill fabric, 280 gsm",
        unit="metre",
        quantity_requested=Decimal("12000"),
        maximum_unit_price=Decimal("480.00"),
    )

    # 480.00 * 1.03 = 494.40
    assert item_a.price_rejection_ceiling == Decimal("494.4000")

    # 12000 * 0.95 = 11400
    assert item_a.min_quantity_tolerance == Decimal("11400.0000")

    # 12000 * 1.05 = 12600
    assert item_a.max_quantity_tolerance == Decimal("12600.0000")


def test_decision_enum_values():
    assert DecisionEnum.APPROVE.value == "APPROVE"
    assert DecisionEnum.REJECT.value == "REJECT"
    assert DecisionEnum.NEEDS_HUMAN_REVIEW.value == "NEEDS HUMAN REVIEW"

