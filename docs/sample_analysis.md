# Sample Data Analysis & Document Verification Breakdown

**Project:** BIAI AI Engineer Recruitment Assessment (Round 2)  
**System:** Supplier Document Verification System  
**Organization:** Aamar Garments Ltd (Fictional)  
**Author:** Senior AI Engineer & Software Architect  
**Status:** Completed Analysis (Phase 1)

---

## 1. Executive Summary

This document provides a comprehensive inspection, extraction analysis, and rule evaluation of all sample artifacts provided for the Supplier Document Verification System. The dataset consists of:
1. `company-rules.md`: The deterministic business policy document establishing rejection criteria, human review triggers, and approval conditions.
2. `purchase-request.csv`: Purchase Request `PR-2026-114` specifying 5 required procurement items, quantities, and ceiling unit prices.
3. 10 Supplier Quotation PDF documents (`supplier-pack-01.pdf` through `supplier-pack-10.pdf`): Digital quotation packs submitted by 10 distinct vendors.

### Verification Outcome Summary

Every supplier pack has been verified against the purchase request and company rules with exact supporting text citations and zero guesswork:

| Pack ID | Supplier Name | Item | Quoted Price | Quoted Qty | Final Decision | Primary Trigger / Justification |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Pack 01** | Padma Textile Mills Ltd | A | 472.00 BDT | 12,000 metre | **APPROVE** | Complies with all PR terms and company rules. Late penalty 1%/wk, 10% advance, 24d delivery, 15% VAT separated. |
| **Pack 02** | Jamuna Trims and Accessories | B | 36.00 BDT | 20,000 piece | **APPROVE** | Fully compliant. Price below max, 0% advance, 21d delivery, penalty 0.75%/wk, 15% VAT separated. |
| **Pack 03** | Karnaphuli Yarn Traders | C | 229.00 BDT | 800 cone | **REJECT** | **Reject Rule 1**: Unit price (229.00 BDT) is +9.05% above PR maximum (210.00 BDT), exceeding the 3% ceiling (+3% is 216.30 BDT). |
| **Pack 04** | Surma Packaging Industries | D | 6.65 BDT | 50,000 piece | **NEEDS HUMAN REVIEW** | **Human Review Rule 1**: Unit price (6.65 BDT) is +2.31% above PR maximum (6.50 BDT), which falls within the ≤ 3% review bracket (max +3% is 6.695 BDT). |
| **Pack 05** | Meghna Carton Works | E | 92.00 BDT | 3,000 piece | **REJECT** | **Reject Rule 2**: Advance payment requested is 40%, exceeding the 20% policy limit. |
| **Pack 06** | Teesta Fabrics Ltd | A | 465.00 BDT | 12,000 metre | **REJECT** | **Reject Rule 3**: The contract omits a late-delivery penalty clause entirely (clauses 1 to 5 skip penalty). |
| **Pack 07** | Rupsha Zipper Factory | B | 35.00 BDT | 16,500 piece | **NEEDS HUMAN REVIEW** | **Human Review Rule 2**: Quoted quantity (16,500) differs by -17.5% from PR request (20,000), exceeding the 5% tolerance threshold. |
| **Pack 08** | Bhairab Thread and Co | C | 205.00 BDT | 800 cone | **REJECT** | **Reject Rule 4**: Supplier TIN and BIN are completely missing ("Supplier registration details available on request"). |
| **Pack 09** | Dhaleshwari Poly Pack | D | 6.40 BDT | 50,000 piece | **NEEDS HUMAN REVIEW** | **Human Review Rule 6 & 3**: Arithmetic mismatch (50,000 × 6.40 = 320,000 BDT, but document displays 322,000 BDT subtotal) & payment terms allow up to 90 days. |
| **Pack 10** | Kushiyara Box Industries | E | 94.00 BDT | 3,000 piece | **REJECT** | **Reject Rule 5**: Delivery timeline promised is 60 days of PO (> 45 days limit). *Also violates VAT separation rule (Rule 5)*. |

---

## 2. Sample File Inventory

| File Name | File Size | Document Type | Page Count | Integrity / Text Extractability | Primary Scope |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `company-rules.md` | 1,235 bytes | Markdown | N/A | Valid UTF-8 text | Business logic rules & thresholds |
| `purchase-request.csv` | 370 bytes | CSV | N/A | Valid UTF-8 CSV | Benchmark PR reference PR-2026-114 |
| `supplier-pack-01.pdf` | 3,138 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-901 (Item A) |
| `supplier-pack-02.pdf` | 3,102 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-902 (Item B) |
| `supplier-pack-03.pdf` | 3,102 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-903 (Item C) |
| `supplier-pack-04.pdf` | 3,098 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-904 (Item D) |
| `supplier-pack-05.pdf` | 3,089 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-905 (Item E) |
| `supplier-pack-06.pdf` | 3,030 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-906 (Item A) |
| `supplier-pack-07.pdf` | 3,075 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-907 (Item B) |
| `supplier-pack-08.pdf` | 3,070 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-908 (Item C) |
| `supplier-pack-09.pdf` | 3,113 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-909 (Item D) |
| `supplier-pack-10.pdf` | 3,022 bytes | PDF 1.4 | 1 | Digital PDF (clean text layer) | Quotation QT-2026-910 (Item E) |

