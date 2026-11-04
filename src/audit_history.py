from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from src.config import settings
from src.models.schemas import DecisionEnum, DocumentVerificationReport

logger = logging.getLogger(__name__)

DHAKA_TZ = ZoneInfo("Asia/Dhaka")


class AuditRecord(BaseModel):
    """Encapsulates a single persisted verification audit record."""

    model_config = ConfigDict(strict=True, extra="ignore")

    verification_id: str
    timestamp_utc: str
    timestamp_dhaka: str
    date_dhaka: str
    supplier_name: str
    document_name: str
    document_hash: str
    quotation_no: str
    matched_pr_item: Optional[str] = "N/A"
    final_decision: str
    primary_reason: str
    all_decision_reasons: List[str] = Field(default_factory=list)
    processing_time_ms: float
    source: str  # 'UPLOAD' or 'BENCHMARK_DEMO'
    created_at_epoch: float


class AuditHistoryRepository:
    """Manages SQLite persistent audit logging with automatic retention and Asia/Dhaka time handling.

    Cloud Persistence Note:
    On ephemeral cloud containers (e.g. Streamlit Community Cloud), the local filesystem
    resets between redeployments or container restarts. For permanent cloud production,
    this repository can be subclassed or adapted to point to external managed storage
    (PostgreSQL, Cloud SQL, Supabase) without requiring changes to the Streamlit UI presentation.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None, retention_hours: int = 24):
        self.db_path = Path(db_path) if db_path else settings.audit_db_path
        self.retention_hours = retention_hours
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Opens connection with timeout and WAL mode enabled for concurrency."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Creates table and indices if they do not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_records (
                    verification_id TEXT PRIMARY KEY,
                    timestamp_utc TEXT NOT NULL,
                    supplier_name TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    document_hash TEXT NOT NULL,
                    quotation_no TEXT NOT NULL,
                    matched_pr_item TEXT,
                    final_decision TEXT NOT NULL,
                    primary_reason TEXT NOT NULL,
                    all_decision_reasons TEXT NOT NULL,
                    processing_time_ms REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at_epoch REAL NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_created ON verification_records (created_at_epoch);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_decision ON verification_records (final_decision);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_source ON verification_records (source);"
            )
            conn.commit()

    def record_verification(
        self, report: DocumentVerificationReport, source: str = "UPLOAD", auto_cleanup: bool = True
    ) -> str:
        """Persists a completed verification report, preventing duplicate entries."""
        v_id = report.verification_id or str(uuid.uuid4())
        report.verification_id = v_id

        # UTC timestamp
        now_utc = datetime.now(timezone.utc)
        timestamp_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        created_at_epoch = now_utc.timestamp()

        # All decision reasons
        all_reasons = report.all_decision_reasons or [report.primary_reason]
        reasons_json = json.dumps(all_reasons, ensure_ascii=False)

        decision_val = (
            report.final_decision.value
            if isinstance(report.final_decision, DecisionEnum)
            else str(report.final_decision)
        )

        with self._get_connection() as conn:
            # Check for immediate duplicates within 10-second window
            cur = conn.cursor()
            cur.execute(
                """
                SELECT verification_id FROM verification_records
                WHERE document_hash = ? AND quotation_no = ? AND source = ?
                  AND created_at_epoch > ?
                LIMIT 1;
                """,
                (report.document_hash, report.quotation_no, source, created_at_epoch - 10.0),
            )
            existing = cur.fetchone()
            if existing:
                logger.debug(f"Skipping duplicate record for {report.document_name} ({report.quotation_no})")
                return existing["verification_id"]

            conn.execute(
                """
                INSERT OR IGNORE INTO verification_records (
                    verification_id, timestamp_utc, supplier_name, document_name,
                    document_hash, quotation_no, matched_pr_item, final_decision,
                    primary_reason, all_decision_reasons, processing_time_ms,
                    source, created_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    v_id,
                    timestamp_utc,
                    report.supplier_name,
                    report.document_name,
                    report.document_hash,
                    report.quotation_no,
                    report.matched_pr_item or "N/A",
                    decision_val,
                    report.primary_reason,
                    reasons_json,
                    float(report.processing_time_ms),
                    source,
                    created_at_epoch,
                ),
            )
            conn.commit()

        if auto_cleanup:
            self.cleanup_expired_records(self.retention_hours)

        return v_id

    def record_batch(
        self, reports: List[DocumentVerificationReport], source: str = "UPLOAD"
    ) -> int:
        """Records a batch of reports in a single transaction, skipping duplicates."""
        if not reports:
            return 0

        recorded_count = 0
        now_utc = datetime.now(timezone.utc)
        timestamp_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        created_at_epoch = now_utc.timestamp()

        with self._get_connection() as conn:
            cur = conn.cursor()
            for r in reports:
                v_id = r.verification_id or str(uuid.uuid4())
                r.verification_id = v_id
                all_reasons = r.all_decision_reasons or [r.primary_reason]
                reasons_json = json.dumps(all_reasons, ensure_ascii=False)
                decision_val = (
                    r.final_decision.value
                    if isinstance(r.final_decision, DecisionEnum)
                    else str(r.final_decision)
                )

                # Check recent duplicate
                cur.execute(
                    """
                    SELECT verification_id FROM verification_records
                    WHERE document_hash = ? AND quotation_no = ? AND source = ?
                      AND created_at_epoch > ?
                    LIMIT 1;
                    """,
                    (r.document_hash, r.quotation_no, source, created_at_epoch - 10.0),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT OR IGNORE INTO verification_records (
                        verification_id, timestamp_utc, supplier_name, document_name,
                        document_hash, quotation_no, matched_pr_item, final_decision,
                        primary_reason, all_decision_reasons, processing_time_ms,
                        source, created_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        v_id,
                        timestamp_utc,
                        r.supplier_name,
                        r.document_name,
                        r.document_hash,
                        r.quotation_no,
                        r.matched_pr_item or "N/A",
                        decision_val,
                        r.primary_reason,
                        reasons_json,
                        float(r.processing_time_ms),
                        source,
                        created_at_epoch,
                    ),
                )
                recorded_count += 1
            conn.commit()

        self.cleanup_expired_records(self.retention_hours)
        return recorded_count

    def cleanup_expired_records(self, retention_hours: Optional[int] = None) -> int:
        """Removes records older than retention period (default: 24h).

        Never executed during export generation to prevent race conditions.
        """
        hours = retention_hours if retention_hours is not None else self.retention_hours
        cutoff_epoch = time.time() - (hours * 3600.0)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM verification_records WHERE created_at_epoch < ?;",
                (cutoff_epoch,),
            )
            deleted = cur.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired verification records (older than {hours}h).")
            return deleted

    def get_records(
        self,
        date_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        start_epoch: Optional[float] = None,
        limit: int = 1000,
    ) -> List[AuditRecord]:
        """Retrieves audit records with Asia/Dhaka timestamps and optional filters."""
        query = "SELECT * FROM verification_records WHERE 1=1"
        params: List[Any] = []

        if start_epoch is not None:
            query += " AND created_at_epoch >= ?"
            params.append(start_epoch)

        if source_filter and source_filter.upper() != "ALL":
            query += " AND source = ?"
            params.append(source_filter.upper())

        query += " ORDER BY created_at_epoch DESC LIMIT ?"
        params.append(limit)

        records: List[AuditRecord] = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()

            for row in rows:
                try:
                    reasons_list = json.loads(row["all_decision_reasons"])
                except Exception:
                    reasons_list = [row["primary_reason"]]

                # Convert UTC timestamp to Asia/Dhaka
                ts_utc_str = row["timestamp_utc"]
                try:
                    dt_utc = datetime.fromisoformat(ts_utc_str.replace("Z", "+00:00"))
                    dt_dhaka = dt_utc.astimezone(DHAKA_TZ)
                    ts_dhaka_str = dt_dhaka.strftime("%Y-%m-%d %I:%M:%S %p")
                    date_dhaka_str = dt_dhaka.strftime("%Y-%m-%d")
                except Exception:
                    ts_dhaka_str = ts_utc_str
                    date_dhaka_str = "Unknown"

                # Apply date filter on Asia/Dhaka date if provided
                if date_filter and date_filter.upper() != "ALL":
                    if date_dhaka_str != date_filter:
                        continue

                rec = AuditRecord(
                    verification_id=row["verification_id"],
                    timestamp_utc=row["timestamp_utc"],
                    timestamp_dhaka=ts_dhaka_str,
                    date_dhaka=date_dhaka_str,
                    supplier_name=row["supplier_name"],
                    document_name=row["document_name"],
                    document_hash=row["document_hash"],
                    quotation_no=row["quotation_no"],
                    matched_pr_item=row["matched_pr_item"] or "N/A",
                    final_decision=row["final_decision"],
                    primary_reason=row["primary_reason"],
                    all_decision_reasons=reasons_list,
                    processing_time_ms=row["processing_time_ms"],
                    source=row["source"],
                    created_at_epoch=row["created_at_epoch"],
                )
                records.append(rec)

        return records

    def get_dashboard_metrics(self, records: List[AuditRecord]) -> Dict[str, Any]:
        """Calculates dashboard executive metrics from the given audit records."""
        total = len(records)
        approved = sum(1 for r in records if r.final_decision == DecisionEnum.APPROVE.value)
        rejected = sum(1 for r in records if r.final_decision == DecisionEnum.REJECT.value)
        review = sum(1 for r in records if r.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW.value)

        rate = (approved / total * 100.0) if total > 0 else 0.0

        return {
            "total_quotations": total,
            "approved_count": approved,
            "rejected_count": rejected,
            "review_count": review,
            "approval_rate_pct": round(rate, 1),
        }

    def get_daily_summary(self, records: List[AuditRecord]) -> List[Dict[str, Any]]:
        """Groups records by Asia/Dhaka local date and calculates summary statistics."""
        daily_map: Dict[str, Dict[str, Any]] = {}

        for r in records:
            d = r.date_dhaka
            if d not in daily_map:
                daily_map[d] = {
                    "Date (Asia/Dhaka)": d,
                    "Total Quotations": 0,
                    "Approved": 0,
                    "Rejected": 0,
                    "Needs Human Review": 0,
                }
            daily_map[d]["Total Quotations"] += 1
            if r.final_decision == DecisionEnum.APPROVE.value:
                daily_map[d]["Approved"] += 1
            elif r.final_decision == DecisionEnum.REJECT.value:
                daily_map[d]["Rejected"] += 1
            else:
                daily_map[d]["Needs Human Review"] += 1

        summary_list = []
        for d in sorted(daily_map.keys(), reverse=True):
            entry = daily_map[d]
            tot = entry["Total Quotations"]
            app = entry["Approved"]
            entry["Approval Rate (%)"] = f"{(app / tot * 100.0):.1f}%" if tot > 0 else "0.0%"
            summary_list.append(entry)

        return summary_list

    def generate_excel_export(self, records: List[AuditRecord]) -> bytes:
        """Generates an Excel (.xlsx) workbook with 3 structured worksheets:

        1. Audit History: One row per completed verification.
        2. Daily Summary: Date-wise counts (Asia/Dhaka) of decisions.
        3. Decision Findings: Individual decision reasons linked to their verification IDs.
        """
        output = io.BytesIO()

        # 1. Audit History Data
        history_rows = []
        for r in records:
            history_rows.append(
                {
                    "Verification ID": r.verification_id,
                    "Timestamp (UTC)": r.timestamp_utc,
                    "Timestamp (Dhaka)": r.timestamp_dhaka,
                    "Date (Dhaka)": r.date_dhaka,
                    "Supplier Name": r.supplier_name,
                    "Document Name": r.document_name,
                    "Quotation Number": r.quotation_no,
                    "PR Item Code": r.matched_pr_item,
                    "Final Decision": r.final_decision,
                    "Primary Reason": r.primary_reason,
                    "All Decision Reasons": " | ".join(r.all_decision_reasons),
                    "Processing Time (ms)": r.processing_time_ms,
                    "Verification Source": r.source,
                }
            )
        df_history = pd.DataFrame(history_rows)

        # 2. Daily Summary Data
        summary_rows = self.get_daily_summary(records)
        df_summary = pd.DataFrame(summary_rows)

        # 3. Decision Findings Data
        findings_rows = []
        for r in records:
            for idx, reason in enumerate(r.all_decision_reasons, start=1):
                findings_rows.append(
                    {
                        "Verification ID": r.verification_id,
                        "Supplier Name": r.supplier_name,
                        "Document Name": r.document_name,
                        "Final Decision": r.final_decision,
                        "Finding Index": idx,
                        "Reason Description": reason,
                    }
                )
        df_findings = pd.DataFrame(findings_rows)

        # Build Excel Workbook
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Sheet 1: Audit History
            if not df_history.empty:
                df_history.to_excel(writer, sheet_name="Audit History", index=False)
            else:
                pd.DataFrame({"Message": ["No audit records available."]}).to_excel(
                    writer, sheet_name="Audit History", index=False
                )

            # Sheet 2: Daily Summary
            if not df_summary.empty:
                df_summary.to_excel(writer, sheet_name="Daily Summary", index=False)
            else:
                pd.DataFrame({"Message": ["No daily activity summary available."]}).to_excel(
                    writer, sheet_name="Daily Summary", index=False
                )

            # Sheet 3: Decision Findings
            if not df_findings.empty:
                df_findings.to_excel(writer, sheet_name="Decision Findings", index=False)
            else:
                pd.DataFrame({"Message": ["No decision findings recorded."]}).to_excel(
                    writer, sheet_name="Decision Findings", index=False
                )

        output.seek(0)
        return output.getvalue()

