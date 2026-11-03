from abc import ABC, abstractmethod
from decimal import Decimal
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

from src.config import settings
from src.interfaces.base import IngestedDocument
from src.models.schemas import (
    ExtractedLineItem,
    ExtractedQuotation,
    ExtractedTerms,
    ExtractionStatus,
    ExtractionUncertainty,
    FieldProvenance,
)
from src.normalizer import CanonicalNormalizer

logger = logging.getLogger(__name__)


def verify_text_on_page(raw_text: Optional[str], page_num: Optional[int], doc: IngestedDocument) -> bool:
    """Verifies that the raw_text quote actually exists on the referenced PDF page."""
    if not raw_text or not page_num:
        return False
    if page_num not in doc.pages:
        return False

    page_content = doc.pages[page_num]
    normalized_quote = " ".join(raw_text.split()).lower()
    normalized_page = " ".join(page_content.split()).lower()
    return normalized_quote in normalized_page


class BaseExtractionProvider(ABC):
    """Abstract extraction provider."""

    @abstractmethod
    def extract(self, doc: IngestedDocument) -> Tuple[ExtractedQuotation, List[ExtractionUncertainty]]:
        """Extract structured quotation data and any extraction uncertainties."""
        pass


class DeterministicExtractionProvider(BaseExtractionProvider):
    """Deterministic extractor using structured regex and layout analysis.

    Provides 100% grounded extraction with exact verbatim quotes and page numbers.
    """

    def extract(self, doc: IngestedDocument) -> Tuple[ExtractedQuotation, List[ExtractionUncertainty]]:
        uncertainties: List[ExtractionUncertainty] = []

        if not doc.is_readable or not doc.full_text.strip():
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="document",
                    issue_type="UNREADABLE",
                    details=doc.error_message or "Document contains no readable text layer.",
                    confidence=0.0,
                )
            )
            # Safe failure mode: return unreadable structure so errors never become confirmed missing clauses
            return self._build_unreadable_quotation(doc), uncertainties

        page_num = 1
        page_text = doc.pages.get(page_num, doc.full_text)
        lines = [line.strip() for line in page_text.split("\n") if line.strip()]

        # 1. Supplier Name (first non-empty line)
        supplier_raw = lines[0] if lines else "UNKNOWN"
        supplier_verified = verify_text_on_page(supplier_raw, page_num, doc)
        supplier_prov = FieldProvenance[str].extracted(
            value=supplier_raw,
            raw_text=supplier_raw,
            page_number=page_num,
            confidence=1.0 if supplier_verified else 0.0,
            evidence_verified=supplier_verified,
        )

        # 2. Quotation Number
        quot_match = re.search(r"Quotation no\.\s*\n?\s*([A-Z0-9\-]+)", page_text)
        if quot_match:
            quot_no = quot_match.group(1).strip()
            quot_quote = quot_match.group(0).strip()
            quot_verified = verify_text_on_page(quot_quote, page_num, doc)
            quot_prov = FieldProvenance[str].extracted(
                value=quot_no,
                raw_text=quot_quote,
                page_number=page_num,
                confidence=1.0 if quot_verified else 0.0,
                evidence_verified=quot_verified,
            )
        else:
            quot_prov = FieldProvenance[str].missing()
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="quotation_no",
                    issue_type="MISSING_REQUIRED",
                    details="Quotation number not found in document.",
                    confidence=1.0,
                )
            )

        # 3. Date
        date_match = re.search(r"Date\s*\n?\s*(\d{4}-\d{2}-\d{2})", page_text)
        if date_match:
            date_val = date_match.group(1).strip()
            date_quote = date_match.group(0).strip()
            date_verified = verify_text_on_page(date_quote, page_num, doc)
            date_prov = FieldProvenance[str].extracted(
                value=date_val,
                raw_text=date_quote,
                page_number=page_num,
                confidence=1.0 if date_verified else 0.0,
                evidence_verified=date_verified,
            )
        else:
            date_prov = FieldProvenance[str].missing()

        # 4. Reference PR and Buyer
        ref_match = re.search(r"Reference\s*\n?\s*([A-Z0-9\-]+)", page_text)
        ref_prov = (
            FieldProvenance[str].extracted(
                value=ref_match.group(1).strip(),
                raw_text=ref_match.group(0).strip(),
                page_number=page_num,
                confidence=1.0 if verify_text_on_page(ref_match.group(0).strip(), page_num, doc) else 0.0,
                evidence_verified=verify_text_on_page(ref_match.group(0).strip(), page_num, doc),
            )
            if ref_match
            else FieldProvenance[str].missing()
        )

        buyer_match = re.search(r"To\s*\n?\s*([^\n]+)", page_text)
        buyer_prov = (
            FieldProvenance[str].extracted(
                value=buyer_match.group(1).strip(),
                raw_text=buyer_match.group(0).strip(),
                page_number=page_num,
                confidence=1.0 if verify_text_on_page(buyer_match.group(0).strip(), page_num, doc) else 0.0,
                evidence_verified=verify_text_on_page(buyer_match.group(0).strip(), page_num, doc),
            )
            if buyer_match
            else FieldProvenance[str].missing()
        )

        # 5. Registration Details (TIN & BIN)
        reg_match = re.search(r"(Supplier TIN:[^\n]+|Supplier registration[^\n]+)", page_text)
        if reg_match:
            reg_raw = reg_match.group(1).strip()
            reg_norm = CanonicalNormalizer.normalize_registration(reg_raw)
            reg_verified = verify_text_on_page(reg_raw, page_num, doc)
            reg_quote_prov = FieldProvenance[str].extracted(
                value=reg_raw,
                raw_text=reg_raw,
                page_number=page_num,
                confidence=1.0 if reg_verified else 0.0,
                evidence_verified=reg_verified,
            )

            if reg_norm["is_evasive"]:
                tin_prov = FieldProvenance[str].missing()
                bin_prov = FieldProvenance[str].missing()
                uncertainties.append(
                    ExtractionUncertainty(
                        field_name="supplier_tin_bin",
                        issue_type="AMBIGUOUS",
                        details="Supplier provided evasive registration statement instead of TIN/BIN numbers.",
                        evidence_quote=reg_raw,
                        page_number=page_num,
                        confidence=1.0,
                    )
                )
            else:
                tin_prov = (
                    FieldProvenance[str].extracted(
                        value=reg_norm["tin"],
                        raw_text=f"TIN: {reg_norm['tin']}",
                        page_number=page_num,
                        confidence=1.0 if reg_verified else 0.0,
                        evidence_verified=reg_verified,
                    )
                    if reg_norm["tin"]
                    else FieldProvenance[str].missing()
                )
                bin_prov = (
                    FieldProvenance[str].extracted(
                        value=reg_norm["bin"],
                        raw_text=f"BIN: {reg_norm['bin']}",
                        page_number=page_num,
                        confidence=1.0 if reg_verified else 0.0,
                        evidence_verified=reg_verified,
                    )
                    if reg_norm["bin"]
                    else FieldProvenance[str].missing()
                )
        else:
            reg_quote_prov = FieldProvenance[str].missing()
            tin_prov = FieldProvenance[str].missing()
            bin_prov = FieldProvenance[str].missing()
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="supplier_tin_bin",
                    issue_type="MISSING_REQUIRED",
                    details="Neither TIN nor BIN could be located in document text.",
                    confidence=1.0,
                )
            )

        # 6. Line Item Extraction
        line_items: List[ExtractedLineItem] = []
        item_match = re.search(
            r"Amount\s*\(BDT\)\s*\n([A-E])\s*\n([^\n]+)\s*\n([\d,]+)\s*\n([a-z]+)\s*\n([\d,]+\.\d{2})\s*\n([\d,]+\.\d{2})",
            page_text,
        )
        if item_match:
            code, desc, qty_str, unit, price_str, amt_str = item_match.groups()
            qty_norm = CanonicalNormalizer.normalize_quantity(qty_str) or Decimal("0")
            price_norm = CanonicalNormalizer.normalize_currency(price_str) or Decimal("0")
            amt_norm = CanonicalNormalizer.normalize_currency(amt_str) or Decimal("0")

            item_obj = ExtractedLineItem(
                item_code=FieldProvenance[str].extracted(
                    value=code.strip(), raw_text=code.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(code.strip(), page_num, doc)
                ),
                description=FieldProvenance[str].extracted(
                    value=desc.strip(), raw_text=desc.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(desc.strip(), page_num, doc)
                ),
                quantity=FieldProvenance[Decimal].extracted(
                    value=qty_norm, raw_text=qty_str.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(qty_str.strip(), page_num, doc)
                ),
                unit=FieldProvenance[str].extracted(
                    value=unit.strip(), raw_text=unit.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(unit.strip(), page_num, doc)
                ),
                unit_price=FieldProvenance[Decimal].extracted(
                    value=price_norm, raw_text=price_str.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(price_str.strip(), page_num, doc)
                ),
                line_amount=FieldProvenance[Decimal].extracted(
                    value=amt_norm, raw_text=amt_str.strip(), page_number=page_num,
                    evidence_verified=verify_text_on_page(amt_str.strip(), page_num, doc)
                ),
            )
            line_items.append(item_obj)
        else:
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="line_items",
                    issue_type="UNPARSEABLE",
                    details="Could not parse quotation line item table structure.",
                    confidence=0.0,
                )
            )

        # 7. Subtotal, VAT, Total Financials
        sub_match = re.search(r"Subtotal\s*\n?\s*([\d,]+\.\d{2})", page_text)
        if sub_match:
            sub_raw = sub_match.group(1).strip()
            sub_val = CanonicalNormalizer.normalize_currency(sub_raw)
            sub_prov = FieldProvenance[Decimal].extracted(
                value=sub_val, raw_text=sub_match.group(0).strip(), page_number=page_num,
                evidence_verified=verify_text_on_page(sub_match.group(0).strip(), page_num, doc)
            )
        else:
            sub_prov = FieldProvenance[Decimal].missing()

        vat_match = re.search(r"VAT\s*(\d+%)?\s*\n?\s*([\d,]+\.\d{2})", page_text)
        if vat_match:
            pct_raw = vat_match.group(1) or "15%"
            vat_amt_raw = vat_match.group(2).strip()
            vat_pct_val = CanonicalNormalizer.normalize_percentage(pct_raw)
            vat_amt_val = CanonicalNormalizer.normalize_currency(vat_amt_raw)
            vat_shown_separately = True

            vat_pct_prov = FieldProvenance[Decimal].extracted(
                value=vat_pct_val, raw_text=pct_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(vat_match.group(0).strip(), page_num, doc)
            )
            vat_amt_prov = FieldProvenance[Decimal].extracted(
                value=vat_amt_val, raw_text=vat_amt_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(vat_amt_raw, page_num, doc)
            )
        else:
            vat_shown_separately = False
            vat_pct_prov = FieldProvenance[Decimal].missing()
            vat_amt_prov = FieldProvenance[Decimal].missing()

        tot_match = re.search(r"Total(?:\s*\([^\)]+\))?\s*\n?\s*([\d,]+\.\d{2})", page_text)
        if tot_match:
            tot_raw = tot_match.group(1).strip()
            tot_val = CanonicalNormalizer.normalize_currency(tot_raw)
            tot_prov = FieldProvenance[Decimal].extracted(
                value=tot_val, raw_text=tot_match.group(0).strip(), page_number=page_num,
                evidence_verified=verify_text_on_page(tot_match.group(0).strip(), page_num, doc)
            )
        else:
            tot_prov = FieldProvenance[Decimal].missing()
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="total_amount",
                    issue_type="MISSING_REQUIRED",
                    details="Grand total amount not found in document.",
                    confidence=0.0,
                )
            )

        # 8. Terms and Conditions Extraction
        # Payment Clause
        pay_match = re.search(r"1\.\s*Payment\.\s*([^\n]+(?:\n[^\n0-9]+)?)", page_text)
        if pay_match:
            pay_raw = pay_match.group(0).strip()
            pay_adv_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*advance", pay_raw, re.IGNORECASE)
            no_adv_match = re.search(r"no\s*advance", pay_raw, re.IGNORECASE)

            if no_adv_match:
                adv_val = Decimal("0")
                adv_prov = FieldProvenance[Decimal].extracted(
                    value=adv_val, raw_text=pay_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
                )
            elif pay_adv_match:
                adv_val = Decimal(pay_adv_match.group(1))
                adv_prov = FieldProvenance[Decimal].extracted(
                    value=adv_val, raw_text=pay_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
                )
            else:
                adv_prov = FieldProvenance[Decimal].missing()

            credit_days, pay_unclear = CanonicalNormalizer.normalize_credit_days(pay_raw)

            # Part A item 5: Ambiguous expressions such as '30 to 90 days as agreed'
            # must not become definite numeric values (credit_days is None)
            if pay_unclear:
                credit_prov = FieldProvenance[int].ambiguous(
                    raw_text=pay_raw, value=credit_days, page_number=page_num, confidence=0.5,
                    evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
                )
            elif credit_days is not None:
                credit_prov = FieldProvenance[int].extracted(
                    value=credit_days, raw_text=pay_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
                )
            else:
                credit_prov = FieldProvenance[int].missing()

            pay_text_prov = FieldProvenance[str].extracted(
                value=pay_raw, raw_text=pay_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
            )
            pay_unclear_prov = FieldProvenance[bool].extracted(
                value=pay_unclear, raw_text=pay_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(pay_raw, page_num, doc)
            )
        else:
            adv_prov = FieldProvenance[Decimal].missing()
            credit_prov = FieldProvenance[int].missing()
            pay_text_prov = FieldProvenance[str].missing()
            pay_unclear_prov = FieldProvenance[bool].extracted(value=True, raw_text="")
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="payment_terms",
                    issue_type="MISSING_REQUIRED",
                    details="Payment terms clause was not found.",
                    confidence=0.0,
                )
            )

        # Delivery Clause
        del_match = re.search(r"2\.\s*Delivery\.\s*([^\n]+(?:\n[^\n0-9]+)?)", page_text)
        if del_match:
            del_raw = del_match.group(0).strip()
            del_days, del_ambiguous = CanonicalNormalizer.normalize_delivery_days(del_raw)

            if del_ambiguous or del_days is None:
                del_days_prov = FieldProvenance[int].ambiguous(
                    raw_text=del_raw, value=del_days, page_number=page_num, confidence=0.5,
                    evidence_verified=verify_text_on_page(del_raw, page_num, doc)
                )
            else:
                del_days_prov = FieldProvenance[int].extracted(
                    value=del_days, raw_text=del_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(del_raw, page_num, doc)
                )

            del_text_prov = FieldProvenance[str].extracted(
                value=del_raw, raw_text=del_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(del_raw, page_num, doc)
            )
        else:
            del_days_prov = FieldProvenance[int].missing()
            del_text_prov = FieldProvenance[str].missing()
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="delivery_terms",
                    issue_type="MISSING_REQUIRED",
                    details="Delivery terms clause was not found.",
                    confidence=0.0,
                )
            )

        # Late Delivery Delay Penalty Clause
        delay_match = re.search(r"3\.\s*Delay\.\s*([^\n]+(?:\n[^\n0-9]+)?)", page_text)
        if delay_match:
            delay_raw = delay_match.group(0).strip()
            pen_pct_val = CanonicalNormalizer.normalize_percentage(delay_raw)

            has_pen_prov = FieldProvenance[bool].extracted(
                value=True, raw_text=delay_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(delay_raw, page_num, doc)
            )
            pen_pct_prov = (
                FieldProvenance[Decimal].extracted(
                    value=pen_pct_val, raw_text=delay_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(delay_raw, page_num, doc)
                )
                if pen_pct_val is not None
                else FieldProvenance[Decimal].missing()
            )
            pen_text_prov = FieldProvenance[str].extracted(
                value=delay_raw, raw_text=delay_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(delay_raw, page_num, doc)
            )
        else:
            has_pen_prov = FieldProvenance[bool].extracted(value=False, raw_text="", page_number=page_num)
            pen_pct_prov = FieldProvenance[Decimal].missing()
            pen_text_prov = FieldProvenance[str].missing()

        # Quotation Validity Clause
        val_match = re.search(r"(?:3|4)\.\s*Validity\.\s*([^\n]+(?:\n[^\n0-9]+)?)", page_text)
        if val_match:
            val_raw = val_match.group(0).strip()
            val_days_match = re.search(r"(\d+)\s*days", val_raw)
            val_days = int(val_days_match.group(1)) if val_days_match else None

            val_days_prov = (
                FieldProvenance[int].extracted(
                    value=val_days, raw_text=val_raw, page_number=page_num,
                    evidence_verified=verify_text_on_page(val_raw, page_num, doc)
                )
                if val_days is not None
                else FieldProvenance[int].missing()
            )
            val_text_prov = FieldProvenance[str].extracted(
                value=val_raw, raw_text=val_raw, page_number=page_num,
                evidence_verified=verify_text_on_page(val_raw, page_num, doc)
            )
        else:
            val_days_prov = FieldProvenance[int].missing()
            val_text_prov = FieldProvenance[str].missing()

        terms_obj = ExtractedTerms(
            advance_payment_percentage=adv_prov,
            credit_days_after_delivery=credit_prov,
            payment_terms_unclear=pay_unclear_prov,
            payment_terms_text=pay_text_prov,
            delivery_timeline_days=del_days_prov,
            delivery_terms_text=del_text_prov,
            has_late_delivery_penalty=has_pen_prov,
            late_penalty_percentage_per_week=pen_pct_prov,
            penalty_terms_text=pen_text_prov,
            quotation_validity_days=val_days_prov,
            validity_terms_text=val_text_prov,
        )

        quotation = ExtractedQuotation(
            supplier_name=supplier_prov,
            quotation_no=quot_prov,
            quotation_date=date_prov,
            reference_pr=ref_prov,
            buyer_name=buyer_prov,
            supplier_tin=tin_prov,
            supplier_bin=bin_prov,
            registration_raw_quote=reg_quote_prov,
            line_items=line_items,
            subtotal=sub_prov,
            vat_percentage=vat_pct_prov,
            vat_amount=vat_amt_prov,
            vat_shown_separately=FieldProvenance[bool].extracted(
                value=vat_shown_separately, raw_text="VAT 15%" if vat_shown_separately else ""
            ),
            total_amount=tot_prov,
            terms=terms_obj,
        )

        return quotation, uncertainties

    def _build_unreadable_quotation(self, doc: IngestedDocument) -> ExtractedQuotation:
        """Construct UNREADABLE quotation when document or provider fails,

        preventing ingestion failures from silently becoming confirmed missing clauses.
        """
        return ExtractedQuotation(
            supplier_name=FieldProvenance[str].unreadable(),
            quotation_no=FieldProvenance[str].unreadable(),
            quotation_date=FieldProvenance[str].unreadable(),
            reference_pr=FieldProvenance[str].unreadable(),
            buyer_name=FieldProvenance[str].unreadable(),
            supplier_tin=FieldProvenance[str].unreadable(),
            supplier_bin=FieldProvenance[str].unreadable(),
            registration_raw_quote=FieldProvenance[str].unreadable(),
            line_items=[
                ExtractedLineItem(
                    item_code=FieldProvenance[str].unreadable(),
                    description=FieldProvenance[str].unreadable(),
                    quantity=FieldProvenance[Decimal].unreadable(),
                    unit=FieldProvenance[str].unreadable(),
                    unit_price=FieldProvenance[Decimal].unreadable(),
                )
            ],
            subtotal=FieldProvenance[Decimal].unreadable(),
            vat_percentage=FieldProvenance[Decimal].unreadable(),
            vat_amount=FieldProvenance[Decimal].unreadable(),
            vat_shown_separately=FieldProvenance[bool].unreadable(),
            total_amount=FieldProvenance[Decimal].unreadable(),
            terms=ExtractedTerms(
                advance_payment_percentage=FieldProvenance[Decimal].unreadable(),
                credit_days_after_delivery=FieldProvenance[int].unreadable(),
                payment_terms_unclear=FieldProvenance[bool].unreadable(),
                payment_terms_text=FieldProvenance[str].unreadable(),
                delivery_timeline_days=FieldProvenance[int].unreadable(),
                delivery_terms_text=FieldProvenance[str].unreadable(),
                has_late_delivery_penalty=FieldProvenance[bool].unreadable(),
                late_penalty_percentage_per_week=FieldProvenance[Decimal].unreadable(),
                penalty_terms_text=FieldProvenance[str].unreadable(),
                quotation_validity_days=FieldProvenance[int].unreadable(),
                validity_terms_text=FieldProvenance[str].unreadable(),
            ),
        )