*Note: All 10 PDF documents are digital vector PDFs with single-page layout, structured tables, and readable standard fonts.*

---

## 3. Purchase Request Summary (`purchase-request.csv`)

- **Purchase Request Number:** `PR-2026-114`
- **Target Organization:** Aamar Garments Ltd (fictional)
- **Line Items Specification:**

| Item Code | Item Description | Unit | Quantity Requested | Maximum Unit Price (BDT) | Upper Limit (+3% Reject Threshold) | Tolerance Quantity Range (±5%) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **A** | Cotton twill fabric, 280 gsm | metre | 12,000 | 480.00 BDT | 494.40 BDT | 11,400 to 12,600 |
| **B** | Metal zipper, 18 cm | piece | 20,000 | 38.00 BDT | 39.14 BDT | 19,000 to 21,000 |
| **C** | Polyester sewing thread, cone | cone | 800 | 210.00 BDT | 216.30 BDT | 760 to 840 |
| **D** | Poly bag, 30 x 40 cm | piece | 50,000 | 6.50 BDT | 6.695 BDT | 47,500 to 52,500 |
| **E** | Carton box, 5-ply | piece | 3,000 | 95.00 BDT | 97.85 BDT | 2,850 to 3,150 |

---

## 4. Company Rules Summary (`company-rules.md`)

The company evaluation logic follows an absolute precedence order: **REJECT** > **NEEDS HUMAN REVIEW** > **APPROVE**.

### Precedence Tier 1: Rejection Rules (`REJECT`)
If **any one** of the following conditions is met, the system must immediately issue a **REJECT** decision:
1. **Unit Price Breach:** Quoted unit price is strictly greater than 3% above the maximum unit price in the purchase request (`Unit_Price > PR_Max_Price * 1.03`).
2. **Excessive Advance Payment:** Advance payment requested exceeds 20% (`Advance_Payment_Pct > 20%`).
3. **Missing Late-Delivery Penalty:** The quotation / contract terms have no late-delivery penalty clause.
4. **Missing Tax Identification:** The supplier's Tax Identification Number (TIN) or Business Identification Number (BIN) is missing.
5. **Excessive Delivery Window:** Delivery is promised later than 45 days after the purchase order (`Delivery_Days > 45`).

### Precedence Tier 2: Human Review Triggers (`NEEDS HUMAN REVIEW`)
If **no rejection rule applies**, the system checks if **any one** of the following triggers human inspection:
1. **Marginal Price Excess:** Unit price is above the PR maximum, but by no more than 3% (`PR_Max_Price < Unit_Price <= PR_Max_Price * 1.03`).
2. **Quantity Discrepancy:** Quoted quantity differs from the requested quantity by more than 5% (`|Quoted_Qty - PR_Qty| / PR_Qty > 0.05`).
3. **Payment Term Ambiguity / Window:** Payment terms are unclear, or credit term is outside 30 to 60 days after delivery.
4. **Borderline Delivery Timeline:** Delivery is promised in 31 to 45 days (`31 <= Delivery_Days <= 45`).
5. **VAT Separation Defect:** VAT is not shown separately at 15% (e.g., VAT inclusive, wrong rate, or omitted).
6. **Arithmetic Error:** Financial figures do not add up (e.g., line total $\neq \text{Qty} \times \text{Price}$, subtotal mismatch, or VAT/Total mismatch).
7. **Insufficient Quotation Validity:** The quotation validity period is strictly less than 30 days (`Validity_Days < 30`).

### Precedence Tier 3: Approval (`APPROVE`)
Issued **only if none** of the rejection rules and **none** of the human review rules are triggered.

### Mandatory Operational Constraints
- **Minimum Penalty Rate:** Late-delivery penalty clause must provide at least 0.5% of order value per week of delay.
- **Evidence Requirement:** Every decision must quote the exact document text supporting the evaluation.
- **Strict Uncertainty Rule:** If any check is ambiguous, unreadable, or missing, the decision must default to `NEEDS HUMAN REVIEW`. Guessing is strictly prohibited.

---

## 5. Detailed Per-Document Analysis & Extraction

---

