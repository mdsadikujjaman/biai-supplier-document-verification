from datetime import datetime, timezone, timedelta
from decimal import Decimal
import io
from pathlib import Path
import time
import pytest
import openpyxl

from src.audit_history import AuditHistoryRepository, AuditRecord, DHAKA_TZ
from src.models.schemas import (
    ArithmeticAuditResult,
    DecisionEnum,
    DocumentVerificationReport,
    ExtractionUncertainty,
    PRComparisonReport,
)


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_audit.db"
    return AuditHistoryRepository(db_path=db_file, retention_hours=24)


def create_dummy_report(
    doc_name="quotation.pdf",
    doc_hash="hash_123",
    supplier="Test Supplier",
    quotation_no="QT-001",
    decision=DecisionEnum.APPROVE,
    primary_reason="All rules passed.",
    all_reasons=None,
    pr_item="A",
    latency=10.5,
    v_id=None,
):
    return DocumentVerificationReport(
        verification_id=v_id,
        document_name=doc_name,
        document_path=f"sample_data/{doc_name}",
        document_hash=doc_hash,
        supplier_name=supplier,
        quotation_no=quotation_no,
        matched_pr_item=pr_item,
        final_decision=decision,
        primary_reason=primary_reason,
        all_decision_reasons=all_reasons or [primary_reason],
        rejection_confirmed=(decision == DecisionEnum.REJECT),
        arithmetic_audit=ArithmeticAuditResult(),
        pr_comparison=PRComparisonReport(pr_number="PR-2026-114"),
        processing_time_ms=latency,
    )


# Test 1: Recording a completed verification
def test_1_record_completed_verification(temp_repo):
    rep = create_dummy_report(doc_name="supplier-01.pdf", quotation_no="Q-100")
    v_id = temp_repo.record_verification(rep, source="UPLOAD")
    assert v_id is not None
    assert len(v_id) > 0

    records = temp_repo.get_records()
    assert len(records) == 1
    assert records[0].verification_id == v_id
    assert records[0].supplier_name == "Test Supplier"
    assert records[0].document_name == "supplier-01.pdf"
    assert records[0].source == "UPLOAD"


# Test 2: Preventing duplicate records on reruns
def test_2_prevent_duplicate_records_on_reruns(temp_repo):
    rep = create_dummy_report(doc_hash="same_hash", quotation_no="Q-SAME", v_id="fixed-uuid-1")
    id1 = temp_repo.record_verification(rep, source="UPLOAD")
    # Immediate repeat attempt (e.g. Streamlit rerun)
    id2 = temp_repo.record_verification(rep, source="UPLOAD")

    assert id1 == id2
    records = temp_repo.get_records()
    assert len(records) == 1


# Test 3: Retrieving records by date
def test_3_retrieve_records_by_date(temp_repo):
    rep = create_dummy_report(quotation_no="Q-DATE")
    temp_repo.record_verification(rep, source="UPLOAD")

    now_dhaka = datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    records_today = temp_repo.get_records(date_filter=now_dhaka)
    assert len(records_today) == 1
    assert records_today[0].date_dhaka == now_dhaka

    records_future = temp_repo.get_records(date_filter="2099-01-01")
    assert len(records_future) == 0


# Test 4: Correct Asia/Dhaka date grouping
def test_4_correct_dhaka_date_grouping(temp_repo):
    rep1 = create_dummy_report(quotation_no="Q-D1", decision=DecisionEnum.APPROVE)
    rep2 = create_dummy_report(quotation_no="Q-D2", decision=DecisionEnum.REJECT)
    temp_repo.record_batch([rep1, rep2], source="UPLOAD")

    records = temp_repo.get_records()
    summary = temp_repo.get_daily_summary(records)

    assert len(summary) >= 1
    today_dhaka = datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    today_entry = next((s for s in summary if s["Date (Asia/Dhaka)"] == today_dhaka), None)
    assert today_entry is not None
    assert today_entry["Total Quotations"] == 2
    assert today_entry["Approved"] == 1
    assert today_entry["Rejected"] == 1


# Test 5: 24-hour expiration and cleanup
def test_5_expiration_cleanup_24_hours(temp_repo):
    # Record recent item
    rep_recent = create_dummy_report(quotation_no="Q-RECENT", v_id="recent-1")
    temp_repo.record_verification(rep_recent, source="UPLOAD", auto_cleanup=False)

    # Insert an artificially expired record (30 hours old)
    old_time_utc = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old_epoch = time.time() - (30 * 3600.0)

    with temp_repo._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO verification_records (
                verification_id, timestamp_utc, supplier_name, document_name,
                document_hash, quotation_no, matched_pr_item, final_decision,
                primary_reason, all_decision_reasons, processing_time_ms,
                source, created_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "old-record-id",
                old_time_utc,
                "Old Supplier",
                "old.pdf",
                "old_hash",
                "Q-OLD",
                "B",
                "REJECT",
                "Old reason",
                '["Old reason"]',
                5.0,
                "UPLOAD",
                old_epoch,
            ),
        )
        conn.commit()

    all_before = temp_repo.get_records()
    assert len(all_before) == 2

    # Run cleanup with 24 hours retention
    deleted = temp_repo.cleanup_expired_records(retention_hours=24)
    assert deleted == 1

    all_after = temp_repo.get_records()
    assert len(all_after) == 1
    assert all_after[0].quotation_no == "Q-RECENT"


