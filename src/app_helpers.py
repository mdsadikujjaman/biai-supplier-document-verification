import json
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from src.models.schemas import DecisionEnum

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit per PDF document


def validate_uploaded_pdf(file_name: str, file_size: int, max_bytes: int = MAX_FILE_SIZE_BYTES) -> Tuple[bool, str]:
    """Validates that uploaded file is a valid PDF within acceptable size limits."""
    if not file_name.lower().endswith(".pdf"):
        return False, f"Invalid file format: '{file_name}'. Only PDF files are supported."

    if file_size <= 0:
        return False, f"Empty file: '{file_name}' contains 0 bytes."

    if file_size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"File too large: '{file_name}' is {actual_mb:.1f} MB (maximum allowed is {max_mb:.0f} MB)."

    return True, ""


def save_uploaded_stream_to_temp(uploaded_file, target_dir: Path) -> Path:
    """Safely saves an uploaded file buffer to a dedicated temporary directory.

    Guarantees isolation and ensures temporary file cleanup.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = target_dir / uploaded_file.name

    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return temp_file_path


def cleanup_directory(directory: Optional[Path]) -> None:
    """Safely removes temporary directory and its contents."""
    if directory and directory.exists() and directory.is_dir():
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary directory {directory}: {e}")


def load_benchmark_report_json(reports_path: Path = Path("reports/evaluation_summary.json")) -> Optional[Dict[str, Any]]:
    """Loads benchmark evaluation JSON summary."""
    if not reports_path.exists():
        return None
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading benchmark report from {reports_path}: {e}")
        return None


def load_benchmark_report_markdown(reports_path: Path = Path("reports/audit_summary.md")) -> Optional[str]:
    """Loads benchmark executive audit markdown report."""
    if not reports_path.exists():
        return None
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading markdown report from {reports_path}: {e}")
        return None


def get_decision_color_theme(decision: DecisionEnum) -> Dict[str, str]:
    """Returns accessible color styles and icons for each decision state."""
    if decision == DecisionEnum.APPROVE:
        return {
            "bg": "#ecfdf5",
            "border": "#10b981",
            "text": "#065f46",
            "badge": "🟢 APPROVED",
            "icon": "✅",
        }
    elif decision == DecisionEnum.REJECT:
        return {
            "bg": "#fef2f2",
            "border": "#ef4444",
            "text": "#991b1b",
            "badge": "🔴 REJECTED",
            "icon": "❌",
        }
    else:
        return {
            "bg": "#fffbeb",
            "border": "#f59e0b",
            "text": "#92400e",
            "badge": "🟡 NEEDS HUMAN REVIEW",
            "icon": "⚠️",
        }