### Pack 01: `sample_data/supplier-pack-01.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Padma Textile Mills Ltd
- **Quotation No:** `QT-2026-901`
- **Quotation Date:** `2026-10-21`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `A`, `Cotton twill fabric, 280 gsm`
- **Quantity & Unit:** `12,000` `metre`
- **Unit Price (BDT):** `472.00`
- **Line Amount (BDT):** `5,664,000.00`
- **Subtotal (BDT):** `5,664,000.00`
- **VAT (15%):** `849,600.00`
- **Total Amount (BDT):** `6,513,600.00`
- **Tax IDs:** Supplier TIN: `101458013391` | BIN: `000170141-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "10% advance payable with the purchase order. Balance payable within 45 days after delivery and acceptance of goods."
  - *Clause 2 (Delivery):* "Delivery within 24 days of receiving the purchase order."
  - *Clause 3 (Delay):* "Late delivery penalty: 1% of order value for each full week of delay."
  - *Clause 4 (Validity):* "This quotation is valid for 45 days from the date above."
  - *Clause 5 & 6 (Quality & Disputes):* Replacement at supplier's cost; arbitration in Dhaka.

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 12,000 vs PR 12,000 ($0.0\%$ diff $\le 5\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 472.00 vs PR Max 480.00 (-1.67% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:** $12,000 \times 472.00 = 5,664,000.00$; VAT $5,664,000.00 \times 0.15 = 849,600.00$; Total $5,664,000 + 849,600 = 6,513,600.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $10\% \le 20\%$ $\rightarrow$ **PASS**
- **Payment Window:** 45 days (within 30–60 days window) $\rightarrow$ **PASS**
- **Delivery Timeline:** 24 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 1% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**
- **Tax Registration:** Both TIN & BIN present $\rightarrow$ **PASS**
- **Quotation Validity:** 45 days ($\ge 30$ days) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **APPROVE**
- **Justification:** All terms, technical specifications, registration credentials, pricing, and schedules strictly adhere to the purchase request and company policies without exceptions.
- **Supporting Evidence:**
  - Quote: *"Cotton twill fabric, 280 gsm | 12,000 | metre | 472.00 | 5,664,000.00"*
  - Quote: *"Supplier TIN: 101458013391 BIN: 000170141-0101"*
  - Quote: *"1. Payment. 10% advance payable with the purchase order. Balance payable within 45 days after delivery and acceptance of goods."*
  - Quote: *"2. Delivery. Delivery within 24 days of receiving the purchase order."*
  - Quote: *"3. Delay. Late delivery penalty: 1% of order value for each full week of delay."*

---

### Pack 02: `sample_data/supplier-pack-02.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Jamuna Trims and Accessories
- **Quotation No:** `QT-2026-902`
- **Quotation Date:** `2026-10-22`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `B`, `Metal zipper, 18 cm`
- **Quantity & Unit:** `20,000` `piece`
- **Unit Price (BDT):** `36.00`
- **Line Amount (BDT):** `720,000.00`
- **Subtotal (BDT):** `720,000.00`
- **VAT (15%):** `108,000.00`
- **Total Amount (BDT):** `828,000.00`
- **Tax IDs:** Supplier TIN: `102458023391` | BIN: `000270241-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "No advance payment required. Full payment within 30 days of delivery."
  - *Clause 2 (Delivery):* "Goods will be delivered at your factory within 21 days from the date of PO."
  - *Clause 3 (Delay):* "For late delivery the supplier shall pay 0.75% of the order value per week of delay."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."
  - *Clause 5 & 6 (Quality & Disputes):* Replacement at supplier's cost; arbitration in Dhaka.

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 20,000 vs PR 20,000 ($0.0\%$ diff $\le 5\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 36.00 vs PR Max 38.00 (-5.26% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:** $20,000 \times 36.00 = 720,000.00$; VAT $720,000.00 \times 0.15 = 108,000.00$; Total $720,000 + 108,000 = 828,000.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $0\% \le 20\%$ $\rightarrow$ **PASS**
- **Payment Window:** 30 days (within 30–60 days window) $\rightarrow$ **PASS**
- **Delivery Timeline:** 21 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.75% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**
- **Tax Registration:** Both TIN & BIN present $\rightarrow$ **PASS**
- **Quotation Validity:** 30 days ($\ge 30$ days) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **APPROVE**
- **Justification:** Complete compliance across pricing, quantities, delivery, late penalty, tax registration, and payment terms.
- **Supporting Evidence:**
  - Quote: *"Metal zipper, 18 cm | 20,000 | piece | 36.00 | 720,000.00"*
  - Quote: *"Supplier TIN: 102458023391 BIN: 000270241-0101"*
  - Quote: *"1. Payment. No advance payment required. Full payment within 30 days of delivery."*
  - Quote: *"2. Delivery. Goods will be delivered at your factory within 21 days from the date of PO."*
  - Quote: *"3. Delay. For late delivery the supplier shall pay 0.75% of the order value per week of delay."*

---

### Pack 03: `sample_data/supplier-pack-03.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Karnaphuli Yarn Traders
- **Quotation No:** `QT-2026-903`
- **Quotation Date:** `2026-10-23`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `C`, `Polyester sewing thread, cone`
- **Quantity & Unit:** `800` `cone`
- **Unit Price (BDT):** `229.00`
- **Line Amount (BDT):** `183,200.00`
- **Subtotal (BDT):** `183,200.00`
- **VAT (15%):** `27,480.00`
- **Total Amount (BDT):** `210,680.00`
- **Tax IDs:** Supplier TIN: `103458033391` | BIN: `000370341-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "15% advance payable with the purchase order. Balance within 40 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 20 days of PO."
  - *Clause 3 (Delay):* "Delay in delivery will attract a penalty of 0.5% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 800 vs PR 800 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 229.00 BDT vs PR Max 210.00 BDT:
  $$\Delta = \frac{229.00 - 210.00}{210.00} = +9.0476\% > +3.0\%$$
  Ceiling for rejection is $210.00 \times 1.03 = 216.30$ BDT. Quoted price exceeds ceiling by 12.70 BDT $\rightarrow$ **TRIGGER REJECT RULE 1**
- **Arithmetic Check:** $800 \times 229.00 = 183,200.00$; VAT = $27,480.00$; Total = $210,680.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $15\% \le 20\%$ $\rightarrow$ **PASS**
- **Delivery Timeline:** 20 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.5% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **REJECT**
- **Justification:** Violates **Reject Rule 1**: Unit price of 229.00 BDT is 9.05% higher than the maximum PR unit price (210.00 BDT), which exceeds the 3% maximum tolerance limit.
- **Supporting Evidence:**
  - Quote: *"Unit price (BDT) 229.00"*
  - Benchmark PR Max: `210.00 BDT` (Maximum allowable unit price +3%: `216.30 BDT`).

---

### Pack 04: `sample_data/supplier-pack-04.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Surma Packaging Industries
- **Quotation No:** `QT-2026-904`
- **Quotation Date:** `2026-10-24`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `D`, `Poly bag, 30 x 40 cm`
- **Quantity & Unit:** `50,000` `piece`
- **Unit Price (BDT):** `6.65`
- **Line Amount (BDT):** `332,500.00`
- **Subtotal (BDT):** `332,500.00`
- **VAT (15%):** `49,875.00`
- **Total Amount (BDT):** `382,375.00`
- **Tax IDs:** Supplier TIN: `104458043391` | BIN: `000470441-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "10% advance payable with the purchase order. Payment within 30 days after delivery."
  - *Clause 2 (Delivery):* "Delivery within 28 days of PO."
  - *Clause 3 (Delay):* "Late delivery penalty of 0.6% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 40 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 50,000 vs PR 50,000 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 6.65 BDT vs PR Max 6.50 BDT:
  $$\Delta = \frac{6.65 - 6.50}{6.50} = +2.3077\%$$
  Reject ceiling (+3%): $6.50 \times 1.03 = 6.695$ BDT.
  Since $6.50 < 6.65 \le 6.695$, it does not trigger rejection, but falls squarely into Human Review Rule 1 $\rightarrow$ **TRIGGER HUMAN REVIEW RULE 1**
- **Arithmetic Check:** $50,000 \times 6.65 = 332,500.00$; VAT $332,500 \times 0.15 = 49,875.00$; Total $382,375.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $10\% \le 20\%$ $\rightarrow$ **PASS**
- **Delivery Timeline:** 28 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.6% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**
- **Quotation Validity:** 40 days ($\ge 30$ days) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **NEEDS HUMAN REVIEW**
- **Justification:** Triggers **Human Review Rule 1**: Quoted unit price (6.65 BDT) exceeds the purchase request maximum price (6.50 BDT) by 2.31%, which is within the 3% discretionary review threshold. Management must decide whether to absorb the premium.
- **Supporting Evidence:**
  - Quote: *"Unit price (BDT) 6.65"*
  - Benchmark PR Max: `6.50 BDT` (Variance: `+0.15 BDT` / `+2.31%`).

---

### Pack 05: `sample_data/supplier-pack-05.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Meghna Carton Works
- **Quotation No:** `QT-2026-905`
- **Quotation Date:** `2026-10-25`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `E`, `Carton box, 5-ply`
- **Quantity & Unit:** `3,000` `piece`
- **Unit Price (BDT):** `92.00`
- **Line Amount (BDT):** `276,000.00`
- **Subtotal (BDT):** `276,000.00`
- **VAT (15%):** `41,400.00`
- **Total Amount (BDT):** `317,400.00`
- **Tax IDs:** Supplier TIN: `105458053391` | BIN: `000570541-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "40% advance payable with the purchase order. 40% advance with the purchase order, balance 60% within 30 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 25 days of PO."
  - *Clause 3 (Delay):* "Late delivery penalty of 1% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 3,000 vs PR 3,000 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 92.00 vs PR Max 95.00 (-3.16% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:** $3,000 \times 92.00 = 276,000.00$; VAT = $41,400.00$; Total = $317,400.00$ $\rightarrow$ **PASS**
- **Advance Payment Check:** Quoted $40\%$ vs Policy Max $20\%$ ($40\% > 20\%$) $\rightarrow$ **TRIGGER REJECT RULE 2**
- **Delivery Timeline:** 25 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 1% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **REJECT**
- **Justification:** Violates **Reject Rule 2**: Advance payment demanded is 40%, which significantly exceeds the maximum company threshold of 20%.
- **Supporting Evidence:**
  - Quote: *"1. Payment. 40% advance payable with the purchase order. 40% advance with the purchase order, balance 60% within 30 days of delivery."*

---

### Pack 06: `sample_data/supplier-pack-06.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Teesta Fabrics Ltd
- **Quotation No:** `QT-2026-906`
- **Quotation Date:** `2026-10-26`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `A`, `Cotton twill fabric, 280 gsm`
- **Quantity & Unit:** `12,000` `metre`
- **Unit Price (BDT):** `465.00`
- **Line Amount (BDT):** `5,580,000.00`
- **Subtotal (BDT):** `5,580,000.00`
- **VAT (15%):** `837,000.00`
- **Total Amount (BDT):** `6,417,000.00`
- **Tax IDs:** Supplier TIN: `106458063391` | BIN: `000670641-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "10% advance payable with the purchase order. Balance within 60 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 27 days of PO."
  - *Clause 3 (Validity):* "This quotation is valid for 30 days from the date above."
  - *Clause 4 (Quality):* "Goods are supplied as per the buyer's approved sample. Defective goods will be replaced at the supplier's cost."
  - *Clause 5 (Disputes):* "Any dispute will first be settled by discussion; failing that, through arbitration in Dhaka."
  - *Delay Clause:* **COMPLETELY MISSING**.

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 12,000 vs PR 12,000 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 465.00 vs PR Max 480.00 (-3.125% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:** $12,000 \times 465.00 = 5,580,000.00$; VAT = $837,000.00$; Total = $6,417,000.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $10\% \le 20\%$ $\rightarrow$ **PASS**
- **Delivery Timeline:** 27 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause Check:** The terms and conditions contain no late-delivery penalty clause whatsoever $\rightarrow$ **TRIGGER REJECT RULE 3**

#### Final Decision & Supporting Evidence
- **Decision:** **REJECT**
- **Justification:** Violates **Reject Rule 3**: The contract omits any late-delivery penalty clause.
- **Supporting Evidence:**
  - Quote: Enumerated clauses under *TERMS AND CONDITIONS*: *"1. Payment... 2. Delivery... 3. Validity... 4. Quality... 5. Disputes..."* (Late delivery penalty clause is completely absent).

---

### Pack 07: `sample_data/supplier-pack-07.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Rupsha Zipper Factory
- **Quotation No:** `QT-2026-907`
- **Quotation Date:** `2026-10-20`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `B`, `Metal zipper, 18 cm`
- **Quantity & Unit:** `16,500` `piece`
- **Unit Price (BDT):** `35.00`
- **Line Amount (BDT):** `577,500.00`
- **Subtotal (BDT):** `577,500.00`
- **VAT (15%):** `86,625.00`
- **Total Amount (BDT):** `664,125.00`
- **Tax IDs:** Supplier TIN: `107458073391` | BIN: `000770741-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "No advance payment required. Payment within 45 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 22 days of PO."
  - *Clause 3 (Delay):* "Late delivery penalty: 0.5% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 35 days from the date above."

#### Mathematical & Verification Checks
- **Unit Price Check:** Quoted 35.00 vs PR Max 38.00 (-7.89% $\le$ Max) $\rightarrow$ **PASS**
- **Quantity Check:** Quoted 16,500 piece vs PR Requested 20,000 piece:
  $$\Delta = \frac{|16,500 - 20,000|}{20,000} = \frac{3,500}{20,000} = 17.5\% > 5.0\%$$
  Difference of 3,500 pieces exceeds the allowable 5% tolerance (allowed range: 19,000 to 21,000) $\rightarrow$ **TRIGGER HUMAN REVIEW RULE 2**
- **Arithmetic Check:** $16,500 \times 35.00 = 577,500.00$; VAT $577,500 \times 0.15 = 86,625.00$; Total $664,125.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $0\% \le 20\%$ $\rightarrow$ **PASS**
- **Delivery Timeline:** 22 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.5% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **NEEDS HUMAN REVIEW**
- **Justification:** Triggers **Human Review Rule 2**: Quoted quantity (16,500 pieces) falls 17.5% short of the requested 20,000 pieces (a shortfall of 3,500 pieces), exceeding the 5% tolerance. Human review is required to confirm if partial fulfillment is acceptable.
- **Supporting Evidence:**
  - Quote: *"Qty 16,500"*
  - Benchmark PR Qty: `20,000 piece` (Shortfall: `3,500 piece` / `-17.5%`).

---

### Pack 08: `sample_data/supplier-pack-08.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Bhairab Thread and Co
- **Quotation No:** `QT-2026-908`
- **Quotation Date:** `2026-10-21`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `C`, `Polyester sewing thread, cone`
- **Quantity & Unit:** `800` `cone`
- **Unit Price (BDT):** `205.00`
- **Line Amount (BDT):** `164,000.00`
- **Subtotal (BDT):** `164,000.00`
- **VAT (15%):** `24,600.00`
- **Total Amount (BDT):** `188,600.00`
- **Tax IDs:** **NONE**. Stated: "Supplier registration details available on request."
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "10% advance payable with the purchase order. Payment within 30 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 18 days of PO."
  - *Clause 3 (Delay):* "Late delivery penalty of 0.5% per week of delay."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 800 vs PR 800 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 205.00 vs PR Max 210.00 (-2.38% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:** $800 \times 205.00 = 164,000.00$; VAT = $24,600.00$; Total = $188,600.00$ $\rightarrow$ **PASS**
- **Advance Payment:** $10\% \le 20\%$ $\rightarrow$ **PASS**
- **Delivery Timeline:** 18 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.5% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**
- **Tax Registration Check:** Both TIN and BIN are omitted $\rightarrow$ **TRIGGER REJECT RULE 4**

#### Final Decision & Supporting Evidence
- **Decision:** **REJECT**
- **Justification:** Violates **Reject Rule 4**: Supplier's TIN or BIN is missing from the quotation document.
- **Supporting Evidence:**
  - Quote: *"Supplier registration details available on request."* (Neither TIN nor BIN numbers are provided).

---

### Pack 09: `sample_data/supplier-pack-09.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Dhaleshwari Poly Pack
- **Quotation No:** `QT-2026-909`
- **Quotation Date:** `2026-10-22`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `D`, `Poly bag, 30 x 40 cm`
- **Quantity & Unit:** `50,000` `piece`
- **Unit Price (BDT):** `6.40`
- **Line Amount (BDT):** `322,000.00` *(Printed in table)*
- **Subtotal (BDT):** `322,000.00`
- **VAT (15%):** `48,300.00`
- **Total Amount (BDT):** `370,300.00`
- **Tax IDs:** Supplier TIN: `109458093391` | BIN: `000970941-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "5% advance payable with the purchase order. Payment within 30 to 90 days as agreed by both parties."
  - *Clause 2 (Delivery):* "Delivery within 4 weeks of PO."
  - *Clause 3 (Delay):* "Late delivery penalty of 0.5% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 50,000 vs PR 50,000 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 6.40 vs PR Max 6.50 (-1.54% $\le$ Max) $\rightarrow$ **PASS**
- **Arithmetic Check:**
  $$\text{Expected Line Total} = 50,000 \times 6.40 = 320,000.00 \text{ BDT}$$
  Document displays `322,000.00 BDT` (discrepancy of `+2,000.00 BDT`).
  Calculated VAT on subtotal is $322,000 \times 0.15 = 48,300.00$, and Total is $322,000 + 48,300 = 370,300.00$. While VAT and Total add up to the stated subtotal, the line item calculation itself is erroneous $\rightarrow$ **TRIGGER HUMAN REVIEW RULE 6**
- **Advance Payment:** $5\% \le 20\%$ $\rightarrow$ **PASS**
- **Payment Terms Check:** "Payment within 30 to 90 days as agreed by both parties."
  Window extends past 60 days (up to 90 days), and condition is contingent upon mutual negotiation $\rightarrow$ **TRIGGER HUMAN REVIEW RULE 3**
- **Delivery Timeline:** "within 4 weeks" = 28 days ($\le 30$ days) $\rightarrow$ **PASS**
- **Penalty Clause:** 0.5% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **NEEDS HUMAN REVIEW**
- **Justification:** Triggers **Human Review Rule 6** (numbers do not add up: $50,000 \times 6.40 = 320,000.00$ BDT, but document states 322,000.00 BDT) and **Human Review Rule 3** (payment credit terms extend up to 90 days, exceeding the 30–60 day standard, and are subject to ambiguous subsequent agreement).
- **Supporting Evidence:**
  - Quote: *"50,000 | piece | 6.40 | 322,000.00"* and *"Subtotal 322,000.00"* (Expected: 320,000.00 BDT).
  - Quote: *"1. Payment. 5% advance payable with the purchase order. Payment within 30 to 90 days as agreed by both parties."*

---

### Pack 10: `sample_data/supplier-pack-10.pdf`

#### Document Metadata & Extracted Entities
- **Supplier Name:** Kushiyara Box Industries
- **Quotation No:** `QT-2026-910`
- **Quotation Date:** `2026-10-23`
- **Customer / Reference:** Aamar Garments Ltd (fictional) / `PR-2026-114`
- **Item Code & Description:** Item `E`, `Carton box, 5-ply`
- **Quantity & Unit:** `3,000` `piece`
- **Unit Price (BDT):** `94.00` *(Column header: "Unit price (BDT, VAT included)")*
- **Line Amount (BDT):** `282,000.00`
- **Subtotal:** Not shown
- **VAT (15%):** Not shown separately
- **Total Amount (BDT):** `282,000.00` *(Row header: "Total (all taxes included)")*
- **Tax IDs:** Supplier TIN: `110458103391` | BIN: `001071041-0101`
- **Commercial & Legal Terms:**
  - *Clause 1 (Payment):* "10% advance payable with the purchase order. Payment within 45 days of delivery."
  - *Clause 2 (Delivery):* "Delivery within 60 days of PO."
  - *Clause 3 (Delay):* "Late delivery penalty of 0.5% of order value per week."
  - *Clause 4 (Validity):* "This quotation is valid for 30 days from the date above."

#### Mathematical & Verification Checks
- **Quantity Check:** Quoted 3,000 vs PR 3,000 ($0.0\%$) $\rightarrow$ **PASS**
- **Unit Price Check:** Quoted 94.00 vs PR Max 95.00 (-1.05% $\le$ Max) $\rightarrow$ **PASS**
- **Delivery Timeline Check:** Quoted delivery is 60 days of PO ($60 > 45$ days) $\rightarrow$ **TRIGGER REJECT RULE 5**
- **VAT Structure Check:** VAT is bundled into the unit price rather than shown separately at 15% $\rightarrow$ Would trigger Human Review Rule 5, but **Precedence Tier 1 Rejection supersedes Human Review**.
- **Advance Payment:** $10\% \le 20\%$ $\rightarrow$ **PASS**
- **Penalty Clause:** 0.5% per week ($\ge 0.5\%$) $\rightarrow$ **PASS**

#### Final Decision & Supporting Evidence
- **Decision:** **REJECT**
- **Justification:** Violates **Reject Rule 5**: Delivery timeline of 60 days exceeds the strict 45-day policy limit. (Additionally violates VAT separation rule, but Rejection takes absolute precedence).
- **Supporting Evidence:**
  - Quote: *"2. Delivery. Delivery within 60 days of PO."*
  - Secondary Quote: *"Unit price (BDT, VAT included) 94.00"* and *"Total (all taxes included) 282,000.00"*.

---

## 6. Discrepancy Matrix Across All 10 Packs

The following comparative matrix synthesizes how each supplier document performs across every policy dimension:

| Dimension | Rule Threshold | P01 | P02 | P03 | P04 | P05 | P06 | P07 | P08 | P09 | P10 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Target Item** | PR Items A–E | A | B | C | D | E | A | B | C | D | E |
| **Unit Price Check** | $\le \text{Max Price}$ | $\le$ | $\le$ | **>+3%** | **+2.3%** | $\le$ | $\le$ | $\le$ | $\le$ | $\le$ | $\le$ |
| **Quantity Match** | Within $\pm 5\%$ | 0% | 0% | 0% | 0% | 0% | 0% | **-17.5%** | 0% | 0% | 0% |
| **Advance %** | $\le 20\%$ | 10% | 0% | 15% | 10% | **40%** | 10% | 0% | 10% | 5% | 10% |
| **Credit Term** | 30 to 60 days | 45d | 30d | 40d | 30d | 30d | 60d | 45d | 30d | **30-90d** | 45d |
| **Delivery Time** | $\le 30\text{d (OK)}, \le 45\text{d (Rev)}, >45\text{d (Rej)}$ | 24d | 21d | 20d | 28d | 25d | 27d | 22d | 18d | 28d* | **60d** |
| **Penalty Clause** | Exists & $\ge 0.5\%/\text{wk}$ | 1.0% | 0.75% | 0.5% | 0.6% | 1.0% | **NONE** | 0.5% | 0.5% | 0.5% | 0.5% |
| **TIN & BIN** | Both must be present | Yes | Yes | Yes | Yes | Yes | Yes | Yes | **MISSING**| Yes | Yes |
| **VAT Display** | Separated at 15% | 15% | 15% | 15% | 15% | 15% | 15% | 15% | 15% | 15% | **BUNDLED**|
| **Arithmetic** | Line, Subtotal, VAT, Total match | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | **MISMATCH**| N/A |
| **Validity** | $\ge 30$ days | 45d | 30d | 30d | 40d | 30d | 30d | 35d | 30d | 30d | 30d |
| **FINAL VERDICT** | — | **APP** | **APP** | **REJ** | **REV** | **REJ** | **REJ** | **REV** | **REJ** | **REV** | **REJ** |

*\*Note: Pack 09 expresses delivery as "4 weeks", equivalent to 28 days.*

---

## 7. Uncertainties, Edge Cases & Parser Vulnerabilities

During manual and programmatic inspection of the 10 supplier packs, several edge cases were uncovered that require explicit handling in the proposed architecture:

### 1. Delivery Duration Unit Variance (Weeks vs. Days)
- **Manifestation:** In Pack 09, Clause 2 specifies *"Delivery within 4 weeks of PO"*, whereas all other packs state delivery explicitly in days (e.g., *"within 24 days"*).
- **Architecture Impact:** A naive regex searching only for `r"within (\d+) days"` will fail on Pack 09 and falsely flag delivery as unreadable or missing. The extraction normalization engine must parse duration units (`weeks`, `months`, `working days`, `calendar days`) and convert them to calendar day equivalents before evaluation.

### 2. Embedded Arithmetic Discrepancy (Pack 09)
- **Manifestation:** In Pack 09, Item D has Qty = 50,000 and Unit Price = 6.40. $50,000 \times 6.40 = 320,000.00$, but the PDF displays Amount = 322,000.00 and Subtotal = 322,000.00. However, the subsequent calculations ($322,000 \times 0.15 = 48,300$ and $322,000 + 48,300 = 370,300$) are mathematically consistent with the *incorrect* subtotal.
- **Architecture Impact:** Arithmetic verification must not stop at verifying `Subtotal + VAT == Total`. It must verify the entire dependency tree starting from primitive inputs:
  1. $\text{Line Amount} = \text{Quantity} \times \text{Unit Price}$
  2. $\text{Subtotal} = \sum \text{Line Amounts}$
  3. $\text{VAT} = \text{Subtotal} \times 0.15$
  4. $\text{Total} = \text{Subtotal} + \text{VAT}$

### 3. Multi-Violation Precedence Resolution (Pack 10)
- **Manifestation:** Pack 10 violates both **Reject Rule 5** (Delivery within 60 days $> 45$ days) and **Human Review Rule 5** (VAT not shown separately at 15%).
- **Architecture Impact:** The rule evaluation engine must strictly enforce rule hierarchy. Reject criteria must always supersede Human Review triggers. Additionally, the audit report must capture *all* violated rules, ranking the primary rejection reason first, while listing secondary review observations for human awareness.

### 4. Duplicate Phrasing in Legal Clauses (Pack 05)
- **Manifestation:** In Pack 05, Clause 1 reads: *"40% advance payable with the purchase order. 40% advance with the purchase order, balance 60% within 30 days of delivery."*
- **Architecture Impact:** LLM extractors could be confused by redundant sentence fragments or hallucinate multiple payments. The extraction schema must isolate the initial deposit percentage deterministically.

### 5. Absence of Explicit Identifiers (Pack 08)
- **Manifestation:** Pack 08 does not leave the TIN/BIN field blank; instead, it includes an evasive sentence: *"Supplier registration details available on request."*
- **Architecture Impact:** The extractor must recognize that evasive statements or promissory notes do not satisfy the requirement for explicit Tax Identification Numbers on the face of the quotation.

### 6. Floating Point Precision in Percentage Tolerances (Pack 04)
- **Manifestation:** In Pack 04, unit price is 6.65 BDT vs max 6.50 BDT.
  $$\frac{6.65 - 6.50}{6.50} = \frac{0.15}{6.50} = 0.023076923...$$
  $6.50 \times 1.03 = 6.695$.
- **Architecture Impact:** If floating-point arithmetic is evaluated with naive rounding, edge cases near 3% could flip between `REJECT` and `NEEDS HUMAN REVIEW`. The system must use `decimal.Decimal` with fixed-precision rounding (e.g. 4 decimal places) for monetary and percentage calculations.

---

## 8. Verification Conclusion

The sample analysis confirms that the provided test suite comprehensively exercises every reject condition, human review trigger, and approval pathway defined in `company-rules.md`. The findings in this document provide a sound, fully verified foundation for designing the system architecture in `docs/proposed_architecture.md`.

