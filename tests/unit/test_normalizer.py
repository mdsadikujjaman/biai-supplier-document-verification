from decimal import Decimal
import pytest
from src.normalizer import CanonicalNormalizer


def test_normalize_currency():
    norm = CanonicalNormalizer.normalize_currency
    assert norm("BDT 6.50") == Decimal("6.50")
    assert norm("472.00") == Decimal("472.00")
    assert norm("5,664,000.00") == Decimal("5664000.00")
    assert norm("Tk. 95.00") == Decimal("95.00")
    assert norm("0.00") == Decimal("0.00")
    assert norm(None) is None
    assert norm("") is None
    assert norm("invalid text") is None


def test_normalize_quantity():
    norm = CanonicalNormalizer.normalize_quantity
    assert norm("12,000") == Decimal("12000")
    assert norm("800") == Decimal("800")
    assert norm("50,000") == Decimal("50000")
    assert norm("16,500") == Decimal("16500")
    assert norm(None) is None
    assert norm("abc") is None


def test_normalize_percentage():
    norm = CanonicalNormalizer.normalize_percentage
    assert norm("15%") == Decimal("15")
    assert norm("10% advance") == Decimal("10")
    assert norm("0.75% of order value") == Decimal("0.75")
    assert norm("1% per week") == Decimal("1")
    assert norm("40%") == Decimal("40")
    assert norm(None) is None


def test_normalize_delivery_days():
    norm = CanonicalNormalizer.normalize_delivery_days

    # Explicit days
    days, ambiguous = norm("Delivery within 24 days of receiving the purchase order.")
    assert days == 24
    assert not ambiguous

    days, ambiguous = norm("Delivery within 60 days of PO.")
    assert days == 60
    assert not ambiguous

    # Weeks conversion
    days, ambiguous = norm("Delivery within 4 weeks of PO.")
    assert days == 28
    assert not ambiguous

    # Months conversion
    days, ambiguous = norm("Delivery within 1 month of PO.")
    assert days == 30
    assert not ambiguous

    # Ambiguous / discussion terms
    days, ambiguous = norm("Delivery schedule subject to discussion.")
    assert days is None
    assert ambiguous


def test_normalize_credit_days():
    norm = CanonicalNormalizer.normalize_credit_days

    # Standard unambiguous days
    days, unclear = norm("Balance payable within 45 days after delivery and acceptance of goods.")
    assert days == 45
    assert not unclear

    days, unclear = norm("Full payment within 30 days of delivery.")
    assert days == 30
    assert not unclear

    days, unclear = norm("Balance within 60 days of delivery.")
    assert days == 60
    assert not unclear

    # Ambiguous / range terms (Pack 09): must NOT return a definite numeric value!
    days, unclear = norm("Payment within 30 to 90 days as agreed by both parties.")
    assert days is None
    assert unclear


def test_normalize_registration():
    norm = CanonicalNormalizer.normalize_registration

    # Valid TIN and BIN
    res = norm("Supplier TIN: 101458013391 BIN: 000170141-0101")
    assert res["tin"] == "101458013391"
    assert res["bin"] == "000170141-0101"
    assert not res["is_evasive"]

    # Evasive registration statement (Pack 08)
    res_evasive = norm("Supplier registration details available on request.")
    assert res_evasive["tin"] is None
    assert res_evasive["bin"] is None
    assert res_evasive["is_evasive"]

    # Empty
    res_empty = norm(None)
    assert res_empty["tin"] is None
    assert res_empty["bin"] is None

