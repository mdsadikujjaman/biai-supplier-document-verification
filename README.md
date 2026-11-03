# Supplier Document Verification System
### Bangladesh Institute of Artificial Intelligence (BIAI) • AI Engineer Recruitment Assessment (Round 2)
**Client Context:** Fictional Organization *Aamar Garments Ltd*  
**Author:** AI Engineer Candidate  

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-V2.10%2B-green.svg)](https://docs.pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-red.svg)](https://streamlit.io/)
[![Tests Passing](https://img.shields.io/badge/Tests-91%20Passed-brightgreen.svg)](https://pytest.org/)
[![Accuracy](https://img.shields.io/badge/Benchmark%20Accuracy-100%25-success.svg)](docs/evaluation.md)
[![Safety Invariant](https://img.shields.io/badge/False%20Approvals-0%20(Zero%20Tolerance)-critical.svg)](docs/evaluation.md)

---

## 1. Project Overview & Problem Statement

In large-scale industrial manufacturing and apparel production (such as *Aamar Garments Ltd*), procurement departments handle dozens of supplier quotation documents daily. Manual verification against Purchase Requests (PRs) and internal compliance policies is error-prone, labor-intensive, and susceptible to financial leakage (e.g., hidden price escalations, omitted late penalties, bundled VAT, and calculation errors).

This project implements an **enterprise-grade, deterministic AI Supplier Document Verification System** that evaluates supplier quotation PDFs against benchmark purchase requests (`purchase-request.csv`) and corporate governance policies (`company-rules.md`).

The system produces one of three unambiguous decisions for every supplier quotation pack:
- 🟢 **`APPROVE`**: The quotation cleanly satisfies all PR criteria, complies with every business rule, and has 100% verified arithmetic.
- 🔴 **`REJECT`**: The quotation violates at least one confirmed mandatory policy threshold (e.g. price ceiling, advance payment cap, missing penalty clause, missing TIN/BIN, or delivery timeline).
- 🟡 **`NEEDS HUMAN REVIEW`**: The document contains ambiguous terms, marginal variances, unreadable sections, mathematical discrepancies, or requires discretionary review.

---

## 2. Core Architectural Principles

1. **Fixed Sequential Pipeline (Non-Autonomous):**  
   Strictly avoids unconstrained autonomous agents. Execution follows an immutable, verifiable 7-stage sequential pipeline.
2. **Deterministic Business Validation:**  
   LLMs are restricted to text parsing and perceptual extraction. All arithmetic recalculations, tolerance checks, and compliance decisions execute strictly in deterministic Python code.
3. **Evidence Grounding & Zero Hallucination:**  
   Every extracted data point is wrapped in a generic `FieldProvenance[T]` Pydantic model containing the verbatim document quotation, 1-indexed page number, and evidence verification status.
4. **Safety Precedence Synthesis:**  
   - Confirmed rejection rules take absolute precedence ($\rightarrow$ `REJECT`).
   - Discretionary variances, ambiguities, or math errors route to human review ($\rightarrow$ `NEEDS HUMAN REVIEW`).
   - A confirmed rejection is never masked or softened by an unrelated uncertainty.

---

## 3. Sequential Workflow Architecture

```mermaid
flowchart TD
    subgraph S1["Stage 1: Document Ingestion"]
        PDF["Supplier Quotation PDF"] --> SHA["SHA-256 Provenance Hashing"]
        SHA --> Ingest["PyMuPDF / pypdf Text Parser"]
        Ingest --> IngestDoc["IngestedDocument Container"]
    end

    subgraph S2["Stage 2: Structured Extraction & Normalization"]
        IngestDoc --> Extractor["ExtractionEngine\n(Deterministic Regex / Hybrid LLM)"]
        Extractor --> Norm["CanonicalNormalizer\n(Decimal, Days, Percentages)"]
        Norm --> Provenance["FieldProvenance Verification\n(Verbatim Text & Page Checks)"]
        Provenance --> Quotation["ExtractedQuotation Schema"]
    end

    subgraph S3["Stage 3: Arithmetic Consistency Audit"]
        Quotation --> LineMath["Line Amounts (Qty × Price)"]
        LineMath --> SubtotalMath["Subtotal Sum Reconciliation"]
        SubtotalMath --> VATMath["15% Statutory VAT Recalculation"]
        VATMath --> TotalMath["Grand Total Consistency (Decimal)"]
        TotalMath --> MathAudit["ArithmeticAuditResult"]
    end

    subgraph S4["Stage 4: Purchase Request Benchmark Alignment"]
        Quotation & PR["purchase-request.csv\n(PR-2026-114)"] --> Comparator["PurchaseRequestComparator"]
        Comparator --> QtyTol["Quantity Variance (±5% Tolerance)"]
        Comparator --> PriceCeil["Price Ceiling (+3% Max Limit)"]
        Comparator --> ItemMatch["Item Code & Unit Compatibility"]
        QtyTol & PriceCeil & ItemMatch --> PRReport["PRComparisonReport"]
    end

    subgraph S5["Stage 5: Business Rule Evaluation"]
        Quotation & MathAudit & PRReport --> RulesEngine["CompanyRuleEngine\n(company-rules.md)"]
        RulesEngine --> RejectRules["Reject Rules (1-5)"]
        RulesEngine --> ReviewRules["Human Review Rules (1-7)"]
        RulesEngine --> Integrity["Matching Integrity Audit"]
    end

    subgraph S6["Stage 6: Precedence Decision Synthesis"]
        RejectRules & ReviewRules & Integrity --> Precedence["Decision Precedence Engine"]
        Precedence --> C1{"Confirmed\nRejection?"}
        C1 -- Yes --> REJECT["REJECT 🔴"]
        C1 -- No --> C2{"Review Rule,\nUncertainty,\nor Math Error?"}
        C2 -- Yes --> REVIEW["NEEDS HUMAN REVIEW 🟡"]
        C2 -- No --> APPROVE["APPROVE 🟢"]
    end

    subgraph S7["Stage 7: Presentation & Reporting"]
        REJECT & REVIEW & APPROVE --> WebUI["Streamlit Interactive UI (app.py)"]
        REJECT & REVIEW & APPROVE --> Reports["Reports: Markdown, JSON, CSV"]
    end
```

---

## 4. Benchmark Performance & Evaluation

The system was evaluated against all 10 sample supplier packs in `sample_data/`:

| Pack File | Supplier Name | Quoted Item | Expected Decision | Actual Decision | Status | Latency | Primary Reason / Finding |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `supplier-pack-01.pdf` | Padma Textile Mills Ltd | `A` | **`APPROVE`** | **`APPROVE`** | ✅ PASS | 12.0 ms | Fully compliant: Item A @ 472.00 BDT (PR max 480.00 BDT), 10% adv, 24d delivery, 1%/wk penalty, 15% VAT separated |
| `supplier-pack-02.pdf` | Jamuna Trims and Accessories | `B` | **`APPROVE`** | **`APPROVE`** | ✅ PASS | 5.6 ms | Fully compliant: Item B @ 36.00 BDT (PR max 38.00 BDT), 0% adv, 21d delivery, 0.75%/wk penalty, 15% VAT separated |
| `supplier-pack-03.pdf` | Karnaphuli Yarn Traders | `C` | **`REJECT`** | **`REJECT`** | ✅ PASS | 8.6 ms | `REJECT_RULE_1`: Quoted unit price (229.00 BDT) exceeds PR max (210.00 BDT) by $+9.05\% > +3\%$ ceiling |
| `supplier-pack-04.pdf` | Surma Packaging Industries | `D` | **`NEEDS HUMAN REVIEW`** | **`NEEDS HUMAN REVIEW`** | ✅ PASS | 5.8 ms | `REVIEW_RULE_1`: Quoted unit price (6.65 BDT) is $+2.31\%$ above PR max (6.50 BDT), falling into $\le +3\%$ review bracket |
| `supplier-pack-05.pdf` | Meghna Carton Works | `E` | **`REJECT`** | **`REJECT`** | ✅ PASS | 7.3 ms | `REJECT_RULE_2`: Advance payment of $40.0\%$ exceeds the $20.0\%$ policy limit |
| `supplier-pack-06.pdf` | Teesta Fabrics Ltd | `A` | **`REJECT`** | **`REJECT`** | ✅ PASS | 7.5 ms | `REJECT_RULE_3`: Late-delivery penalty clause is completely omitted from Terms & Conditions |
| `supplier-pack-07.pdf` | Rupsha Zipper Factory | `B` | **`NEEDS HUMAN REVIEW`** | **`NEEDS HUMAN REVIEW`** | ✅ PASS | 6.0 ms | `REVIEW_RULE_2`: Quoted quantity (16,500 pcs) is $-17.50\%$ below requested (20,000 pcs), exceeding $\pm 5\%$ tolerance |
| `supplier-pack-08.pdf` | Bhairab Thread and Co | `C` | **`REJECT`** | **`REJECT`** | ✅ PASS | 7.8 ms | `REJECT_RULE_4`: Supplier TIN and BIN missing (replaced with evasive 'available upon award' text) |
| `supplier-pack-09.pdf` | Dhaleshwari Poly Pack | `D` | **`NEEDS HUMAN REVIEW`** | **`NEEDS HUMAN REVIEW`** | ✅ PASS | 5.9 ms | `REVIEW_RULE_3` & `REVIEW_RULE_6`: Ambiguous terms ('30 to 90 days') + 2,000 BDT arithmetic subtotal error |
| `supplier-pack-10.pdf` | Kushiyara Box Industries | `E` | **`REJECT`** | **`REJECT`** | ✅ PASS | 6.2 ms | `REJECT_RULE_5`: Delivery timeline (60 days) $> 45$ days (rejection confirmed over bundled VAT) |

### Key Benchmark Metrics
- **Decision Accuracy:** `100.0%` (10/10 correct)
- **False Approvals (Safety Critical):** `0` (Zero Tolerance Met)
- **False Rejections:** `0`
- **Mean Backend Pipeline Latency:** `5.86 ms` per document (isolated pipeline execution; excludes browser network & UI DOM rendering)
- **Reports:** [`reports/evaluation_summary.json`](reports/evaluation_summary.json) and [`reports/audit_summary.md`](reports/audit_summary.md)

---

## 5. Technology Stack

- **Runtime:** Python 3.11+ (Tested on Python 3.13)
- **Web Interface:** Streamlit 1.40+
- **Schema Validation & Typing:** Pydantic V2 (`BaseModel`, `FieldProvenance[T]`, `extra="forbid"`)
- **PDF Ingestion:** PyMuPDF (`fitz`) with fallback to `pypdf`
- **Data Manipulation:** Pandas
- **Financial Arithmetic:** Python Standard Library `decimal.Decimal` (`ROUND_HALF_UP`)
- **Testing:** Pytest (91 unit and integration tests)
- **Configuration:** `pydantic-settings` & `python-dotenv`

---

## 6. Installation & Setup Instructions

### A. Prerequisites
- Windows 10/11 (or Linux / macOS)
- Python 3.11 or higher installed and added to `PATH`
- Git installed (optional)

### B. Setup Virtual Environment (Windows PowerShell)

```powershell
# 1. Navigate to the project root directory
cd E:\Work\BIAI-AI-Engineer-Task

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 4. Upgrade pip and install all required dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

*(Note for Linux / macOS: Use `source venv/bin/activate` to activate).*

---

## 7. Running the Application

Launch the Streamlit interactive UI:

```powershell
streamlit run app.py
```

The application will launch in your default web browser at `http://localhost:8501`.

### Application Features:
1. **Executive Dashboard:** Real-time metrics, decision distributions, and session tracking.
2. **Document Verification:** Upload custom PDF quotations or click **"⚡ One-Click 10-Pack Benchmark Demo"** to evaluate the 10 provided sample packs instantly.
3. **Decision Ledger:** Color-coded cards displaying decisions, primary findings, and violation counts.
4. **Deep Audit Inspector:** Line-by-line financial audit, PR comparison tables, full company rules matrix, and exact PDF evidence quotes.
5. **Benchmark & Evaluation:** Dynamically inspects the official 10-document evaluation benchmark with re-run capabilities.
6. **Multi-Format Export:** Download audit reports in **CSV**, **Markdown**, or **JSON**.

---

## 8. Optional LLM Configuration

The system is designed to operate **100% deterministically and offline without requiring an API key**.

If you wish to test hybrid LLM extraction using Google Gemini or OpenAI:
1. Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` and set your API key:
   ```ini
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   LLM_MODEL=gemini-1.5-flash
   ```
3. If no key is set or the network is unavailable, the system automatically runs in deterministic layout-grounded mode.

---

## 9. Running Tests

Run the full automated test suite (91 unit and integration tests):

```powershell
pytest tests/ -v
```

To run individual test modules:
```powershell
# Run benchmark integration test across all 10 packs
pytest tests/integration/test_all_sample_packs.py -v

# Run business rules unit tests
pytest tests/unit/test_rules.py -v

# Run arithmetic financial tests
pytest tests/unit/test_arithmetic.py -v
```

---

## 10. Reproducing the Benchmark

To independently execute the benchmark evaluation and refresh the report files:

```powershell
python -m src.evaluation
```

This updates:
- `reports/evaluation_summary.json`
- `reports/audit_summary.md`

---

## 11. Project Directory Structure

```
BIAI-AI-Engineer-Task/
├── app.py                          # Streamlit Enterprise UI application
├── requirements.txt                # Python package dependencies
├── .env.example                    # Environment configuration template
├── .gitignore                      # Git exclusion rules
├── README.md                       # Main project documentation
├── docs/                           # Technical documentation
│   ├── architecture.md             # Detailed architecture specification & Mermaid diagrams
│   ├── evaluation.md               # Benchmark evaluation report & confusion matrix
│   ├── limitations.md              # System boundaries, assumptions & future roadmap
│   ├── proposed_architecture.md    # Initial phase architectural specification
│   └── sample_analysis.md          # Preliminary sample analysis & discrepancy matrix
├── reports/                        # Evaluation and audit reports
│   ├── audit_summary.md            # Human-readable markdown audit summary
│   └── evaluation_summary.json     # Machine-readable benchmark JSON metrics
├── sample_data/                    # Official recruitment assessment sample dataset
│   ├── company-rules.md            # Deterministic company policies & rules
│   ├── purchase-request.csv        # Benchmark purchase request PR-2026-114
│   ├── supplier-pack-01.pdf        # Fully compliant quotation (APPROVE)
│   ├── supplier-pack-02.pdf        # Fully compliant quotation (APPROVE)
│   ├── supplier-pack-03.pdf        # +9.05% price escalation (REJECT)
│   ├── supplier-pack-04.pdf        # +2.31% marginal price (NEEDS HUMAN REVIEW)
│   ├── supplier-pack-05.pdf        # 40% advance payment (REJECT)
│   ├── supplier-pack-06.pdf        # Omitted late penalty clause (REJECT)
│   ├── supplier-pack-07.pdf        # -17.5% quantity shortfall (NEEDS HUMAN REVIEW)
│   ├── supplier-pack-08.pdf        # Missing TIN/BIN registration (REJECT)
│   ├── supplier-pack-09.pdf        # Ambiguous payment + math error (NEEDS HUMAN REVIEW)
│   └── supplier-pack-10.pdf        # 60d delivery + bundled VAT (REJECT)
├── src/                            # Production source code
│   ├── __init__.py
│   ├── app_helpers.py              # UI helpers, file validation, temporary file cleanup
│   ├── arithmetic.py               # Python Decimal financial recalculation engine
│   ├── comparator.py               # Purchase Request alignment & variance engine
│   ├── config.py                   # Pydantic Settings configuration & thresholds
│   ├── decision_engine.py          # Sequential pipeline coordinator & precedence engine
│   ├── evaluation.py               # Benchmark runner & metrics calculator
│   ├── extractor.py                # Grounded extraction engine with text verification
│   ├── ingestion.py                # Dual-engine PDF reader & SHA-256 calculator
│   ├── normalizer.py               # Canonical type & unit normalizer
│   ├── pr_loader.py                # Purchase Request CSV loader
│   ├── report_generator.py         # Multi-format report export (Markdown, JSON, CSV)
│   ├── rules.py                    # Deterministic company rule implementations (Rules 1-12)
│   ├── interfaces/                 # Abstract base interfaces
│   │   ├── __init__.py
│   │   └── base.py
│   └── models/                     # Strict Pydantic V2 domain models
│       ├── __init__.py
│       └── schemas.py              # FieldProvenance, Quotation, Rules & Report models
└── tests/                          # Automated Pytest suite (91 tests)
    ├── __init__.py
    ├── integration/
    │   ├── __init__.py
    │   └── test_all_sample_packs.py # Full end-to-end evaluation of all 10 packs
    └── unit/
        ├── __init__.py
        ├── test_app_helpers.py     # Upload & report loading tests
        ├── test_app_integration.py # Streamlit integration & corrupted PDF handling
        ├── test_arithmetic.py      # Line math, subtotal, VAT, total recalculation
        ├── test_comparator.py      # PR matching, tolerance, ceiling tests
        ├── test_decision_engine.py # Precedence synthesis & essential info checks
        ├── test_extractor.py       # Regex & grounding extraction tests
        ├── test_ingestion.py       # PDF reader & hashing tests
        ├── test_normalizer.py      # Currency, quantity, temporal normalizers
        ├── test_report_generator.py # Markdown, JSON, CSV export tests
        ├── test_rules.py           # Boundary & threshold tests for Rules 1-12
        ├── test_schemas.py         # Pydantic schema validation tests
        └── test_stage2_review.py   # Regression & hardening tests
```