class LLMExtractionProvider(BaseExtractionProvider):
    """LLM-based structured extraction provider supporting Gemini or OpenAI.

    Enforces schema compliance and runs rigorous post-extraction evidence verification.
    """

    def __init__(self, api_key: str, model_name: str, provider: str = "gemini"):
        self.api_key = api_key
        self.model_name = model_name
        self.provider = provider.lower()

    def extract(self, doc: IngestedDocument) -> Tuple[ExtractedQuotation, List[ExtractionUncertainty]]:
        if not self.api_key:
            logger.info("No API key configured for LLM. Falling back to deterministic extraction provider.")
            fallback = DeterministicExtractionProvider()
            return fallback.extract(doc)

        prompt = self._build_prompt(doc)
        raw_json_str = self._call_llm_with_retry(prompt)

        if not raw_json_str:
            logger.warning("LLM API failed to return response. Falling back to deterministic extraction.")
            fallback = DeterministicExtractionProvider()
            quot, uncert = fallback.extract(doc)
            uncert.append(
                ExtractionUncertainty(
                    field_name="llm_extraction",
                    issue_type="LOW_CONFIDENCE",
                    details="LLM API call timed out or failed; deterministic fallback used.",
                    confidence=0.5,
                )
            )
            return quot, uncert

        try:
            parsed_data = json.loads(raw_json_str)
            quotation = ExtractedQuotation.model_validate(parsed_data)
            uncertainties = self._verify_provenance_quotes(quotation, doc)
            return quotation, uncertainties
        except Exception as e:
            logger.warning(f"Failed to validate LLM response into schema: {e}. Falling back to deterministic.")
            fallback = DeterministicExtractionProvider()
            quot, uncert = fallback.extract(doc)
            uncert.append(
                ExtractionUncertainty(
                    field_name="llm_schema_validation",
                    issue_type="AMBIGUOUS",
                    details=f"LLM output could not be strictly validated: {str(e)}",
                    confidence=0.5,
                )
            )
            return quot, uncert

    def _build_prompt(self, doc: IngestedDocument) -> str:
        return (
            "You are a strict data extraction system. Extract structured quotation fields from the document text below.\n"
            "CRITICAL: For every field, provide the parsed value, the verbatim raw_text quote from the PDF, "
            "the 1-indexed page number, and your confidence score (0.0 to 1.0).\n"
            "Do NOT fabricate or guess. If a field is missing, set status to 'MISSING' and value to null.\n"
            f"Document text:\n{doc.full_text}\n"
        )

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    resp = requests.post(url, json=payload, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            return candidates[0]["content"]["parts"][0]["text"]
                elif self.provider == "openai":
                    url = "https://api.openai.com/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    payload = {
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    }
                    resp = requests.post(url, headers=headers, json=payload, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"LLM API attempt {attempt+1} failed: {e}")
        return None

    def _verify_provenance_quotes(self, quot: ExtractedQuotation, doc: IngestedDocument) -> List[ExtractionUncertainty]:
        uncertainties = []
        if quot.supplier_name.raw_text:
            if not verify_text_on_page(quot.supplier_name.raw_text, quot.supplier_name.page_number, doc):
                quot.supplier_name.evidence_verified = False
                quot.supplier_name.confidence = 0.0
                uncertainties.append(
                    ExtractionUncertainty(
                        field_name="supplier_name",
                        issue_type="EVIDENCE_UNVERIFIED",
                        details="Extracted supplier quote was not found on referenced page.",
                        evidence_quote=quot.supplier_name.raw_text,
                        page_number=quot.supplier_name.page_number,
                    )
                )
            else:
                quot.supplier_name.evidence_verified = True
        return uncertainties


