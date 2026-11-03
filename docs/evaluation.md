# Benchmark Evaluation & Audit Report
## Supplier Document Verification System • Aamar Garments Ltd

This document details the evaluation methodology, benchmark results, and verification ledger for the 10 reference supplier packs supplied in `sample_data/`.

---

## 1. Executive Summary & Benchmark Metrics

The system was evaluated against the official benchmark ground truth using the automated evaluation module ([`src/evaluation.py`](file:///e:/Work/BIAI-AI-Engineer-Task/src/evaluation.py)):

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :---: |
| **Overall Decision Accuracy** | **100.0%** | 100.0% | ✅ PASS (10/10) |
| **False Approvals (Safety Critical)** | **0** | 0 (Zero Tolerance) | ✅ ZERO FA |
| **False Rejections** | **0** | 0 | ✅ ZERO FR |
| **Extraction Failure Rate (EFR)** | **0.0%** | 0.0% | ✅ PASS |
| **Mean Processing Latency** | **5.89 ms** | < 2,000 ms | ✅ PASS |
| **P95 Processing Latency** | **12.04 ms** | < 3,000 ms | ✅ PASS |

---

## 2. Decision Confusion Matrix

```
                      System Output Decision
                   APPROVE   REJECT   NEEDS REVIEW   Total
Ground   APPROVE      2        0           0           2
Truth    REJECT       0        5           0           5
Decision REVIEW       0        0           3           3
         Total        2        5           3          10
```

- **Accuracy:** $10/10 = 100.0\%$
- **Precision (Approve):** $2/2 = 100.0\%$
- **Recall (Approve):** $2/2 = 100.0\%$
- **False Positive Rate (False Approvals):** $0.0\%$

---

## 3. Comprehensive Document Verification Ledger

### Pack 01: `supplier-pack-01.pdf`
- **Supplier:** Padma Textile Mills Ltd
- **Quoted Item:** Item `A` (12,000 metre @ 472.00 BDT)
- **PR Benchmark:** Item `A` requested 12,000 metre, Max Price 480.00 BDT
- **Variance Analysis:** Quantity variance $0.0\%$, Price variance $-1.67\%$ (below max price)
- **Contractual Terms:** 10% advance ($\le 20\%$), 24 days delivery ($\le 30$ days), 1.0%/week late penalty ($\ge 0.5\%$), 45 days validity, 45 days payment credit. TIN & BIN verified.
- **Arithmetic Audit:** $12,000 \times 472.00 = 5,664,000.00\text{ BDT}$. VAT $15\% = 849,600.00\text{ BDT}$. Total $= 6,513,600.00\text{ BDT}$ (Exact match).
- **Decision:** **`APPROVE`** ✅

### Pack 02: `supplier-pack-02.pdf`
- **Supplier:** Jamuna Trims and Accessories
- **Quoted Item:** Item `B` (20,000 piece @ 36.00 BDT)
- **PR Benchmark:** Item `B` requested 20,000 piece, Max Price 38.00 BDT
- **Variance Analysis:** Quantity variance $0.0\%$, Price variance $-5.26\%$ (below max price)
- **Contractual Terms:** 0% advance, 21 days delivery ($\le 30$ days), 0.75%/week late penalty ($\ge 0.5\%$), 30 days validity, 30 days payment credit. TIN & BIN verified.
- **Arithmetic Audit:** $20,000 \times 36.00 = 720,000.00\text{ BDT}$. VAT $15\% = 108,000.00\text{ BDT}$. Total $= 828,000.00\text{ BDT}$ (Exact match).
- **Decision:** **`APPROVE`** ✅

### Pack 03: `supplier-pack-03.pdf`
- **Supplier:** Karnaphuli Yarn Traders
- **Quoted Item:** Item `C` (800 cone @ 229.00 BDT)
- **PR Benchmark:** Item `C` requested 800 cone, Max Price 210.00 BDT
- **Violation:** `REJECT_RULE_1` triggered. The allowable $+3\%$ price ceiling is $210.00 \times 1.03 = 216.30\text{ BDT}$. The quoted price of 229.00 BDT represents a $+9.05\%$ variance over max price, exceeding the $+3\%$ rejection ceiling.
- **Decision:** **`REJECT`** 🔴 (Confirmed violation)

### Pack 04: `supplier-pack-04.pdf`
- **Supplier:** Surma Packaging Industries
- **Quoted Item:** Item `D` (50,000 piece @ 6.65 BDT)
- **PR Benchmark:** Item `D` requested 50,000 piece, Max Price 6.50 BDT
- **Trigger:** `REVIEW_RULE_1` triggered. Quoted price is $6.65\text{ BDT}$ ($+2.31\%$ above max price). Because this is $\le +3.00\%$ ($6.695\text{ BDT}$ ceiling), it falls into the discretionary human-review bracket.
- **Decision:** **`NEEDS HUMAN REVIEW`** 🟡

### Pack 05: `supplier-pack-05.pdf`
- **Supplier:** Meghna Carton Works
- **Quoted Item:** Item `E` (3,000 piece @ 92.00 BDT)
- **PR Benchmark:** Item `E` requested 3,000 piece, Max Price 95.00 BDT
- **Violation:** `REJECT_RULE_2` triggered. Quoted advance payment is $40.0\%$, exceeding the company maximum of $20.0\%$.
- **Decision:** **`REJECT`** 🔴 (Confirmed violation)

### Pack 06: `supplier-pack-06.pdf`
- **Supplier:** Teesta Fabrics Ltd
- **Quoted Item:** Item `A` (12,000 metre @ 465.00 BDT)
- **PR Benchmark:** Item `A` requested 12,000 metre, Max Price 480.00 BDT
- **Violation:** `REJECT_RULE_3` triggered. The contract terms omit any late-delivery penalty clause entirely.
- **Decision:** **`REJECT`** 🔴 (Confirmed violation)

### Pack 07: `supplier-pack-07.pdf`
- **Supplier:** Rupsha Zipper Factory
- **Quoted Item:** Item `B` (16,500 piece @ 35.00 BDT)
- **PR Benchmark:** Item `B` requested 20,000 piece, Max Price 38.00 BDT
- **Trigger:** `REVIEW_RULE_2` triggered. Quoted quantity of 16,500 differs from requested 20,000 by $-17.50\%$, far exceeding the allowable $\pm 5.00\%$ tolerance.
- **Decision:** **`NEEDS HUMAN REVIEW`** 🟡

### Pack 08: `supplier-pack-08.pdf`
- **Supplier:** Bhairab Thread and Co
- **Quoted Item:** Item `C` (800 cone @ 205.00 BDT)
- **PR Benchmark:** Item `C` requested 800 cone, Max Price 210.00 BDT
- **Violation:** `REJECT_RULE_4` triggered. Both TIN and BIN are missing, replaced with evasive text ("Available upon contract award").
- **Decision:** **`REJECT`** 🔴 (Confirmed violation)

### Pack 09: `supplier-pack-09.pdf`
- **Supplier:** Dhaleshwari Poly Pack
- **Quoted Item:** Item `D` (50,000 piece @ 6.40 BDT)
- **PR Benchmark:** Item `D` requested 50,000 piece, Max Price 6.50 BDT
- **Triggers:**
  1. `REVIEW_RULE_3`: Payment credit terms stated as "30 to 90 days as agreed" (indefinite/ambiguous range outside standard 30–60 days).
  2. `REVIEW_RULE_6`: Mathematical discrepancy. Recalculated subtotal is $50,000 \times 6.40 = 320,000.00\text{ BDT}$, but quotation quotes $322,000.00\text{ BDT}$ ($2,000\text{ BDT}$ discrepancy).
- **Decision:** **`NEEDS HUMAN REVIEW`** 🟡

### Pack 10: `supplier-pack-10.pdf`
- **Supplier:** Kushiyara Box Industries
- **Quoted Item:** Item `E` (3,000 piece @ 94.00 BDT, VAT included)
- **PR Benchmark:** Item `E` requested 3,000 piece, Max Price 95.00 BDT
- **Findings:**
  - Promised delivery duration is $60\text{ days}$ ($> 45\text{ days}$).
  - VAT is bundled rather than shown separately at 15%.
- **Precedence Resolution:** `REJECT_RULE_5` is a confirmed rejection violation. Under the precedence rule, confirmed rejections take absolute precedence over review conditions.
- **Decision:** **`REJECT`** 🔴 (Confirmed violation)

---

## 4. Reproducing the Benchmark

To execute the benchmark suite and reproduce all metrics:

```powershell
python -m src.evaluation
```

Artifacts generated:
- Machine-Readable JSON: `reports/evaluation_summary.json`
- Markdown Audit Summary: `reports/audit_summary.md`