# Test 6: Empty audit history
def test_6_empty_audit_history(temp_repo):
    records = temp_repo.get_records()
    assert len(records) == 0

    metrics = temp_repo.get_dashboard_metrics(records)
    assert metrics["total_quotations"] == 0
    assert metrics["approved_count"] == 0
    assert metrics["rejected_count"] == 0
    assert metrics["review_count"] == 0
    assert metrics["approval_rate_pct"] == 0.0

    summary = temp_repo.get_daily_summary(records)
    assert len(summary) == 0

    # Excel generation handles empty gracefully
    excel_bytes = temp_repo.generate_excel_export(records)
    assert len(excel_bytes) > 0


# Test 7: Correct dashboard counts
def test_7_correct_dashboard_counts(temp_repo):
    reps = [
        create_dummy_report(quotation_no="Q-1", decision=DecisionEnum.APPROVE, v_id="c-1"),
        create_dummy_report(quotation_no="Q-2", decision=DecisionEnum.APPROVE, v_id="c-2"),
        create_dummy_report(quotation_no="Q-3", decision=DecisionEnum.REJECT, v_id="c-3"),
        create_dummy_report(quotation_no="Q-4", decision=DecisionEnum.NEEDS_HUMAN_REVIEW, v_id="c-4"),
    ]
    temp_repo.record_batch(reps, source="UPLOAD")
    records = temp_repo.get_records()
    metrics = temp_repo.get_dashboard_metrics(records)

    assert metrics["total_quotations"] == 4
    assert metrics["approved_count"] == 2
    assert metrics["rejected_count"] == 1
    assert metrics["review_count"] == 1
    assert metrics["approval_rate_pct"] == 50.0


# Test 8: Correct decision distribution
def test_8_correct_decision_distribution(temp_repo):
    reps = [
        create_dummy_report(quotation_no="Q-A", decision=DecisionEnum.APPROVE, v_id="dist-1"),
        create_dummy_report(quotation_no="Q-R1", decision=DecisionEnum.REJECT, v_id="dist-2"),
        create_dummy_report(quotation_no="Q-R2", decision=DecisionEnum.REJECT, v_id="dist-3"),
    ]
    temp_repo.record_batch(reps, source="UPLOAD")
    records = temp_repo.get_records()
    metrics = temp_repo.get_dashboard_metrics(records)

    assert metrics["approved_count"] == 1
    assert metrics["rejected_count"] == 2
    assert metrics["review_count"] == 0


# Test 9: Benchmark-demo versus upload source filtering
def test_9_benchmark_demo_vs_upload_filtering(temp_repo):
    rep_up = create_dummy_report(quotation_no="Q-UP", v_id="src-1")
    rep_demo = create_dummy_report(quotation_no="Q-DEMO", v_id="src-2")

    temp_repo.record_verification(rep_up, source="UPLOAD")
    temp_repo.record_verification(rep_demo, source="BENCHMARK_DEMO")

    all_records = temp_repo.get_records()
    assert len(all_records) == 2

    upload_only = temp_repo.get_records(source_filter="UPLOAD")
    assert len(upload_only) == 1
    assert upload_only[0].quotation_no == "Q-UP"
    assert upload_only[0].source == "UPLOAD"

    demo_only = temp_repo.get_records(source_filter="BENCHMARK_DEMO")
    assert len(demo_only) == 1
    assert demo_only[0].quotation_no == "Q-DEMO"
    assert demo_only[0].source == "BENCHMARK_DEMO"


# Test 10: Excel workbook generation and worksheet contents
def test_10_excel_workbook_generation(temp_repo):
    rep1 = create_dummy_report(
        supplier="Padma Ltd",
        quotation_no="Q-EX1",
        decision=DecisionEnum.APPROVE,
        all_reasons=["Reason 1", "Reason 2"],
        v_id="ex-1",
    )
    rep2 = create_dummy_report(
        supplier="Jamuna Ltd",
        quotation_no="Q-EX2",
        decision=DecisionEnum.REJECT,
        all_reasons=["Price violation"],
        v_id="ex-2",
    )
    temp_repo.record_batch([rep1, rep2], source="UPLOAD")
    records = temp_repo.get_records()

    excel_bytes = temp_repo.generate_excel_export(records)
    assert excel_bytes is not None
    assert len(excel_bytes) > 1000

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    sheet_names = wb.sheetnames
    assert "Audit History" in sheet_names
    assert "Daily Summary" in sheet_names
    assert "Decision Findings" in sheet_names

    # Check Audit History rows
    ws_history = wb["Audit History"]
    assert ws_history.max_row >= 3  # Header + 2 data rows

    # Check Decision Findings rows
    ws_findings = wb["Decision Findings"]
    assert ws_findings.max_row >= 4  # Header + 2 reasons for rep1 + 1 reason for rep2


# Test 11: Multiple records with different decisions
def test_11_multiple_records_different_decisions(temp_repo):
    decisions = [
        DecisionEnum.APPROVE,
        DecisionEnum.REJECT,
        DecisionEnum.NEEDS_HUMAN_REVIEW,
    ]
    reps = [
        create_dummy_report(quotation_no=f"Q-DIFF-{idx}", decision=d, v_id=f"diff-{idx}")
        for idx, d in enumerate(decisions)
    ]
    temp_repo.record_batch(reps, source="UPLOAD")
    records = temp_repo.get_records()

    retrieved_decisions = {r.final_decision for r in records}
    assert retrieved_decisions == {"APPROVE", "REJECT", "NEEDS HUMAN REVIEW"}
