from decimal import Decimal
from enum import Enum
from typing import Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DecisionEnum(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_HUMAN_REVIEW = "NEEDS HUMAN REVIEW"


class RuleCategory(str, Enum):
    REJECT = "REJECT"
    HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    EXTRACTION_UNCERTAINTY = "EXTRACTION_UNCERTAINTY"
    INFO = "INFO"


class ExtractionStatus(str, Enum):
    """Explicit status indicating extraction outcome for a specific field."""

    EXTRACTED = "EXTRACTED"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    UNREADABLE = "UNREADABLE"
    CONFLICTING = "CONFLICTING"


class RuleStatus(str, Enum):
    """Execution status of an individual company rule evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"  # Rule condition triggered (violation / review trigger)
    UNCERTAIN = "UNCERTAIN"  # Field is unverified, unreadable, or ambiguous
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FieldProvenance(BaseModel, Generic[T]):
    """Encapsulates any extracted value with its original text provenance,

    page number, extraction status, and verification flag.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    status: ExtractionStatus = Field(
        default=ExtractionStatus.EXTRACTED,
        description="Extraction status: EXTRACTED, MISSING, AMBIGUOUS, UNREADABLE, CONFLICTING",
    )
    value: Optional[T] = Field(default=None, description="Parsed domain value")
    raw_text: Optional[str] = Field(
        default=None, description="Verbatim text quote from PDF if found"
    )
    page_number: Optional[int] = Field(
        default=None, ge=1, description="1-indexed PDF page number where text was found"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (0.0 - 1.0)"
    )
    evidence_verified: bool = Field(
        default=False,
        description="True if raw_text was confirmed to exist on the referenced PDF page",
    )

    @classmethod
    def missing(cls, field_name: str = "") -> "FieldProvenance[T]":
        """Convenience factory for missing fields without inventing fake text."""
        return cls(
            status=ExtractionStatus.MISSING,
            value=None,
            raw_text=None,
            page_number=None,
            confidence=1.0,
            evidence_verified=False,
        )

    @classmethod
    def unreadable(cls, field_name: str = "") -> "FieldProvenance[T]":
        """Convenience factory when field could not be read due to file/provider failure."""
        return cls(
            status=ExtractionStatus.UNREADABLE,
            value=None,
            raw_text=None,
            page_number=None,
            confidence=0.0,
            evidence_verified=False,
        )

    @classmethod
    def extracted(
        cls,
        value: T,
        raw_text: str,
        page_number: int = 1,
        confidence: float = 1.0,
        evidence_verified: bool = True,
    ) -> "FieldProvenance[T]":
        """Convenience factory for cleanly extracted fields."""
        return cls(
            status=ExtractionStatus.EXTRACTED,
            value=value,
            raw_text=raw_text,
            page_number=page_number,
            confidence=confidence,
            evidence_verified=evidence_verified,
        )

    @classmethod
    def ambiguous(
        cls,
        raw_text: str,
        value: Optional[T] = None,
        page_number: int = 1,
        confidence: float = 0.5,
        evidence_verified: bool = True,
    ) -> "FieldProvenance[T]":
        """Convenience factory for ambiguous terms (value must remain None if indefinite)."""
        return cls(
            status=ExtractionStatus.AMBIGUOUS,
            value=value,
            raw_text=raw_text,
            page_number=page_number,
            confidence=confidence,
            evidence_verified=evidence_verified,
        )

    @classmethod
    def conflicting(
        cls,
        raw_text: str,
        value: Optional[T] = None,
        page_number: int = 1,
        confidence: float = 0.0,
        evidence_verified: bool = True,
    ) -> "FieldProvenance[T]":
        """Convenience factory for contradictory or conflicting expressions."""
        return cls(
            status=ExtractionStatus.CONFLICTING,
            value=value,
            raw_text=raw_text,
            page_number=page_number,
            confidence=confidence,
            evidence_verified=evidence_verified,
        )


class PurchaseRequestItem(BaseModel):
    """Line item requested in the Purchase Request."""

    model_config = ConfigDict(strict=True, extra="forbid")

    item_code: str = Field(..., min_length=1, description="Item code, e.g. 'A'")
    description: str = Field(..., min_length=1, description="Item description")
    unit: str = Field(..., min_length=1, description="Measurement unit, e.g. 'metre'")
    quantity_requested: Decimal = Field(..., gt=0)
    maximum_unit_price: Decimal = Field(..., gt=0)

    @property
    def price_rejection_ceiling(self) -> Decimal:
        """3% above maximum unit price: Price_Max * 1.03."""
        return (self.maximum_unit_price * Decimal("1.03")).quantize(Decimal("0.0001"))

    @property
    def min_quantity_tolerance(self) -> Decimal:
        """-5% of requested quantity: Qty * 0.95."""
        return (self.quantity_requested * Decimal("0.95")).quantize(Decimal("0.0001"))

    @property
    def max_quantity_tolerance(self) -> Decimal:
        """+5% of requested quantity: Qty * 1.05."""
        return (self.quantity_requested * Decimal("1.05")).quantize(Decimal("0.0001"))


class PurchaseRequest(BaseModel):
    """Full Purchase Request representation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pr_number: str = Field(..., min_length=1, description="PR identifier, e.g. 'PR-2026-114'")
    items: Dict[str, PurchaseRequestItem] = Field(
        ..., description="Items mapped by item_code (A, B, C, D, E)"
    )


class ExtractedLineItem(BaseModel):
    """Line item extracted from a supplier quotation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    item_code: FieldProvenance[str]
    description: FieldProvenance[str]
    quantity: FieldProvenance[Decimal]
    unit: FieldProvenance[str]
    unit_price: FieldProvenance[Decimal]
    line_amount: Optional[FieldProvenance[Decimal]] = None


class ExtractedTerms(BaseModel):
    """Commercial, delivery, and contractual terms extracted from quotation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    advance_payment_percentage: FieldProvenance[Decimal] = Field(
        default_factory=lambda: FieldProvenance[Decimal].missing()
    )
    credit_days_after_delivery: FieldProvenance[int] = Field(
        default_factory=lambda: FieldProvenance[int].missing()
    )
    payment_terms_unclear: FieldProvenance[bool] = Field(
        default_factory=lambda: FieldProvenance[bool].extracted(value=False, raw_text="")
    )
    payment_terms_text: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )

    delivery_timeline_days: FieldProvenance[int] = Field(
        default_factory=lambda: FieldProvenance[int].missing()
    )
    delivery_terms_text: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )

    has_late_delivery_penalty: FieldProvenance[bool] = Field(
        default_factory=lambda: FieldProvenance[bool].extracted(value=False, raw_text="")
    )
    late_penalty_percentage_per_week: FieldProvenance[Decimal] = Field(
        default_factory=lambda: FieldProvenance[Decimal].missing()
    )
    penalty_terms_text: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )

    quotation_validity_days: FieldProvenance[int] = Field(
        default_factory=lambda: FieldProvenance[int].missing()
    )
    validity_terms_text: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )


class ExtractedQuotation(BaseModel):
    """Full extracted supplier quotation pack."""

    model_config = ConfigDict(strict=True, extra="forbid")

    supplier_name: FieldProvenance[str]
    quotation_no: FieldProvenance[str]
    quotation_date: FieldProvenance[str]
    reference_pr: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )
    buyer_name: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )

    supplier_tin: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )
    supplier_bin: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )
    registration_raw_quote: FieldProvenance[str] = Field(
        default_factory=lambda: FieldProvenance[str].missing()
    )

    line_items: List[ExtractedLineItem] = Field(..., min_length=1)

    subtotal: FieldProvenance[Decimal] = Field(
        default_factory=lambda: FieldProvenance[Decimal].missing()
    )
    vat_percentage: FieldProvenance[Decimal] = Field(
        default_factory=lambda: FieldProvenance[Decimal].missing()
    )
    vat_amount: FieldProvenance[Decimal] = Field(
        default_factory=lambda: FieldProvenance[Decimal].missing()
    )
    vat_shown_separately: FieldProvenance[bool] = Field(
        default_factory=lambda: FieldProvenance[bool].extracted(value=False, raw_text="")
    )
    total_amount: FieldProvenance[Decimal]

    terms: ExtractedTerms


class ExtractionUncertainty(BaseModel):
    """Records any uncertainty, ambiguity, or conflict discovered during extraction."""

    model_config = ConfigDict(strict=True, extra="forbid")

    field_name: str
    issue_type: str = Field(
        ...,
        description="'LOW_CONFIDENCE', 'AMBIGUOUS', 'CONFLICT', 'UNPARSEABLE', 'MISSING_REQUIRED', 'EVIDENCE_UNVERIFIED'",
    )
    details: str
    evidence_quote: Optional[str] = None
    page_number: Optional[int] = None
    confidence: float = 0.0


class RuleCheckResult(BaseModel):
    """Result of an individual company business rule evaluation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    rule_id: str = Field(..., description="e.g. 'REJECT_RULE_1', 'REVIEW_RULE_6'")
    rule_name: str
    category: RuleCategory
    status: RuleStatus = Field(default=RuleStatus.PASS, description="PASS, FAIL, UNCERTAIN, NOT_APPLICABLE")
    triggered: bool = False
    is_confirmed: bool = Field(
        default=False,
        description="True only if high confidence and non-ambiguous data supports it",
    )
    explanation: str = ""
    actual_value: Optional[str] = None
    expected_condition: Optional[str] = None
    evidence_quote: str = ""
    page_number: Optional[int] = 1
    confidence: float = 1.0
    details: str = ""


# ==========================================
# Arithmetic and PR Comparison Domain Schemas
# ==========================================
class LineItemArithmeticCheck(BaseModel):
    """Detailed calculation audit for a single line item."""

    model_config = ConfigDict(strict=True, extra="forbid")

    item_code: str
    quantity: Decimal
    unit_price: Decimal
    calculated_amount: Decimal
    quoted_amount: Optional[Decimal] = None
    difference: Decimal = Decimal("0.00")
    matches: bool = True
    evidence_quote: str = ""


class ArithmeticDiscrepancy(BaseModel):
    """Records an explicit arithmetic error or inconsistency."""

    model_config = ConfigDict(strict=True, extra="forbid")

    component: str  # 'LINE_AMOUNT', 'SUBTOTAL', 'VAT', 'TOTAL'
    expected_value: Decimal
    quoted_value: Optional[Decimal] = None
    discrepancy_amount: Decimal
    evidence_quote: str
    details: str


class ArithmeticAuditResult(BaseModel):
    """Results of mathematical and calculation consistency verification."""

    model_config = ConfigDict(strict=True, extra="forbid")

    line_calculations_match: bool = True
    subtotal_matches_lines: bool = True
    vat_matches_subtotal_15pct: bool = True
    total_matches_sum: bool = True
    vat_shown_separately: bool = True

    calculated_subtotal: Optional[Decimal] = None
    calculated_vat: Optional[Decimal] = None
    calculated_total: Optional[Decimal] = None

    quoted_subtotal: Optional[Decimal] = None
    quoted_vat: Optional[Decimal] = None
    quoted_total: Optional[Decimal] = None

    line_checks: List[LineItemArithmeticCheck] = []
    discrepancies: List[ArithmeticDiscrepancy] = []
    discrepancy_details: List[str] = []

    @property
    def all_passed(self) -> bool:
        return (
            self.line_calculations_match
            and self.subtotal_matches_lines
            and self.vat_matches_subtotal_15pct
            and self.total_matches_sum
            and self.vat_shown_separately
        )


class ItemComparisonResult(BaseModel):
    """Comparison of a quoted line item against the Purchase Request benchmark."""

    model_config = ConfigDict(strict=True, extra="forbid")

    item_code: str
    pr_description: str
    quoted_description: str
    description_match: bool

    pr_unit: str
    quoted_unit: str
    unit_match: bool

    requested_quantity: Decimal
    quoted_quantity: Decimal
    quantity_difference: Decimal
    quantity_variance_pct: Decimal  # ((quoted - requested) / requested) * 100
    quantity_within_tolerance: bool  # within ±5%

    max_unit_price: Decimal
    quoted_unit_price: Decimal
    price_difference: Decimal
    price_variance_pct: Decimal  # ((quoted - max) / max) * 100
    price_rejection_ceiling: Decimal  # max * 1.03
    price_is_below_or_equal_max: bool
    price_is_within_review_band: bool  # max < price <= ceiling
    price_exceeds_rejection_ceiling: bool  # price > ceiling

    evidence_quote: str
    is_valid_match: bool


class PRComparisonReport(BaseModel):
    """Comprehensive comparison of quotation against Purchase Request."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pr_number: str
    matched_items: List[ItemComparisonResult] = []
    unknown_item_codes: List[str] = []
    unmatched_pr_items: List[str] = []
    duplicate_item_codes: List[str] = []
    has_unit_mismatch: bool = False
    has_description_mismatch: bool = False
    comparison_notes: List[str] = []


class DocumentVerificationReport(BaseModel):
    """Final comprehensive verification report for a supplier pack."""

    model_config = ConfigDict(strict=True, extra="forbid")

    document_name: str
    document_path: str
    document_hash: str
    supplier_name: str
    quotation_no: str
    matched_pr_item: Optional[str] = None

    final_decision: DecisionEnum
    primary_reason: str
    rejection_confirmed: bool = False

    arithmetic_audit: ArithmeticAuditResult
    pr_comparison: Optional[PRComparisonReport] = None
    extraction_uncertainties: List[ExtractionUncertainty] = []
    triggered_rules: List[RuleCheckResult] = []
    all_evaluated_rules: List[RuleCheckResult] = []
    supporting_evidence_quotes: List[str] = []
    processing_time_ms: float = 0.0
