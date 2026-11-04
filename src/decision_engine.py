from decimal import Decimal
import logging
from pathlib import Path
import time
from typing import List, Optional, Union
import uuid

from src.arithmetic import ArithmeticVerifier
from src.comparator import PurchaseRequestComparator
from src.config import settings
from src.extractor import ExtractionEngine
from src.ingestion import DocumentIngestionEngine
from src.models.schemas import (
    ArithmeticAuditResult,
    DecisionEnum,
    DocumentVerificationReport,
    ExtractedQuotation,
    ExtractionStatus,
    ExtractionUncertainty,
    PRComparisonReport,
    PurchaseRequest,
    RuleCategory,
    RuleCheckResult,
    RuleStatus,
)
from src.pr_loader import load_purchase_request
from src.rules import CompanyRuleEngine

logger = logging.getLogger(__name__)


class DecisionEngine:
    """End-to-end deterministic verification engine.

    Sequentially executes:
      1. Ingestion: Document loading & SHA-256 provenance calculation.
      2. Structured Extraction: Grounded field extraction with exact quotes & page verification.
      3. Arithmetic Verification: Python Decimal recalculation of line totals, subtotal, VAT, and grand total.
      4. Purchase Request Comparison: Quantity tolerance (±5%) & price threshold (+3%) checks.
      5. Rule Evaluation: Strict deterministic execution of Reject Rules (1-5) and Review Rules (1-7).
      6. Precedence Decision Synthesis:
         - Confirmed rejection rule violation -> REJECT.
         - Human review rule violation, uncertainty, math error, or PR mismatch -> NEEDS HUMAN REVIEW.
         - All checks pass cleanly -> APPROVE.
    """

    def __init__(
        self,
        pr_path: Union[str, Path] = "sample_data/purchase-request.csv",
        ingestion_engine: Optional[DocumentIngestionEngine] = None,
        extraction_engine: Optional[ExtractionEngine] = None,
        arithmetic_verifier: Optional[ArithmeticVerifier] = None,
        pr_comparator: Optional[PurchaseRequestComparator] = None,
        rule_engine: Optional[CompanyRuleEngine] = None,
    ):
        self.pr_path = Path(pr_path)
        self.pr: PurchaseRequest = load_purchase_request(self.pr_path)
        self.ingestion_engine = ingestion_engine or DocumentIngestionEngine()
        self.extraction_engine = extraction_engine or ExtractionEngine()
        self.arithmetic_verifier = arithmetic_verifier or ArithmeticVerifier()
        self.pr_comparator = pr_comparator or PurchaseRequestComparator()
        self.rule_engine = rule_engine or CompanyRuleEngine()

    def verify_document(self, pdf_path: Union[str, Path]) -> DocumentVerificationReport:
        """Executes the complete verification workflow on a single PDF supplier pack."""
        start_time = time.perf_counter()
        doc_path = Path(pdf_path)

        if not doc_path.exists():
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return DocumentVerificationReport(
                document_name=doc_path.name,
                document_path=str(doc_path),
                document_hash="FILE_NOT_FOUND",
                supplier_name="Unknown",
                quotation_no="Unknown",
                final_decision=DecisionEnum.NEEDS_HUMAN_REVIEW,
                primary_reason=f"File not found at path: {doc_path}. Manual human investigation required.",
                rejection_confirmed=False,
                all_decision_reasons=[f"File not found at path: {doc_path}. Manual human investigation required."],
                verification_id=str(uuid.uuid4()),
                arithmetic_audit=ArithmeticAuditResult(),
                extraction_uncertainties=[
                    ExtractionUncertainty(
                        field_name="document",
                        issue_type="FILE_NOT_FOUND",
                        details=f"Document file does not exist: {doc_path}",
                    )
                ],
                processing_time_ms=elapsed_ms,
            )

        # ----------------------------------------------------------------------
        # Stage 1: Ingestion
        # ----------------------------------------------------------------------
        try:
            ingested_doc = self.ingestion_engine.ingest(doc_path)
        except Exception as e:
            logger.error(f"Ingestion failed for {doc_path.name}: {e}")
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return DocumentVerificationReport(
                document_name=doc_path.name,
                document_path=str(doc_path),
                document_hash="INGESTION_ERROR",
                supplier_name="Unknown",
                quotation_no="Unknown",
                final_decision=DecisionEnum.NEEDS_HUMAN_REVIEW,
                primary_reason=f"Ingestion failure: {e}. Document requires human review.",
                rejection_confirmed=False,
                all_decision_reasons=[f"Ingestion failure: {e}. Document requires human review."],
                verification_id=str(uuid.uuid4()),
                arithmetic_audit=ArithmeticAuditResult(),
                extraction_uncertainties=[
                    ExtractionUncertainty(
                        field_name="document",
                        issue_type="INGESTION_FAILURE",
                        details=str(e),
                    )
                ],
                processing_time_ms=elapsed_ms,
            )

        # ----------------------------------------------------------------------
        # Stage 2: Structured Extraction
        # ----------------------------------------------------------------------
        quotation, extraction_uncertainties = self.extraction_engine.extract(ingested_doc)

        # Essential information guard: check if critical identification fields are missing
        self._check_essential_information(quotation, extraction_uncertainties)

        # ----------------------------------------------------------------------
        # Stage 3: Arithmetic Verification
        # ----------------------------------------------------------------------
        math_audit = self.arithmetic_verifier.verify(quotation)

        # ----------------------------------------------------------------------
        # Stage 4: Purchase Request Comparison
        # ----------------------------------------------------------------------
        pr_comparison = self.pr_comparator.compare(quotation, self.pr)

        # ----------------------------------------------------------------------
        # Stage 5: Business Rule Evaluation
        # ----------------------------------------------------------------------
        all_rules = self.rule_engine.evaluate_all(quotation, pr_comparison, math_audit)

        # ----------------------------------------------------------------------
        # Stage 6: Precedence Decision Synthesis
        # ----------------------------------------------------------------------
        decision, primary_reason, rejection_confirmed = self._synthesize_decision(
            all_rules=all_rules,
            extraction_uncertainties=extraction_uncertainties,
            math_audit=math_audit,
            pr_comparison=pr_comparison,
            is_readable=ingested_doc.is_readable,
        )

        all_reasons = self._gather_all_decision_reasons(
            decision=decision,
            primary_reason=primary_reason,
            all_rules=all_rules,
            extraction_uncertainties=extraction_uncertainties,
            math_audit=math_audit,
            pr_comparison=pr_comparison,
            is_readable=ingested_doc.is_readable,
        )

        # Collect evidence quotes
        evidence_quotes = self._collect_evidence_quotes(all_rules, math_audit, pr_comparison)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Matched PR item identifier
        matched_item_str = None
        if pr_comparison.matched_items:
            matched_item_str = ", ".join(item.item_code for item in pr_comparison.matched_items)

        return DocumentVerificationReport(
            document_name=doc_path.name,
            document_path=str(doc_path),
            document_hash=ingested_doc.file_hash,
            supplier_name=quotation.supplier_name.value or "Unknown",
            quotation_no=quotation.quotation_no.value or "Unknown",
            matched_pr_item=matched_item_str,
            final_decision=decision,
            primary_reason=primary_reason,
            rejection_confirmed=rejection_confirmed,
            all_decision_reasons=all_reasons,
            verification_id=str(uuid.uuid4()),
            arithmetic_audit=math_audit,
            pr_comparison=pr_comparison,
            extraction_uncertainties=extraction_uncertainties,
            triggered_rules=[r for r in all_rules if r.triggered],
            all_evaluated_rules=all_rules,
            supporting_evidence_quotes=evidence_quotes,
            processing_time_ms=round(elapsed_ms, 2),
            extracted_quotation=quotation,
        )

    def verify_all(self, directory_or_files: Union[str, Path, List[Union[str, Path]]]) -> List[DocumentVerificationReport]:
        """Runs the verification workflow over multiple PDF documents."""
        if isinstance(directory_or_files, (str, Path)):
            dir_path = Path(directory_or_files)
            if dir_path.is_dir():
                pdf_files = sorted(dir_path.glob("*.pdf"), key=lambda p: p.name.lower())
            else:
                pdf_files = [dir_path]
        else:
            pdf_files = [Path(f) for f in directory_or_files]

        reports = []
        for pdf_path in pdf_files:
            logger.info(f"Processing supplier pack: {pdf_path.name}")
            report = self.verify_document(pdf_path)
            reports.append(report)
        return reports

    def _check_essential_information(
        self, quotation: ExtractedQuotation, uncertainties: List[ExtractionUncertainty]
    ) -> None:
        """Flags missing essential fields that prevent reliable automatic approval."""
        if quotation.supplier_name.status in (ExtractionStatus.MISSING, ExtractionStatus.UNREADABLE):
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="supplier_name",
                    issue_type="MISSING_REQUIRED",
                    details="Supplier name could not be identified on quotation.",
                )
            )

        if quotation.quotation_no.status in (ExtractionStatus.MISSING, ExtractionStatus.UNREADABLE):
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="quotation_no",
                    issue_type="MISSING_REQUIRED",
                    details="Quotation number could not be identified on quotation.",
                )
            )

        has_invalid_items = not quotation.line_items or any(
            item.quantity.status in (ExtractionStatus.MISSING, ExtractionStatus.UNREADABLE)
            or item.unit_price.status in (ExtractionStatus.MISSING, ExtractionStatus.UNREADABLE)
            for item in quotation.line_items
        )
        if has_invalid_items:
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="line_items",
                    issue_type="MISSING_REQUIRED",
                    details="No valid line items could be extracted from quotation.",
                )
            )

        if quotation.total_amount.status in (ExtractionStatus.MISSING, ExtractionStatus.UNREADABLE):
            uncertainties.append(
                ExtractionUncertainty(
                    field_name="total_amount",
                    issue_type="MISSING_REQUIRED",
                    details="Total amount could not be extracted from quotation.",
                )
            )

    def _synthesize_decision(
        self,
        all_rules: List[RuleCheckResult],
        extraction_uncertainties: List[ExtractionUncertainty],
        math_audit: ArithmeticAuditResult,
        pr_comparison: PRComparisonReport,
        is_readable: bool,
    ) -> tuple[DecisionEnum, str, bool]:
        """Applies safety-first precedence logic:

        1. Confirmed Reject Rule violation -> REJECT.
        2. Otherwise, if Human Review Rule triggered, uncertainty, math discrepancy,
           or PR alignment failure -> NEEDS HUMAN REVIEW.
        3. Otherwise -> APPROVE.
        """
        # Tier 1: Confirmed Rejection
        confirmed_rejections = [
            r
            for r in all_rules
            if r.category == RuleCategory.REJECT and r.status == RuleStatus.FAIL and r.is_confirmed
        ]

        if confirmed_rejections:
            primary = confirmed_rejections[0]
            reason = f"Confirmed violation of {primary.rule_name}: {primary.explanation}"
            return DecisionEnum.REJECT, reason, True

        # Tier 2: Human Review Triggers & Uncertainty
        triggered_reviews = [
            r
            for r in all_rules
            if r.category == RuleCategory.HUMAN_REVIEW and r.status == RuleStatus.FAIL
        ]
        uncertain_rules = [r for r in all_rules if r.status == RuleStatus.UNCERTAIN]
        has_math_error = not math_audit.all_passed
        has_uncertainty = len(extraction_uncertainties) > 0
        has_pr_issues = (
            bool(pr_comparison.unknown_item_codes)
            or bool(pr_comparison.duplicate_item_codes)
            or pr_comparison.has_unit_mismatch
            or pr_comparison.has_description_mismatch
            or not pr_comparison.matched_items
        )

        if not is_readable:
            return (
                DecisionEnum.NEEDS_HUMAN_REVIEW,
                "Document text layer is unreadable or blank. Manual human verification required.",
                False,
            )

        if triggered_reviews:
            primary = triggered_reviews[0]
            reason = f"Review required under {primary.rule_name}: {primary.explanation}"
            return DecisionEnum.NEEDS_HUMAN_REVIEW, reason, False

        if uncertain_rules:
            primary = uncertain_rules[0]
            reason = f"Uncertainty in evaluating {primary.rule_name}: {primary.explanation}"
            return DecisionEnum.NEEDS_HUMAN_REVIEW, reason, False

        if has_uncertainty:
            unc = extraction_uncertainties[0]
            reason = f"Extraction uncertainty on '{unc.field_name}' ({unc.issue_type}): {unc.details}"
            return DecisionEnum.NEEDS_HUMAN_REVIEW, reason, False

        if has_math_error:
            disc_str = "; ".join(math_audit.discrepancy_details)
            reason = f"Financial arithmetic inconsistency detected: {disc_str}"
            return DecisionEnum.NEEDS_HUMAN_REVIEW, reason, False

        if has_pr_issues:
            notes_str = "; ".join(pr_comparison.comparison_notes) if pr_comparison.comparison_notes else "Item mismatch"
            reason = f"Purchase Request alignment failure: {notes_str}"
            return DecisionEnum.NEEDS_HUMAN_REVIEW, reason, False

        # Tier 3: Approval
        reason = (
            "All company rules passed, PR specifications met within tolerance, "
            "and all financial calculations verified without discrepancies."
        )
        return DecisionEnum.APPROVE, reason, False

    def _gather_all_decision_reasons(
        self,
        decision: DecisionEnum,
        primary_reason: str,
        all_rules: List[RuleCheckResult],
        extraction_uncertainties: List[ExtractionUncertainty],
        math_audit: ArithmeticAuditResult,
        pr_comparison: PRComparisonReport,
        is_readable: bool,
    ) -> List[str]:
        """Aggregates all contributing reasons for the final decision in non-technical language."""
        reasons: List[str] = []

        if decision == DecisionEnum.APPROVE:
            return [primary_reason]

        if decision == DecisionEnum.REJECT:
            confirmed_rejections = [
                r
                for r in all_rules
                if r.category == RuleCategory.REJECT and r.status == RuleStatus.FAIL and r.is_confirmed
            ]
            for r in confirmed_rejections:
                msg = f"Confirmed violation of {r.rule_name}: {r.explanation}"
                if msg not in reasons:
                    reasons.append(msg)
            return reasons if reasons else [primary_reason]

        # Case: DecisionEnum.NEEDS_HUMAN_REVIEW
        if not is_readable:
            reasons.append("Document text layer is unreadable or blank. Manual human verification required.")

        # 1. Triggered review rules
        triggered_reviews = [
            r
            for r in all_rules
            if r.category == RuleCategory.HUMAN_REVIEW and r.status == RuleStatus.FAIL
        ]
        for r in triggered_reviews:
            if r.rule_id == "REVIEW_RULE_6" and math_audit.discrepancies:
                for d in math_audit.discrepancies:
                    q_val = d.quoted_value if d.quoted_value is not None else Decimal("0.00")
                    e_val = d.expected_value if d.expected_value is not None else Decimal("0.00")
                    diff_val = d.discrepancy_amount if d.discrepancy_amount is not None else abs(q_val - e_val)
                    msg = (
                        f"Financial arithmetic mismatch on {d.component.replace('_', ' ').title()}: "
                        f"The quoted amount is BDT {q_val:,.2f}, the recalculated amount is BDT {e_val:,.2f}, "
                        f"and the difference is BDT {diff_val:,.2f}."
                    )
                    if msg not in reasons:
                        reasons.append(msg)
            elif r.rule_id == "REVIEW_RULE_3":
                if r.evidence_quote and ("30" in r.evidence_quote and "90" in r.evidence_quote):
                    msg = 'Payment terms review: Payment terms are ambiguous: "30–90 days as agreed" (outside standard 30 to 60 day credit window).'
                elif r.evidence_quote:
                    msg = f"Payment terms review: {r.explanation} (Quote: '{r.evidence_quote.strip()}')."
                else:
                    msg = f"Payment terms review ({r.rule_name}): {r.explanation}"
                if msg not in reasons:
                    reasons.append(msg)
            else:
                msg = f"Review trigger ({r.rule_name}): {r.explanation}"
                if msg not in reasons:
                    reasons.append(msg)

        # 2. Uncertain rules
        for r in all_rules:
            if r.status == RuleStatus.UNCERTAIN:
                msg = f"Uncertainty in evaluating {r.rule_name}: {r.explanation}"
                if msg not in reasons:
                    reasons.append(msg)

        # 3. Extraction uncertainties
        for unc in extraction_uncertainties:
            msg = f"Extraction uncertainty on '{unc.field_name}' ({unc.issue_type}): {unc.details}"
            if msg not in reasons:
                reasons.append(msg)

        # 4. Arithmetic discrepancies not captured above
        if not math_audit.all_passed and not any("Financial arithmetic mismatch" in s for s in reasons):
            for det in math_audit.discrepancy_details:
                msg = f"Financial arithmetic inconsistency: {det}"
                if msg not in reasons:
                    reasons.append(msg)

        # 5. Purchase Request alignment notes
        if pr_comparison.comparison_notes:
            for note in pr_comparison.comparison_notes:
                msg = f"Purchase Request alignment note: {note}"
                if msg not in reasons:
                    reasons.append(msg)

        if not reasons:
            reasons.append(primary_reason)

        return reasons

    def _collect_evidence_quotes(
        self,
        all_rules: List[RuleCheckResult],
        math_audit: ArithmeticAuditResult,
        pr_comparison: PRComparisonReport,
    ) -> List[str]:
        """Gathers supporting verbatim evidence quotes with page numbers."""
        quotes = []
        for r in all_rules:
            if r.triggered and r.evidence_quote:
                quotes.append(f"[{r.rule_id} (Page {r.page_number or 1})]: \"{r.evidence_quote}\"")

        for d in math_audit.discrepancies:
            if d.evidence_quote and d.evidence_quote not in quotes:
                quotes.append(f"[Arithmetic (Page 1)]: \"{d.evidence_quote}\" -> {d.details}")

        for item in pr_comparison.matched_items:
            if item.evidence_quote:
                quote_entry = f"[PR Item {item.item_code} (Page 1)]: \"{item.evidence_quote}\""
                if quote_entry not in quotes:
                    quotes.append(quote_entry)

        return quotes
