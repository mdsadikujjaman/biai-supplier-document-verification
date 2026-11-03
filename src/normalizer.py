from decimal import Decimal, InvalidOperation
import re
from typing import Optional, Tuple


class CanonicalNormalizer:
    """Provides canonical normalization functions for monetary amounts, durations,

    percentages, registration IDs, and textual representations.
    Preserves original raw quotes unaltered.
    """

    @staticmethod
    def normalize_currency(raw_str: Optional[str]) -> Optional[Decimal]:
        """Convert raw currency string (e.g. 'BDT 6.50', '5,664,000.00', '472.00')

        into Decimal without floating point loss.
        """
        if not raw_str or not raw_str.strip():
            return None

        # Clean string: remove currency labels, whitespace, commas
        cleaned = re.sub(r"(?i)\b(?:bdt|tk|usd|taka)\b", "", raw_str)
        cleaned = cleaned.replace(",", "").strip()

        # Extract numeric component (with optional decimal point)
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if not match:
            return None

        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None

    @staticmethod
    def normalize_quantity(raw_str: Optional[str]) -> Optional[Decimal]:
        """Convert raw quantity string (e.g. '12,000', '800', '50,000') into Decimal."""
        if not raw_str or not raw_str.strip():
            return None

        cleaned = raw_str.replace(",", "").strip()
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if not match:
            return None

        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None

    @staticmethod
    def normalize_percentage(raw_str: Optional[str]) -> Optional[Decimal]:
        """Convert percentage strings (e.g. '15%', '10%', '0.75%', '1%') into Decimal."""
        if not raw_str or not raw_str.strip():
            return None

        match = re.search(r"(\d+(?:\.\d+)?)\s*%", raw_str)
        if match:
            try:
                return Decimal(match.group(1))
            except InvalidOperation:
                return None

        # Fallback to standalone float
        cleaned = raw_str.replace("%", "").strip()
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return Decimal(match.group(0))
            except InvalidOperation:
                return None

        return None

    @staticmethod
    def normalize_delivery_days(raw_str: Optional[str]) -> Tuple[Optional[int], bool]:
        """Normalize delivery duration expressions into integer days.

        Returns (days, is_ambiguous).

        Ambiguous expressions return None for days and True for is_ambiguous,
        guaranteeing that ambiguous terms never become definite numeric values.
        """
        if not raw_str or not raw_str.strip():
            return None, True

        text = raw_str.lower().strip()

        # Check for ambiguous or conditional phrasing
        ambiguous_keywords = [
            "discuss", "negotiat", "as agreed", "tbd", "to be determined",
            "approx", "subject to", "tentative"
        ]
        if any(kw in text for kw in ambiguous_keywords):
            return None, True

        # Check for weeks (e.g., "within 4 weeks of PO" -> 28 days)
        match_weeks = re.search(r"within\s+(\d+)\s*weeks?", text) or re.search(r"(\d+)\s*weeks?", text)
        if match_weeks:
            weeks = int(match_weeks.group(1))
            return weeks * 7, False

        # Check for months
        match_months = re.search(r"within\s+(\d+)\s*months?", text) or re.search(r"(\d+)\s*months?", text)
        if match_months:
            months = int(match_months.group(1))
            return months * 30, False

        # Check for days
        match_days = re.search(r"within\s+(\d+)\s*(?:calendar\s*)?(?:working\s*)?days?", text) or re.search(
            r"(\d+)\s*(?:calendar\s*)?(?:working\s*)?days?", text
        )
        if match_days:
            days = int(match_days.group(1))
            return days, False

        return None, True

    @staticmethod
    def normalize_credit_days(raw_str: Optional[str]) -> Tuple[Optional[int], bool]:
        """Normalize payment credit window after delivery.

        Returns (credit_days, is_unclear_or_ambiguous).

        Ambiguous expressions such as ranges ('30 to 90 days') or conditional
        clauses ('as agreed by both parties') return None for credit_days and
        True for is_unclear_or_ambiguous, ensuring ambiguous terms never become
        definite numeric values.
        """
        if not raw_str or not raw_str.strip():
            return None, True

        text = raw_str.lower().strip()

        # Ambiguous / conditional phrases
        ambiguous_phrases = [
            "as agreed", "by both parties", "subject to", "negotiat",
            "to be agreed", "tbd", "to be discussed"
        ]
        is_ambiguous = any(phrase in text for phrase in ambiguous_phrases)

        # Range check e.g. "30 to 90 days" -> inherently indefinite range!
        range_match = re.search(r"(\d+)\s*to\s*(\d+)\s*days?", text)
        if range_match or is_ambiguous:
            # Must NOT return a definite single integer value for an indefinite or conditional term!
            return None, True

        # Single unambiguous day term e.g. "within 45 days after delivery" or "within 30 days of delivery"
        single_match = re.search(r"within\s+(\d+)\s*days?", text)
        if single_match:
            days = int(single_match.group(1))
            return days, False

        # General days match
        general_match = re.search(r"(\d+)\s*days?", text)
        if general_match:
            days = int(general_match.group(1))
            return days, False

        return None, True

    @staticmethod
    def normalize_registration(raw_text: Optional[str]) -> dict:
        """Parse supplier registration information (TIN, BIN).

        Detects explicit evasive statements such as 'available on request'.

        Returns dict:
            {
                'tin': Optional[str],
                'bin': Optional[str],
                'is_evasive': bool,
                'raw_quote': str
            }
        """
        if not raw_text or not raw_text.strip():
            return {"tin": None, "bin": None, "is_evasive": False, "raw_quote": ""}

        text = raw_text.strip()
        evasive_keywords = [
            "available on request", "on request", "upon request",
            "later", "to be provided", "details on request"
        ]
        is_evasive = any(kw in text.lower() for kw in evasive_keywords)

        # Search for TIN (typically 12 digits in Bangladesh)
        tin_match = re.search(r"(?i)\bTIN\s*:\s*([0-9\-_]+)", text)
        tin = tin_match.group(1).strip() if tin_match else None

        # Search for BIN (typically 9-11 digits with dashes e.g. 000170141-0101)
        bin_match = re.search(r"(?i)\bBIN\s*:\s*([0-9\-_]+)", text)
        bin_num = bin_match.group(1).strip() if bin_match else None

        return {
            "tin": tin,
            "bin": bin_num,
            "is_evasive": is_evasive,
            "raw_quote": text,
        }
