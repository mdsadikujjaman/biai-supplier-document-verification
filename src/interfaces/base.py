from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from src.models.schemas import (
    ArithmeticAuditResult,
    DocumentVerificationReport,
    ExtractedQuotation,
    ExtractionUncertainty,
    PurchaseRequest,
)


class IngestedDocument(BaseModel):
    """Raw ingested document container with full text, page mappings, and metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    file_path: str
    file_name: str
    file_hash: str
    page_count: int
    full_text: str
    pages: Dict[int, str]  # 1-indexed page number -> page text
    is_readable: bool = True
    error_message: Optional[str] = None


class BaseDocumentIngestor(ABC):
    """Abstract interface for document ingestion and text extraction."""

    @abstractmethod
    def ingest(self, file_path: Path) -> IngestedDocument:
        """Ingest a PDF file and extract its page text, metadata, and hash."""
        pass


class BasePRLoader(ABC):
    """Abstract interface for loading and parsing Purchase Request data."""

    @abstractmethod
    def load(self, csv_path: Path) -> PurchaseRequest:
        """Parse Purchase Request CSV into domain model."""
        pass


class BaseStructuredExtractor(ABC):
    """Abstract interface for structured information extraction with provenance."""

    @abstractmethod
    def extract(self, document: IngestedDocument) -> ExtractedQuotation:
        """Extract structured quotation data with quotes, pages, and confidence."""
        pass


class BaseArithmeticVerifier(ABC):
    """Abstract interface for arithmetic and calculation verification."""

    @abstractmethod
    def verify(self, quotation: ExtractedQuotation) -> ArithmeticAuditResult:
        """Recalculate line items, subtotals, VAT, and grand totals."""
        pass


class BaseRuleEngine(ABC):
    """Abstract interface for deterministic company rule evaluation."""

    @abstractmethod
    def evaluate(
        self,
        document: IngestedDocument,
        quotation: ExtractedQuotation,
        purchase_request: PurchaseRequest,
        math_audit: ArithmeticAuditResult,
        uncertainties: List[ExtractionUncertainty],
    ) -> DocumentVerificationReport:
        """Execute deterministic rule evaluation and produce final verification report."""
        pass

