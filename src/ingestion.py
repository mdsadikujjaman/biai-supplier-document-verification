import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional
import pypdf
from src.interfaces.base import BaseDocumentIngestor, IngestedDocument

logger = logging.getLogger(__name__)

# Check PyMuPDF availability
try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


class DocumentIngestionEngine(BaseDocumentIngestor):
    """Ingests PDF documents, computes cryptographic hashes, and extracts page-level text."""

    def __init__(self, use_pymupdf: bool = True):
        self.use_pymupdf = use_pymupdf and HAS_PYMUPDF

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def ingest(self, file_path: Path) -> IngestedDocument:
        """Ingests a PDF file, extracting page mappings, text, and SHA-256 provenance."""
        path = Path(file_path)

        if not path.exists():
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash="",
                page_count=0,
                full_text="",
                pages={},
                is_readable=False,
                error_message=f"File not found: {path}",
            )

        if path.stat().st_size == 0:
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash="",
                page_count=0,
                full_text="",
                pages={},
                is_readable=False,
                error_message="File is empty (0 bytes).",
            )

        try:
            file_hash = self.compute_sha256(path)
        except Exception as e:
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash="",
                page_count=0,
                full_text="",
                pages={},
                is_readable=False,
                error_message=f"Failed to read file hash: {str(e)}",
            )

        # Attempt extraction using PyMuPDF first if available, else pypdf
        if self.use_pymupdf:
            try:
                return self._extract_with_pymupdf(path, file_hash)
            except Exception as e:
                logger.warning(
                    f"PyMuPDF extraction failed for {path.name}: {e}. Falling back to pypdf."
                )

        # Fallback / Default pypdf extraction
        try:
            return self._extract_with_pypdf(path, file_hash)
        except Exception as e:
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash=file_hash,
                page_count=0,
                full_text="",
                pages={},
                is_readable=False,
                error_message=f"PDF parsing error: {str(e)}",
            )

    def _extract_with_pymupdf(self, path: Path, file_hash: str) -> IngestedDocument:
        pages: Dict[int, str] = {}
        full_text_parts = []

        doc = pymupdf.open(str(path))
        page_count = len(doc)

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_text = page.get_text() or ""
            page_num = page_idx + 1
            pages[page_num] = page_text
            full_text_parts.append(page_text)

        doc.close()
        full_text = "\n\n".join(full_text_parts)

        # Check for empty text layer
        if not full_text.strip():
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash=file_hash,
                page_count=page_count,
                full_text="",
                pages=pages,
                is_readable=False,
                error_message="PDF contains no extractable text layer (scanned/image only).",
            )

        return IngestedDocument(
            file_path=str(path),
            file_name=path.name,
            file_hash=file_hash,
            page_count=page_count,
            full_text=full_text,
            pages=pages,
            is_readable=True,
            error_message=None,
        )

    def _extract_with_pypdf(self, path: Path, file_hash: str) -> IngestedDocument:
        pages: Dict[int, str] = {}
        full_text_parts = []

        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)

            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                page_num = page_idx + 1
                pages[page_num] = page_text
                full_text_parts.append(page_text)

        full_text = "\n\n".join(full_text_parts)

        if not full_text.strip():
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                file_hash=file_hash,
                page_count=page_count,
                full_text="",
                pages=pages,
                is_readable=False,
                error_message="PDF contains no extractable text layer (scanned/image only).",
            )

        return IngestedDocument(
            file_path=str(path),
            file_name=path.name,
            file_hash=file_hash,
            page_count=page_count,
            full_text=full_text,
            pages=pages,
            is_readable=True,
            error_message=None,
        )

