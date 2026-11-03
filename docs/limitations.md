# System Boundaries, Known Limitations & Roadmap
## Supplier Document Verification System • Aamar Garments Ltd

This document outlines the current boundaries, technical assumptions, and future roadmap for the **Supplier Document Verification System**.

---

## 1. Current Boundaries & Assumptions

### A. Digital PDF Text Layer Prerequisite
- **Current Capability:** The system utilizes native digital PDF text extractors (`PyMuPDF` with `pypdf` fallback) to extract high-fidelity characters, layouts, and fonts directly from the document's PDF text streams.
- **Limitation:** If a supplier submits a physical document that was scanned or photographed as a pure bitmap image without an embedded OCR text layer, the system flags the document as `UNREADABLE` and routes it to `NEEDS HUMAN REVIEW`.
- **Roadmap Mitigation:** Integrate an open-source OCR engine (such as Tesseract or PaddleOCR) or a vision-multimodal LLM to transcribe scanned pages before ingestion.

### B. Single Quoted Item per Document Benchmark
- **Current Capability:** The 10 assessment sample packs each quote a single primary product from the purchase request (`ITEM-A` through `ITEM-E`). The system compares, audits, and validates single-item quotations with 100% precision.
- **Future Enhancement:** Extend line-matching logic to support multi-item bundle quotations with partial fulfillments across 20+ line items in a single quotation pack.

### C. Domestic Currency & Uniform VAT Rate
- **Current Capability:** The system assumes transactions are denominated in Bangladeshi Taka (`BDT`) and evaluates the standard statutory VAT rate of $15.0\%$ per National Board of Revenue (NBR) rules.
- **Limitation:** International supplier packs denominated in foreign currencies (USD, EUR, CNY) or goods qualifying for VAT exemptions / zero-rated export incentives are not automatically converted.
- **Roadmap Mitigation:** Incorporate live FX rate tables and NBR VAT exemption certificate validation.

---

## 2. Security & Operational Assumptions

1. **Document Immutability:** The system assumes submitted quotation packs represent final, signed quotations. Incremental redlines or handwritten pen annotations are not analyzed.
2. **Local Sandboxing:** File uploads are processed in temporary directories and purged immediately. In production enterprise deployments, persistent cloud object storage (e.g., AWS S3 or GCP Cloud Storage) with customer-managed encryption keys (CMEK) should be introduced for archival retention.
3. **Throughput Scaling:** The current synchronous pipeline processes ~170 documents per second (average latency < 6 ms). For high-throughput enterprise pipelines processing 10,000+ documents daily, a background Celery/Redis queue with webhook callbacks should be implemented.

---

## 3. Human-in-the-Loop (HITL) Workflow Integration

For documents flagged with `NEEDS HUMAN REVIEW`:
- The system currently provides the audit ledger, arithmetic findings, and exact PDF page citations to human procurement officers.
- **Future Enhancement:** Build an interactive feedback and sign-off portal in Streamlit where authorized procurement managers can review the exact evidence quote, input override justifications, and formally approve discretionary exceptions (such as the $+2.31\%$ price variance in Pack 04).

