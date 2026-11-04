import os
import json
import streamlit as st
import logging
from pathlib import Path
import tempfile
import time
from typing import List, Optional

import pandas as pd
import streamlit as st

from src.app_helpers import (
    build_plain_language_findings,
    cleanup_directory,
    get_all_decision_reasons,
    get_decision_color_theme,
    get_evidence_traceability_items,
    get_extracted_summary_fields,
    get_financial_discrepancies,
    get_next_step_guidance,
    load_benchmark_report_json,
    load_benchmark_report_markdown,
    save_uploaded_stream_to_temp,
    validate_uploaded_pdf,
)
from src.audit_history import AuditHistoryRepository, AuditRecord, DHAKA_TZ
from src.config import settings
from src.decision_engine import DecisionEngine
from src.evaluation import EvaluationBenchmark
from src.models.schemas import (
    DecisionEnum,
    DocumentVerificationReport,
    RuleStatus,
)
from src.report_generator import (
    generate_batch_csv_summary,
    generate_batch_excel_summary,
    generate_batch_json_summary,
    generate_batch_markdown_summary,
    generate_benchmark_excel_report,
    generate_individual_excel_report,
    generate_individual_json_report,
    generate_individual_markdown_report,
)

# Initialize audit repository
audit_repo = AuditHistoryRepository(retention_hours=settings.audit_retention_hours)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Streamlit Page Setup
st.set_page_config(
    page_title="Supplier Document Verification System | Aamar Garments Ltd",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Enterprise CSS
st.markdown(
    """
    <style>
    /* Main Layout & Typography */
    .main {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top Header Bar */
    .app-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        border-bottom: 3px solid #3b82f6;
    }
    .app-header h1 {
        margin: 0;
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .app-header p {
        margin: 0.35rem 0 0 0;
        font-size: 0.95rem;
        color: #94a3b8;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    }
    .metric-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-val {
        font-size: 1.85rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 0.25rem;
    }
    
    /* Decision Badges */
    .badge-approve {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
        padding: 0.25rem 0.6rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-reject {
        background-color: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
        padding: 0.25rem 0.6rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-review {
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
        padding: 0.25rem 0.6rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    
    /* Audit Card Containers */
    .audit-section {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
    }
    
    /* Evidence Quote Box */
    .evidence-box {
        background-color: #f1f5f9;
        border-left: 4px solid #3b82f6;
        padding: 0.6rem 0.9rem;
        font-family: monospace;
        font-size: 0.88rem;
        color: #1e293b;
        margin: 0.35rem 0;
        border-radius: 0 4px 4px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state():
    """Initializes isolated session state variables."""
    if "live_reports" not in st.session_state:
        st.session_state["live_reports"] = []
    if "selected_doc_index" not in st.session_state:
        st.session_state["selected_doc_index"] = 0
    if "last_processed_time" not in st.session_state:
        st.session_state["last_processed_time"] = None
    if "is_demo_run" not in st.session_state:
        st.session_state["is_demo_run"] = False


init_session_state()


# ------------------------------------------------------------------------------
# Sidebar Navigation & Settings
# ------------------------------------------------------------------------------
st.sidebar.markdown("### 🏢 Aamar Garments Ltd")
st.sidebar.markdown("**AI Supplier Document Verification**")
st.sidebar.caption("Deterministic Compliance & Audit System")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "📊 Dashboard",
        "🔍 Document Verification",
        "📋 Decision Results",
        "🔬 Deep Audit Inspector",
        "📈 Benchmark & Evaluation",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚙️ Verification Parameters")
pr_path_input = st.sidebar.text_input(
    "Purchase Request File",
    value="sample_data/purchase-request.csv",
    help="Path to purchase-request.csv containing reference quantities and price ceilings.",
)
rules_path_input = st.sidebar.text_input(
    "Company Rules Policy",
    value="sample_data/company-rules.md",
    help="Path to company-rules.md document containing deterministic business rules.",
)

with st.sidebar.expander("Policy Thresholds (Read-Only)"):
    st.write(f"- **Price Reject Ceiling:** `+{settings.price_rejection_threshold * 100:.1f}%`")
    st.write(f"- **Qty Tolerance Band:** `±{settings.quantity_tolerance_threshold * 100:.1f}%`")
    st.write(f"- **Max Advance Payment:** `{settings.max_advance_payment_pct:.0f}%`")
    st.write(f"- **Max Delivery Duration:** `{settings.max_delivery_days:.0f} days`")
    st.write(f"- **Min Late Penalty:** `{settings.min_late_penalty_pct_per_week:.1f}% / week`")
    st.write(f"- **Required VAT:** `{settings.standard_vat_rate * 100:.0f}% separated`")
    st.write(f"- **Standard Credit Terms:** `{settings.min_credit_days_review}–{settings.max_credit_days_review} days`")

st.sidebar.markdown("---")
st.sidebar.caption("System Engine: **Deterministic Regex & Layout Grounding**")
st.sidebar.caption("LLM API Key: **Not Required (Deterministic Mode Active)**")


# ------------------------------------------------------------------------------
# Top App Header
# ------------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>🛡️ Supplier Document Verification System</h1>
        <p>Aamar Garments Ltd Procurement Compliance • Fully Deterministic Verification Pipeline with Grounded Evidence</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# SECTION 1: DASHBOARD
# ==============================================================================
if nav_choice == "📊 Dashboard":
    st.subheader("Executive Verification Dashboard")
    st.caption("Live and persistent audit monitoring of supplier document compliance (Asia/Dhaka Local Time).")

    # Date and Source Filtering Controls
    f_col1, f_col2, f_col3 = st.columns([2, 2, 1])

    # Get unexpired records for filter options
    all_unfiltered_records = audit_repo.get_records(limit=2000)
    available_dates = sorted(list(set(r.date_dhaka for r in all_unfiltered_records)), reverse=True)

    with f_col1:
        date_filter_options = ["Today (Asia/Dhaka) & Last 24h", "All History"] + available_dates
        selected_date_filter = st.selectbox(
            "📅 Date Filter",
            options=date_filter_options,
            index=0,
            help="Filter verification records by Asia/Dhaka date or rolling 24-hour window.",
        )
    with f_col2:
        source_filter = st.selectbox(
            "📂 Source Filter",
            options=["All Sources", "Upload", "Benchmark Demo"],
            index=0,
            help="Filter between real document uploads and benchmark demonstration runs.",
        )
    with f_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

    # Determine filter query parameters
    now_epoch = time.time()
    if selected_date_filter == "Today (Asia/Dhaka) & Last 24h":
        start_epoch_filter = now_epoch - (24 * 3600.0)
        specific_date_filter = None
    elif selected_date_filter == "All History":
        start_epoch_filter = None
        specific_date_filter = None
    else:
        start_epoch_filter = None
        specific_date_filter = selected_date_filter

    src_query = (
        "UPLOAD"
        if source_filter == "Upload"
        else ("BENCHMARK_DEMO" if source_filter == "Benchmark Demo" else None)
    )

    # Fetch records based on the single source of truth
    filtered_records: List[AuditRecord] = audit_repo.get_records(
        date_filter=specific_date_filter,
        source_filter=src_query,
        start_epoch=start_epoch_filter,
    )

    metrics = audit_repo.get_dashboard_metrics(filtered_records)
    total_docs = metrics["total_quotations"]
    approved_docs = metrics["approved_count"]
    rejected_docs = metrics["rejected_count"]
    review_docs = metrics["review_count"]
    approval_rate = metrics["approval_rate_pct"]

    # Metric Cards Row (All calculated from identical filtered records)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Quotations Received</div>
                <div class="metric-val">{total_docs}</div>
                <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.2rem;">Approval Rate: <strong>{approval_rate}%</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4px solid #10b981;">
                <div class="metric-label">Approved</div>
                <div class="metric-val" style="color: #166534;">{approved_docs}</div>
                <div style="font-size: 0.8rem; color: #166534; margin-top: 0.2rem;">Policy Compliant</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4px solid #ef4444;">
                <div class="metric-label">Rejected</div>
                <div class="metric-val" style="color: #991b1b;">{rejected_docs}</div>
                <div style="font-size: 0.8rem; color: #991b1b; margin-top: 0.2rem;">Confirmed Violations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4px solid #f59e0b;">
                <div class="metric-label">Needs Human Review</div>
                <div class="metric-val" style="color: #92400e;">{review_docs}</div>
                <div style="font-size: 0.8rem; color: #92400e; margin-top: 0.2rem;">Requires Manual Review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("#### Decision Distribution")
        if total_docs > 0:
            dist_df = pd.DataFrame(
                {
                    "Decision": ["APPROVE", "REJECT", "NEEDS HUMAN REVIEW"],
                    "Count": [approved_docs, rejected_docs, review_docs],
                }
            ).set_index("Decision")
            st.bar_chart(dist_df, color="#3b82f6")
        else:
            st.info("ℹ️ No verification records match the selected date filter to generate the chart.")

    with c2:
        st.markdown("#### Audit Persistence & Retention Status")
        st.markdown(
            f"""
            - **Storage Engine:** Local SQLite with WAL mode (`{settings.audit_db_path.name}`)
            - **Configured Retention:** Rolling `{settings.audit_retention_hours} hours` (expired records automatically purged)
            - **Timezone Standardization:** Stored in **UTC**, grouped & displayed in **Asia/Dhaka (UTC+6)**
            - **Pipeline Assurance:** 100% Deterministic Sequential Pipeline (No autonomous drift)
            """
        )
        st.caption(
            "☁️ *Cloud Persistence Note: On ephemeral environments (Streamlit Community Cloud), SQLite files "
            "are stored on local ephemeral disks. For permanent enterprise multi-user deployments, the repository "
            "is architected for seamless swap to external PostgreSQL/Cloud SQL without modifying presentation logic.*"
        )

    if filtered_records:
        st.markdown("---")
        st.markdown("#### 🕒 Recent Verification Activity")
        st.caption(f"Showing {len(filtered_records)} verification event(s) matching filter:")

        activity_data = []
        for r in filtered_records:
            source_badge = "⚡ Demo" if r.source == "BENCHMARK_DEMO" else "📤 Upload"
            primary_short = r.primary_reason
            if len(r.all_decision_reasons) > 1:
                primary_short = f"[{len(r.all_decision_reasons)} Issues] {r.primary_reason}"

            activity_data.append(
                {
                    "Timestamp (Dhaka)": r.timestamp_dhaka,
                    "Supplier": r.supplier_name,
                    "Document Name": r.document_name,
                    "Quotation #": r.quotation_no,
                    "PR Item": r.matched_pr_item or "N/A",
                    "Decision": r.final_decision,
                    "Primary Reason": primary_short,
                    "Source": source_badge,
                    "Latency (ms)": f"{r.processing_time_ms:.1f}",
                }
            )
        st.dataframe(pd.DataFrame(activity_data), use_container_width=True, hide_index=True)

        # Excel Download Option on Dashboard
        st.markdown("#### 📥 Export Audit Records")
        st.caption("Download the complete multi-worksheet audit ledger for executive review or ERP integration.")
        excel_bytes = audit_repo.generate_excel_export(filtered_records)
        st.download_button(
            label="📊 Download Filtered Audit Ledger (Excel .xlsx)",
            data=excel_bytes,
            file_name=f"supplier_audit_ledger_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.info("ℹ️ No verification activity recorded for the selected filter period.")



# ==============================================================================
# SECTION 2: DOCUMENT VERIFICATION (UPLOAD & RUN)
# ==============================================================================
elif nav_choice == "🔍 Document Verification":
    st.subheader("Document Verification & Ingestion")
    st.caption("Upload supplier quotation PDFs or execute the benchmark demo.")

    tab_upload, tab_demo = st.tabs(["📤 Upload PDF Quotations", "⚡ One-Click 10-Pack Benchmark Demo"])

    # --- TAB 1: Upload ---
    with tab_upload:
        st.markdown("#### Upload Supplier Quotations")
        uploaded_files = st.file_uploader(
            "Select one or more PDF supplier quotation packs (max 20 MB each)",
            type=["pdf"],
            accept_multiple_files=True,
            help="Files are processed strictly in an isolated temporary sandbox and cleaned up immediately.",
        )

        col_start, col_clear = st.columns([1, 4])
        with col_start:
            start_btn = st.button("🚀 Verify Uploaded Documents", type="primary", use_container_width=True)
        with col_clear:
            if st.button("Clear Results"):
                st.session_state["live_reports"] = []
                st.session_state["is_demo_run"] = False
                st.rerun()

        if start_btn:
            if not uploaded_files:
                st.warning("Please upload at least one PDF quotation file before starting verification.")
            else:
                progress_bar = st.progress(0, text="Initializing verification engine...")
                status_box = st.empty()

                temp_dir = Path(tempfile.mkdtemp(prefix="bi_ai_uploads_"))
                temp_paths = []
                valid_files = []

                # Step 1: File Validation
                for uf in uploaded_files:
                    is_valid, err_msg = validate_uploaded_pdf(uf.name, uf.size)
                    if not is_valid:
                        st.error(f"❌ {err_msg}")
                    else:
                        saved_path = save_uploaded_stream_to_temp(uf, temp_dir)
                        temp_paths.append(saved_path)
                        valid_files.append(saved_path)

                if valid_files:
                    try:
                        engine = DecisionEngine(pr_path=pr_path_input)
                        batch_reports = []
                        total = len(valid_files)

                        for idx, f_path in enumerate(valid_files):
                            progress_pct = (idx + 1) / total
                            status_box.markdown(f"**Verifying document ({idx + 1}/{total}):** `{f_path.name}`")
                            progress_bar.progress(progress_pct)

                            rep = engine.verify_document(f_path)
                            batch_reports.append(rep)

                        audit_repo.record_batch(batch_reports, source="UPLOAD")
                        st.session_state["live_reports"] = batch_reports
                        st.session_state["last_processed_time"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                        st.session_state["is_demo_run"] = False

                        status_box.success(f"✅ Successfully verified {len(batch_reports)} document(s)!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Execution Error: {e}")
                    finally:
                        cleanup_directory(temp_dir)

    # --- TAB 2: One-Click Demo ---
    with tab_demo:
        st.markdown("#### Evaluate All 10 Pre-Supplied Sample Packs")
        st.markdown(
            """
            This executes the full sequential verification pipeline against the 10 sample PDF packs in `sample_data/`:
            - `supplier-pack-01.pdf` through `supplier-pack-10.pdf`
            - Purchase Request: `sample_data/purchase-request.csv`
            - Company Rules: `sample_data/company-rules.md`
            """
        )

        if st.button("⚡ Run 10-Pack Benchmark Demo", type="primary"):
            sample_dir = Path("sample_data")
            pdf_files = sorted(sample_dir.glob("supplier-pack-*.pdf"), key=lambda p: p.name.lower())

            if not pdf_files:
                st.error("Could not find sample files in `sample_data/` directory.")
            else:
                progress_bar = st.progress(0, text="Executing benchmark verification...")
                status_box = st.empty()

                engine = DecisionEngine(pr_path=pr_path_input)
                batch_reports = []
                total = len(pdf_files)

                for idx, p_file in enumerate(pdf_files):
                    progress_pct = (idx + 1) / total
                    status_box.markdown(f"**Auditing ({idx + 1}/{total}):** `{p_file.name}`")
                    progress_bar.progress(progress_pct)

                    rep = engine.verify_document(p_file)
                    batch_reports.append(rep)

                audit_repo.record_batch(batch_reports, source="BENCHMARK_DEMO")
                st.session_state["live_reports"] = batch_reports
                st.session_state["last_processed_time"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                st.session_state["is_demo_run"] = True

                status_box.success("✅ All 10 sample packs processed successfully!")
                time.sleep(0.5)
                st.rerun()

    # --------------------------------------------------------------------------
    # ON-SCREEN HUMAN-FRIENDLY VERIFICATION RESULTS
    # --------------------------------------------------------------------------
    if st.session_state["live_reports"]:
        reports: List[DocumentVerificationReport] = st.session_state["live_reports"]
        st.markdown("---")

        # 1. Multi-Document Selector & Batch Overview
        if len(reports) > 1:
            st.markdown("### 📋 Verification Summary")
            c_tot, c_app, c_rej, c_rev = st.columns(4)
            app_count = sum(1 for r in reports if r.final_decision == DecisionEnum.APPROVE)
            rej_count = sum(1 for r in reports if r.final_decision == DecisionEnum.REJECT)
            rev_count = sum(1 for r in reports if r.final_decision == DecisionEnum.NEEDS_HUMAN_REVIEW)

            with c_tot:
                st.metric("Total Quotations", len(reports))
            with c_app:
                st.metric("🟢 Approved", app_count)
            with c_rej:
                st.metric("🔴 Rejected", rej_count)
            with c_rev:
                st.metric("🟡 Needs Review", rev_count)

            doc_options = [
                f"{idx + 1}. [{r.final_decision.value}] {r.supplier_name} — {r.document_name}"
                for idx, r in enumerate(reports)
            ]
            current_idx = min(st.session_state.get("selected_doc_index", 0), len(reports) - 1)
            selected_label = st.selectbox(
                "Select Quotation to Inspect On-Screen:",
                options=doc_options,
                index=current_idx,
                help="Choose which supplier quotation to review in detail directly below.",
            )
            selected_idx = doc_options.index(selected_label)
            st.session_state["selected_doc_index"] = selected_idx
            rep = reports[selected_idx]
        else:
            rep = reports[0]

        theme = get_decision_color_theme(rep.final_decision)
        badge_class = {
            DecisionEnum.APPROVE: "badge-approve",
            DecisionEnum.REJECT: "badge-reject",
            DecisionEnum.NEEDS_HUMAN_REVIEW: "badge-review",
        }.get(rep.final_decision, "badge-review")

        # 2. Prominent Decision Hero Card (Aggregating all contributing reasons)
        all_reasons = get_all_decision_reasons(rep)
        if len(all_reasons) > 1:
            reasons_html = f"<strong>Contributing Decision Findings ({len(all_reasons)} Issues):</strong><ul style='margin: 0.35rem 0 0 1.2rem; padding: 0;'>"
            for r_text in all_reasons:
                reasons_html += f"<li style='margin-bottom: 0.25rem;'>{r_text}</li>"
            reasons_html += "</ul>"
        else:
            reasons_html = f"<strong>Decision Finding:</strong> {all_reasons[0]}"

        st.markdown(
            f"""
            <div style="background: {theme['bg']}; border: 1.5px solid {theme['border']}; border-left: 8px solid {theme['border']}; border-radius: 8px; padding: 1.4rem; margin-top: 1rem; margin-bottom: 1.25rem;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div style="font-size: 0.85rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">
                            Document Verification Result
                        </div>
                        <h2 style="margin: 0.2rem 0 0.4rem 0; color: #0f172a; font-size: 1.5rem; font-weight: 800;">
                            {rep.supplier_name}
                        </h2>
                        <div style="color: #475569; font-size: 0.95rem;">
                            <strong>Quotation No:</strong> <code>{rep.quotation_no}</code> • 
                            <strong>File:</strong> <code>{rep.document_name}</code> • 
                            <strong>Target Item:</strong> <code>{rep.matched_pr_item or 'N/A'}</code>
                        </div>
                    </div>
                    <div>
                        <span class="{badge_class}" style="font-size: 1.15rem; padding: 0.45rem 1rem;">
                            {theme['icon']} {rep.final_decision.value}
                        </span>
                    </div>
                </div>
                <hr style="border: 0; border-top: 1px solid {theme['border']}; margin: 0.9rem 0; opacity: 0.5;">
                <div style="font-size: 1.02rem; color: #1e293b; line-height: 1.45;">
                    {reasons_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Dedicated Financial Discrepancies Box (if arithmetic mismatches exist)
        math_discrepancies = get_financial_discrepancies(rep)
        if math_discrepancies:
            st.markdown(
                """
                <div style="background: #fff1f2; border: 1px solid #fda4af; border-left: 5px solid #e11d48; border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 1.25rem;">
                    <h4 style="margin: 0 0 0.4rem 0; color: #9f1239; font-size: 1.05rem;">
                        ⚠️ Financial & Arithmetic Discrepancy Comparison
                    </h4>
                    <p style="margin: 0 0 0.6rem 0; color: #4c0519; font-size: 0.9rem;">
                        Mathematical inconsistency detected between supplier-quoted amounts and system-verified calculations.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            df_discrepancies = pd.DataFrame([
                {
                    "Component": d["Component"],
                    "Supplier-Quoted Amount": d["Quoted Amount"],
                    "System-Recalculated Amount": d["Recalculated Amount"],
                    "Absolute Difference": d["Difference"],
                    "Calculation Explanation": d["Explanation"],
                }
                for d in math_discrepancies
            ])
            st.dataframe(df_discrepancies, use_container_width=True, hide_index=True)

        # 3. Next-Step Guidance for Procurement Manager
        guidance = get_next_step_guidance(rep.final_decision)
        if guidance["alert_type"] == "success":
            st.success(f"### {guidance['title']}\n\n{guidance['message']}\n\n*{guidance['note']}*")
        elif guidance["alert_type"] == "error":
            st.error(f"### {guidance['title']}\n\n{guidance['message']}\n\n*{guidance['note']}*")
        else:
            st.warning(f"### {guidance['title']}\n\n{guidance['message']}\n\n*{guidance['note']}*")

        # 4. Plain-Language Findings Table
        st.markdown("### 📋 Verification Checks Summary")
        st.caption("Plain-language results for all company compliance criteria and purchase request alignments.")
        findings = build_plain_language_findings(rep)
        df_findings = pd.DataFrame([
            {"Check": f["Check"], "Result": f["Result"], "Explanation": f["Explanation"]}
            for f in findings
        ])
        st.dataframe(df_findings, use_container_width=True, hide_index=True)

        # 5. Extracted Quotation Details Section
        st.markdown("### 📄 Extracted Quotation Details")
        st.caption("Key commercial and contractual figures extracted from the supplier quotation (with missing/ambiguous fields highlighted).")
        summary_fields = get_extracted_summary_fields(rep)

        col_com, col_con = st.columns(2)
        with col_com:
            st.markdown("#### 💰 Commercial & Financial Breakdown")
            st.markdown(
                f"""
                - **Item Code & Description:** {summary_fields.get('Item code & description', 'N/A')}
                - **Quoted Quantity & Unit:** `{summary_fields.get('Quantity & unit', 'N/A')}`
                - **Quoted Unit Price:** `{summary_fields.get('Unit price', 'N/A')}`
                - **Quoted Line Amount:** `{summary_fields.get('Quoted line amount', 'N/A')}`
                - **Recalculated Line Amount:** `{summary_fields.get('Recalculated line amount', 'N/A')}`
                - **Subtotal:** `{summary_fields.get('Subtotal', 'N/A')}`
                - **VAT (15%):** `{summary_fields.get('VAT', 'N/A')}`
                - **Grand Total Amount:** **`{summary_fields.get('Grand total', 'N/A')}`**
                """
            )
        with col_con:
            st.markdown("#### 📜 Terms, Schedule & Compliance")
            st.markdown(
                f"""
                - **Advance Payment Terms:** `{summary_fields.get('Advance payment', 'N/A')}`
                - **Credit / Payment Terms:** `{summary_fields.get('Credit / payment terms', 'N/A')}`
                - **Delivery Period:** `{summary_fields.get('Delivery period', 'N/A')}`
                - **Late-Delivery Penalty:** `{summary_fields.get('Late-delivery penalty', 'N/A')}`
                - **Quotation Validity:** `{summary_fields.get('Quotation validity', 'N/A')}`
                - **Tax Registration:** `{summary_fields.get('TIN / BIN', 'N/A')}`
                """
            )

        # 6. Expandable Evidence Section (Distinguishing Source Verification vs Field Interpretation)
        with st.expander("🔍 View Supporting Evidence & Grounded Citations", expanded=False):
            st.caption(
                "Verbatim citations extracted from the original PDF with page numbers, layout verification, "
                "and explicit field interpretation reliability."
            )
            evidence_items = get_evidence_traceability_items(rep)
            if evidence_items:
                evidence_df = pd.DataFrame([
                    {
                        "Field / Clause": it["Field"],
                        "Extracted Value": it["Extracted Value"],
                        "Verbatim PDF Quote": f'"{it["Verbatim PDF Quote"]}"' if it["Verbatim PDF Quote"] else "N/A",
                        "Page": f"Page {it['Page Number']}",
                        "Source Text on Page": "✅ Verified" if it.get("Source Verified") else "⚠️ Unverified",
                        "Interpretation Status": it.get("Interpretation Status", "EXTRACTED"),
                    }
                    for it in evidence_items
                ])
                st.dataframe(evidence_df, use_container_width=True, hide_index=True)
            else:
                st.info("No supporting evidence items recorded.")

        # 7. Secondary Export & Downloads Section
        st.markdown("---")
        st.markdown("#### 📥 Export Audit Reports")
        st.caption("Download reports for offline record keeping or ERP integration (optional secondary option).")

        # Individual report download
        indiv_xlsx = generate_individual_excel_report(rep)
        indiv_md = generate_individual_markdown_report(rep)
        indiv_json = generate_individual_json_report(rep)

        down_col1, down_col2, down_col3 = st.columns(3)
        with down_col1:
            st.download_button(
                label="📊 Download This Report (Excel)",
                data=indiv_xlsx,
                file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with down_col2:
            st.download_button(
                label="📄 Download This Report (Markdown)",
                data=indiv_md,
                file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}_{time.strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with down_col3:
            st.download_button(
                label="📊 Download This Report (JSON)",
                data=indiv_json,
                file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

        # Batch summary download if multiple documents
        if len(reports) > 1:
            st.markdown("##### Batch Exports (All Verified Documents)")
            b_csv = generate_batch_csv_summary(reports)
            b_md = generate_batch_markdown_summary(reports)
            b_json = generate_batch_json_summary(reports)
            b_xlsx = generate_batch_excel_summary(reports)

            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.download_button(
                    label="📄 Batch Summary (CSV)",
                    data=b_csv,
                    file_name=f"batch_verification_summary_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    label="📝 Batch Report (Markdown)",
                    data=b_md,
                    file_name=f"batch_verification_report_{time.strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with d3:
                st.download_button(
                    label="📊 Batch Data (JSON)",
                    data=b_json,
                    file_name=f"batch_verification_data_{time.strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with d4:
                st.download_button(
                    label="📈 Batch Workbook (Excel)",
                    data=b_xlsx,
                    file_name=f"batch_verification_workbook_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


# ==============================================================================
# SECTION 3: DECISION RESULTS
# ==============================================================================
elif nav_choice == "📋 Decision Results":
    st.subheader("Verification Decision Ledger")
    st.caption("Consolidated compliance decisions for all processed supplier documents.")

    reports: List[DocumentVerificationReport] = st.session_state["live_reports"]

    if not reports:
        st.info("No documents have been verified yet. Run verification in **Document Verification** to view decisions.")
    else:
        for idx, rep in enumerate(reports):
            theme = get_decision_color_theme(rep.final_decision)
            badge_class = {
                DecisionEnum.APPROVE: "badge-approve",
                DecisionEnum.REJECT: "badge-reject",
                DecisionEnum.NEEDS_HUMAN_REVIEW: "badge-review",
            }.get(rep.final_decision, "badge-review")

            rejection_count = sum(1 for r in rep.triggered_rules if r.category.value == "REJECT")
            review_count = sum(1 for r in rep.triggered_rules if r.category.value != "REJECT")

            with st.container():
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e2e8f0; border-left: 5px solid {theme['border']}; border-radius: 6px; padding: 1.1rem; margin-bottom: 0.9rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 1.1rem; font-weight: 700; color: #0f172a;">{rep.supplier_name}</span>
                                <span style="color: #64748b; font-size: 0.9rem; margin-left: 0.5rem;">({rep.document_name})</span>
                            </div>
                            <div>
                                <span class="{badge_class}">{theme['icon']} {rep.final_decision.value}</span>
                            </div>
                        </div>
                        <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #334155;">
                            <strong>Primary Finding:</strong> {rep.primary_reason}
                        </div>
                        <div style="margin-top: 0.4rem; font-size: 0.85rem; color: #64748b;">
                            Quotation No: <code>{rep.quotation_no}</code> • 
                            Matched PR Item: <code>{rep.matched_pr_item or 'N/A'}</code> • 
                            Rejection Findings: <strong>{rejection_count}</strong> • 
                            Review Triggers: <strong>{review_count}</strong> • 
                            Latency: <code>{rep.processing_time_ms:.1f} ms</code>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# SECTION 4: AUDIT VIEWER (DEEP AUDIT INSPECTOR)
# ==============================================================================
elif nav_choice == "🔬 Deep Audit Inspector":
    st.subheader("Deep Audit Inspector")
    st.caption("Inspect grounded evidence, line-by-line calculations, and full business rule evaluations.")

    reports: List[DocumentVerificationReport] = st.session_state["live_reports"]

    if not reports:
        st.info("No documents are available to inspect. Run verification first to examine detailed audit trails.")
    else:
        doc_names = [f"{idx + 1}. {r.supplier_name} ({r.document_name})" for idx, r in enumerate(reports)]
        selected_label = st.selectbox(
            "Select Supplier Quotation to Audit:",
            options=doc_names,
            index=min(st.session_state["selected_doc_index"], len(doc_names) - 1),
        )
        selected_idx = doc_names.index(selected_label)
        st.session_state["selected_doc_index"] = selected_idx
        rep = reports[selected_idx]

        theme = get_decision_color_theme(rep.final_decision)
        badge_class = {
            DecisionEnum.APPROVE: "badge-approve",
            DecisionEnum.REJECT: "badge-reject",
            DecisionEnum.NEEDS_HUMAN_REVIEW: "badge-review",
        }.get(rep.final_decision, "badge-review")

        # Top Banner
        st.markdown(
            f"""
            <div style="background: {theme['bg']}; border: 1px solid {theme['border']}; border-radius: 6px; padding: 1.25rem; margin-bottom: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin: 0; color: {theme['text']}; font-size: 1.35rem;">
                            {theme['icon']} Decision: {rep.final_decision.value}
                        </h2>
                        <p style="margin: 0.3rem 0 0 0; color: #334155; font-size: 0.95rem;">
                            <strong>Supplier:</strong> {rep.supplier_name} • <strong>Quotation #:</strong> {rep.quotation_no} • <strong>File:</strong> <code>{rep.document_name}</code>
                        </p>
                    </div>
                    <div>
                        <span class="{badge_class}">{rep.final_decision.value}</span>
                    </div>
                </div>
                <div style="margin-top: 0.75rem; color: #1e293b; font-size: 0.92rem;">
                    <strong>Finding:</strong> {rep.primary_reason}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_rules, tab_pr, tab_math, tab_terms, tab_download = st.tabs(
            [
                "⚖️ Company Business Rules",
                "🎯 Purchase Request Alignment",
                "🧮 Financial & Arithmetic Audit",
                "📜 Contractual Terms & Registration",
                "💾 Download Individual Report",
            ]
        )

        # TAB 1: Company Rules
        with tab_rules:
            st.markdown("#### Full Company Rules Matrix (`company-rules.md`)")
            rule_data = []
            for r in rep.all_evaluated_rules:
                status_str = "PASS" if r.status == RuleStatus.PASS else ("FAIL" if r.status == RuleStatus.FAIL else r.status.value)
                rule_data.append(
                    {
                        "Rule ID": r.rule_id,
                        "Rule Name": r.rule_name,
                        "Category": r.category.value,
                        "Status": status_str,
                        "Actual Value": r.actual_value or "N/A",
                        "Expected Condition": r.expected_condition or "N/A",
                        "Evidence Quote": f"\"{r.evidence_quote}\"" if r.evidence_quote else "N/A",
                        "Page": r.page_number or 1,
                    }
                )
            st.dataframe(pd.DataFrame(rule_data), use_container_width=True, hide_index=True)

            if rep.supporting_evidence_quotes:
                st.markdown("#### Verified Document Evidence Provenance")
                for q in rep.supporting_evidence_quotes:
                    st.markdown(f"<div class='evidence-box'>{q}</div>", unsafe_allow_html=True)

        # TAB 2: PR Alignment
        with tab_pr:
            st.markdown("#### Comparison Against Purchase Request (`PR-2026-114`)")
            if rep.pr_comparison and rep.pr_comparison.matched_items:
                pr_items_data = []
                for item in rep.pr_comparison.matched_items:
                    align_status = "Compliant"
                    if item.price_exceeds_rejection_ceiling:
                        align_status = "🔴 Price Exceeds +3% Ceiling"
                    elif item.price_is_within_review_band:
                        align_status = "🟡 Price in Review Band (<= +3%)"
                    elif not item.quantity_within_tolerance:
                        align_status = "🟡 Qty Variance (> 5%)"

                    pr_items_data.append(
                        {
                            "Item Code": item.item_code,
                            "PR Requested Qty": f"{item.requested_quantity:,.0f} {item.pr_unit}",
                            "Quoted Qty": f"{item.quoted_quantity:,.0f} {item.quoted_unit}",
                            "Qty Variance": f"{item.quantity_variance_pct:+,.2f}%",
                            "PR Max Price": f"{item.max_unit_price:,.2f} BDT",
                            "Quoted Price": f"{item.quoted_unit_price:,.2f} BDT",
                            "Price Variance": f"{item.price_variance_pct:+,.2f}%",
                            "Reject Ceiling (+3%)": f"{item.price_rejection_ceiling:,.2f} BDT",
                            "Alignment Status": align_status,
                        }
                    )
                st.dataframe(pd.DataFrame(pr_items_data), use_container_width=True, hide_index=True)
            else:
                st.warning("No matched PR line items found for this quotation.")

        # TAB 3: Arithmetic & Math
        with tab_math:
            st.markdown("#### Mathematical & Financial Verification")
            math = rep.arithmetic_audit

            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.markdown(f"**Line Math:** {'✅ Exact Match' if math.line_calculations_match else '❌ Discrepancy'}")
                st.markdown(f"**Subtotal Sum:** {'✅ Exact Match' if math.subtotal_matches_lines else '❌ Discrepancy'}")
            with m_col2:
                st.markdown(f"**15% VAT Math:** {'✅ Exact Match' if math.vat_matches_subtotal_15pct else '❌ Discrepancy'}")
                st.markdown(f"**Total Sum:** {'✅ Exact Match' if math.total_matches_sum else '❌ Discrepancy'}")
            with m_col3:
                st.markdown(f"**VAT Separated:** {'✅ Yes (15%)' if math.vat_shown_separately else '⚠️ No / Bundled'}")

            if math.line_checks:
                st.markdown("##### Line Item Calculation Breakdown")
                line_data = []
                for lc in math.line_checks:
                    line_data.append(
                        {
                            "Item Code": lc.item_code,
                            "Quantity": f"{lc.quantity:,.0f}",
                            "Unit Price": f"{lc.unit_price:,.2f} BDT",
                            "Calculated Amount": f"{lc.calculated_amount:,.2f} BDT",
                            "Quoted Amount": f"{lc.quoted_amount:,.2f} BDT" if lc.quoted_amount else "N/A",
                            "Difference": f"{lc.difference:,.2f} BDT",
                            "Match": "✅ PASS" if lc.matches else "❌ DISCREPANCY",
                        }
                    )
                st.dataframe(pd.DataFrame(line_data), use_container_width=True, hide_index=True)

            if math.discrepancies:
                st.error("⚠️ Arithmetic Discrepancies Detected:")
                for d in math.discrepancies:
                    st.write(f"- **{d.component}:** Expected `{d.expected_value:,.2f}` BDT, Quoted `{d.quoted_value:,.2f}` BDT. Discrepancy: `{d.discrepancy_amount:,.2f}` BDT. Quote: \"{d.evidence_quote}\"")

        # TAB 4: Contractual Terms
        with tab_terms:
            st.markdown("#### Commercial Terms & Tax Registration Audit")
            st.markdown(
                f"""
                - **Document SHA-256 Hash:** `<code>{rep.document_hash}</code>`
                - **Rejection Confirmed:** `{'Yes' if rep.rejection_confirmed else 'No'}`
                - **Processing Latency:** `{rep.processing_time_ms:.1f} ms`
                """
            )

            if rep.extraction_uncertainties:
                st.markdown("##### Extraction Uncertainties / Discrepancies")
                for u in rep.extraction_uncertainties:
                    st.warning(f"**{u.field_name}** ({u.issue_type}): {u.details}")

        # TAB 5: Download Individual Report
        with tab_download:
            st.markdown("#### Export Individual Audit Report")
            ind_xlsx = generate_individual_excel_report(rep)
            ind_md = generate_individual_markdown_report(rep)
            ind_json = generate_individual_json_report(rep)

            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.download_button(
                    label="📊 Download Excel Audit Report",
                    data=ind_xlsx,
                    file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with col_d2:
                st.download_button(
                    label="📝 Download Markdown Audit Report",
                    data=ind_md,
                    file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_d3:
                st.download_button(
                    label="📊 Download JSON Audit Report",
                    data=ind_json,
                    file_name=f"audit_report_{rep.document_name.replace('.pdf', '')}.json",
                    mime="application/json",
                    use_container_width=True,
                )


# ==============================================================================
# SECTION 5: BENCHMARK & EVALUATION
# ==============================================================================
elif nav_choice == "📈 Benchmark & Evaluation":
    st.subheader("Benchmark & System Evaluation (10 Sample Packs)")
    st.caption("Standardized evaluation against the official recruitment assessment sample dataset.")

    # Load pre-generated benchmark results
    bench_data = load_benchmark_report_json()
    bench_md = load_benchmark_report_markdown()

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 Re-run Live Benchmark Suite", type="primary", use_container_width=True):
            with st.spinner("Executing benchmark across all 10 sample supplier packs..."):
                benchmark = EvaluationBenchmark()
                summary, results, batch_reports = benchmark.run_benchmark("sample_data")
                benchmark.save_reports(summary, results, "reports")
                st.success("Benchmark completed and reports refreshed!")
                time.sleep(0.5)
                st.rerun()

    if not bench_data:
        st.warning("Benchmark summary not found in `reports/evaluation_summary.json`. Click 'Re-run Live Benchmark Suite' above to generate it.")
    else:
        summary = bench_data["benchmark_summary"]
        doc_evals = bench_data["document_evaluations"]

        # KPI Metrics Row
        e1, e2, e3, e4, e5 = st.columns(5)
        with e1:
            st.metric("Decision Accuracy", f"{summary['accuracy_percentage']:.1f}%", delta="Target: 100%")
        with e2:
            st.metric("False Approvals", f"{summary['false_approvals']}", delta="Zero Tolerance", delta_color="inverse")
        with e3:
            st.metric("False Rejections", f"{summary['false_rejections']}", delta="0")
        with e4:
            st.metric("Extraction Failures", f"{summary['extraction_failure_count']}", delta="0")
        with e5:
            st.metric("Mean Latency", f"{summary['mean_processing_time_ms']:.1f} ms", delta="< 2000 ms")

        st.markdown("---")
        st.markdown("#### Sample Dataset Benchmark Ledger")

        eval_table = []
        for d in doc_evals:
            status_symbol = "✅ PASS" if d["decision_correct"] else "❌ FAIL"
            eval_table.append(
                {
                    "Document": d["document_name"],
                    "Supplier": d["supplier_name"],
                    "Item": d["matched_item"] or "N/A",
                    "Expected": d["expected_decision"],
                    "Actual": d["actual_decision"],
                    "Status": status_symbol,
                    "Latency (ms)": f"{d['processing_time_ms']:.1f}",
                    "Ground Truth Notes": d["notes"],
                }
            )
        st.dataframe(pd.DataFrame(eval_table), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 📥 Download Benchmark Reports")
        bench_xlsx = generate_benchmark_excel_report(bench_data)
        b1, b2, b3 = st.columns(3)
        with b1:
            st.download_button(
                "📊 Download Benchmark Report (Excel)",
                data=bench_xlsx,
                file_name="benchmark_audit_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with b2:
            if bench_md:
                st.download_button(
                    "📝 Download Full Benchmark Report (Markdown)",
                    data=bench_md,
                    file_name="benchmark_audit_summary.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
        with b3:
            st.download_button(
                "📊 Download Benchmark Data (JSON)",
                data=json.dumps(bench_data, indent=2),
                file_name="benchmark_evaluation_summary.json",
                mime="application/json",
                use_container_width=True,
            )
