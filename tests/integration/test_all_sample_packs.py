from pathlib import Path
import pytest
from src.decision_engine import DecisionEngine
from src.evaluation import GROUND_TRUTH, EvaluationBenchmark
from src.models.schemas import DecisionEnum


@pytest.fixture(scope="module")
def decision_engine():
    return DecisionEngine()


@pytest.mark.parametrize(
    "filename,expected_decision,expected_primary_rule",
    [
        ("supplier-pack-01.pdf", DecisionEnum.APPROVE, None),
        ("supplier-pack-02.pdf", DecisionEnum.APPROVE, None),
        ("supplier-pack-03.pdf", DecisionEnum.REJECT, "REJECT_RULE_1"),
        ("supplier-pack-04.pdf", DecisionEnum.NEEDS_HUMAN_REVIEW, "REVIEW_RULE_1"),
        ("supplier-pack-05.pdf", DecisionEnum.REJECT, "REJECT_RULE_2"),
        ("supplier-pack-06.pdf", DecisionEnum.REJECT, "REJECT_RULE_3"),
        ("supplier-pack-07.pdf", DecisionEnum.NEEDS_HUMAN_REVIEW, "REVIEW_RULE_2"),
        ("supplier-pack-08.pdf", DecisionEnum.REJECT, "REJECT_RULE_4"),
        ("supplier-pack-09.pdf", DecisionEnum.NEEDS_HUMAN_REVIEW, "REVIEW_RULE_6"),
        ("supplier-pack-10.pdf", DecisionEnum.REJECT, "REJECT_RULE_5"),
    ],
)
def test_sample_pack_end_to_end(decision_engine, filename, expected_decision, expected_primary_rule):
    pdf_path = Path("sample_data") / filename
    assert pdf_path.exists(), f"Sample file {filename} must exist in sample_data/"

    report = decision_engine.verify_document(pdf_path)

    # 1. Exact Decision Match
    assert (
        report.final_decision == expected_decision
    ), f"Decision mismatch for {filename}: expected {expected_decision}, got {report.final_decision}. Reason: {report.primary_reason}"

    # 2. Rejection Confirmation Flag Integrity
    if expected_decision == DecisionEnum.REJECT:
        assert report.rejection_confirmed is True
        assert len(report.triggered_rules) >= 1
    else:
        assert report.rejection_confirmed is False

    # 3. Primary Rule Trigger Verification
    if expected_primary_rule:
        triggered_ids = [r.rule_id for r in report.triggered_rules]
        assert (
            expected_primary_rule in triggered_ids
        ), f"Expected rule {expected_primary_rule} was not triggered in {filename}. Triggered: {triggered_ids}"

    # 4. Evidence Grounding & Metadata Integrity
    assert report.document_hash and len(report.document_hash) == 64
    assert report.supplier_name and report.supplier_name != "Unknown"
    assert report.quotation_no and report.quotation_no != "Unknown"
    assert report.processing_time_ms > 0


def test_full_evaluation_benchmark_suite(decision_engine):
    """Runs the benchmark suite and verifies zero false approvals and 100% accuracy."""
    benchmark = EvaluationBenchmark(engine=decision_engine)
    summary, results, reports = benchmark.run_benchmark("sample_data")

    # Benchmark assertions
    assert summary.total_documents == 10
    assert summary.correct_decisions == 10
    assert summary.accuracy_percentage == 100.0
    assert summary.false_approvals == 0, "Safety violation: false approvals must strictly be 0!"
    assert summary.false_rejections == 0
    assert summary.extraction_failure_count == 0
    assert summary.all_packs_passed_benchmark is True
    assert summary.mean_processing_time_ms < 500.0  # Fast execution benchmark

