import json
from decimal import Decimal
import pytest
from src.decision_engine import DecisionEngine
from src.models.schemas import DecisionEnum
from src.report_generator import (
    generate_batch_csv_summary,
    generate_batch_json_summary,
    generate_batch_markdown_summary,
    generate_individual_json_report,
    generate_individual_markdown_report,
)


@pytest.fixture(scope="module")
def sample_reports():
    engine = DecisionEngine()
    rep1 = engine.verify_document("sample_data/supplier-pack-01.pdf")
    rep3 = engine.verify_document("sample_data/supplier-pack-03.pdf")
    rep4 = engine.verify_document("sample_data/supplier-pack-04.pdf")
    return [rep1, rep3, rep4]


def test_generate_individual_markdown_report(sample_reports):
    rep = sample_reports[0]
    md = generate_individual_markdown_report(rep)

    assert "# Supplier Quotation Verification Audit Report" in md
    assert rep.supplier_name in md
    assert rep.document_name in md
    assert "🟢 **APPROVE**" in md
    assert "## 3. Financial & Arithmetic Audit" in md
    assert "## 5. Complete Company Business Rules Matrix" in md


def test_generate_individual_json_report(sample_reports):
    rep = sample_reports[1]  # Pack 03 (REJECT)
    json_str = generate_individual_json_report(rep)
    data = json.loads(json_str)

    assert data["document_name"] == "supplier-pack-03.pdf"
    assert data["final_decision"] == "REJECT"
    assert data["rejection_confirmed"] is True
    assert len(data["triggered_rules"]) >= 1


def test_generate_batch_csv_summary(sample_reports):
    csv_str = generate_batch_csv_summary(sample_reports)
    lines = csv_str.strip().split("\n")

    # Header + 3 document rows = 4 lines
    assert len(lines) == 4
    assert "Document Name,Document SHA256" in lines[0]
    assert "supplier-pack-01.pdf" in lines[1]
    assert "supplier-pack-03.pdf" in lines[2]
    assert "supplier-pack-04.pdf" in lines[3]


def test_generate_batch_markdown_summary(sample_reports):
    md = generate_batch_markdown_summary(sample_reports)

    assert "# Batch Supplier Verification Summary" in md
    assert "**Total Documents Audited:** `3`" in md
    assert "supplier-pack-01.pdf" in md
    assert "🟢 APPROVE" in md
    assert "🔴 REJECT" in md
    assert "🟡 NEEDS REVIEW" in md


def test_generate_batch_json_summary(sample_reports):
    json_str = generate_batch_json_summary(sample_reports)
    data = json.loads(json_str)

    assert data["total_documents"] == 3
    assert len(data["reports"]) == 3
    assert data["reports"][0]["document_name"] == "supplier-pack-01.pdf"

