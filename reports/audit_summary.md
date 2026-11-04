# Supplier Document Verification System – Evaluation & Benchmark Report

**Evaluation Date:** 2026-11-04 11:28:02 UTC  
**Overall Accuracy:** `100.0%` (10/10 correct)  
**False Approvals (Safety Critical):** `0`  
**False Rejections:** `0`  
**Average Backend Pipeline Latency:** `12.0 ms` per pack (disk read, extraction, arithmetic & rules evaluation; excludes network/UI DOM rendering)  

## 1. Executive Performance Summary

| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Decision Accuracy** | **100.0%** | 100.0% | ✅ PASS |
| **False Approvals (FA)** | **0** | 0 (Zero Tolerance) | ✅ ZERO FA |
| **False Rejections (FR)** | **0** | 0 | ✅ ZERO FR |
| **Extraction Failure Rate (EFR)** | **0.0%** | 0.0% | ✅ PASS |
| **Mean Backend Latency** | **12.0 ms** | < 2,000 ms | ✅ PASS |
| **P95 Backend Latency** | **31.9 ms** | < 3,000 ms | ✅ PASS |

## 2. Decision Distribution Matrix

| Decision Category | Expected Ground Truth | Actual System Output | Conformity |
| :--- | :---: | :---: | :---: |
| **APPROVE** | 2 | 2 | MATCH |
| **REJECT** | 5 | 5 | MATCH |
| **NEEDS HUMAN REVIEW** | 3 | 3 | MATCH |
| **Total Documents** | **10** | **10** | **100% AUDITED** |

## 3. Detailed Document Verification Ledger

| Pack File | Supplier Name | Quoted Item | Expected | Actual | Status | Latency | Primary Reason / Finding |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `supplier-pack-01.pdf` | Padma Textile Mills Ltd | `A` | **APPROVE** | **APPROVE** | ✅ PASS | 31.9 ms | All company rules passed, PR specifications met within tolerance, and all financial calculations verified without discrepancies. |
| `supplier-pack-02.pdf` | Jamuna Trims and Accessories | `B` | **APPROVE** | **APPROVE** | ✅ PASS | 9.6 ms | All company rules passed, PR specifications met within tolerance, and all financial calculations verified without discrepancies. |
| `supplier-pack-03.pdf` | Karnaphuli Yarn Traders | `C` | **REJECT** | **REJECT** | ✅ PASS | 10.2 ms | Confirmed violation of Unit price exceeds PR maximum by > 3%: Quoted unit price (229.00 BDT) for item C is +9.05% above maximum price (210.00 BDT), exceeding the +3% ceiling (216.30 BDT). |
| `supplier-pack-04.pdf` | Surma Packaging Industries | `D` | **NEEDS HUMAN REVIEW** | **NEEDS HUMAN REVIEW** | ✅ PASS | 10.0 ms | Review required under Unit price above maximum by <= 3%: Quoted unit price (6.65 BDT) for item D is +2.31% above PR maximum (6.50 BDT), which falls into the <= 3% discretionary review bracket. |
| `supplier-pack-05.pdf` | Meghna Carton Works | `E` | **REJECT** | **REJECT** | ✅ PASS | 10.6 ms | Confirmed violation of Advance payment exceeds 20%: Quoted advance payment is 40%, exceeding the maximum permitted 20%. |
| `supplier-pack-06.pdf` | Teesta Fabrics Ltd | `A` | **REJECT** | **REJECT** | ✅ PASS | 9.3 ms | Confirmed violation of Late-delivery penalty clause missing or insufficient: The contract omits any late-delivery penalty clause entirely. |
| `supplier-pack-07.pdf` | Rupsha Zipper Factory | `B` | **NEEDS HUMAN REVIEW** | **NEEDS HUMAN REVIEW** | ✅ PASS | 8.9 ms | Review required under Quantity differs from requested by > 5%: Quoted quantity (16,500 piece) differs by -17.50% from requested (20,000 piece), exceeding the allowable 5% tolerance band. |
| `supplier-pack-08.pdf` | Bhairab Thread and Co | `C` | **REJECT** | **REJECT** | ✅ PASS | 9.3 ms | Confirmed violation of Supplier TIN or BIN missing: Supplier tax registration is missing required identifier(s): TIN, BIN. |
| `supplier-pack-09.pdf` | Dhaleshwari Poly Pack | `D` | **NEEDS HUMAN REVIEW** | **NEEDS HUMAN REVIEW** | ✅ PASS | 9.8 ms | Review required under Payment terms unclear or outside 30 to 60 days: Payment credit terms are ambiguous, conditional, or subject to later agreement. |
| `supplier-pack-10.pdf` | Kushiyara Box Industries | `E` | **REJECT** | **REJECT** | ✅ PASS | 10.3 ms | Confirmed violation of Delivery promised later than 45 days: Promised delivery timeline of 60 days exceeds the 45-day limit. |

## 4. Architectural Observations & Safety Compliance

- **Deterministic Business Validation:** Every threshold, percentage variance, arithmetic recalculation, and company rule runs strictly in Python with `Decimal` precision.
- **Zero Hallucination / Grounded Evidence:** All decisions are backed by verbatim quotations and page numbers from the PDF packs.
- **Precedence Integrity:** Confirmed rejection rules strictly take precedence over discretionary review triggers (as demonstrated by Pack 10, where the confirmed 60-day delivery violation takes absolute precedence over bundled VAT).
- **Human-in-the-Loop Safeguards:** Non-standard terms (such as Pack 09's '30 to 90 days as agreed') and pricing within the 3% marginal bracket (Pack 04) are cleanly routed to `NEEDS HUMAN REVIEW`.