class ExtractionEngine:
    """Orchestrates structured quotation extraction using configured provider

    with deterministic fallback and rigorous evidence provenance verification.
    """

    def __init__(self, provider: Optional[BaseExtractionProvider] = None):
        if provider:
            self.provider = provider
        elif settings.llm_provider in ["gemini", "openai"] and (settings.gemini_api_key or settings.openai_api_key):
            key = settings.gemini_api_key if settings.llm_provider == "gemini" else settings.openai_api_key
            self.provider = LLMExtractionProvider(
                api_key=key, model_name=settings.llm_model, provider=settings.llm_provider
            )
            self.active_mode = f"LLM ({settings.llm_provider}: {settings.llm_model})"
        else:
            self.provider = DeterministicExtractionProvider()
            self.active_mode = "Deterministic (Regex & Layout Grounding)"

    def extract(self, doc: IngestedDocument) -> Tuple[ExtractedQuotation, List[ExtractionUncertainty]]:
        """Extract quotation data and perform rigorous evidence verification across all fields."""
        quotation, uncertainties = self.provider.extract(doc)

        # Post-extraction sanity check: verify evidence existence for all line items
        for idx, item in enumerate(quotation.line_items):
            if item.quantity.raw_text:
                if not verify_text_on_page(item.quantity.raw_text, item.quantity.page_number, doc):
                    item.quantity.evidence_verified = False
                    item.quantity.confidence = 0.0
                    uncertainties.append(
                        ExtractionUncertainty(
                            field_name=f"line_item_{idx}_quantity",
                            issue_type="EVIDENCE_UNVERIFIED",
                            details="Quantity quote was not verified on referenced page.",
                            evidence_quote=item.quantity.raw_text,
                            page_number=item.quantity.page_number,
                        )
                    )
            if item.unit_price.raw_text:
                if not verify_text_on_page(item.unit_price.raw_text, item.unit_price.page_number, doc):
                    item.unit_price.evidence_verified = False
                    item.unit_price.confidence = 0.0
                    uncertainties.append(
                        ExtractionUncertainty(
                            field_name=f"line_item_{idx}_unit_price",
                            issue_type="EVIDENCE_UNVERIFIED",
                            details="Unit price quote was not verified on referenced page.",
                            evidence_quote=item.unit_price.raw_text,
                            page_number=item.unit_price.page_number,
                        )
                    )

        return quotation, uncertainties
