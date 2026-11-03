from decimal import Decimal
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class VerificationSettings(BaseSettings):
    """Configuration settings and business rule thresholds."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Directories and file locations
    base_dir: Path = BASE_DIR
    data_dir: Path = Field(default_factory=lambda: BASE_DIR / "sample_data")
    pr_file_path: Path = Field(
        default_factory=lambda: BASE_DIR / "sample_data" / "purchase-request.csv"
    )
    company_rules_path: Path = Field(
        default_factory=lambda: BASE_DIR / "sample_data" / "company-rules.md"
    )
    reports_dir: Path = Field(default_factory=lambda: BASE_DIR / "reports")

    # LLM Settings
    llm_provider: str = Field(default="gemini", description="'gemini', 'openai', or 'deterministic'")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    llm_model: str = Field(default="gemini-1.5-flash", description="Model name")

    # Rule Thresholds (Strictly Configurable & using Decimal for numerical precision)
    price_rejection_threshold: Decimal = Field(
        default=Decimal("0.03"),
        description="Reject if price > max_price * (1 + threshold) (3%)",
    )
    quantity_tolerance_threshold: Decimal = Field(
        default=Decimal("0.05"),
        description="Review if |qty - requested_qty| / requested_qty > threshold (5%)",
    )
    max_advance_payment_pct: Decimal = Field(
        default=Decimal("20.0"),
        description="Reject if advance payment > 20%",
    )
    min_late_penalty_pct_per_week: Decimal = Field(
        default=Decimal("0.5"),
        description="Penalty must be at least 0.5% of order value per week of delay",
    )
    max_delivery_days: int = Field(
        default=45,
        description="Reject if delivery promised > 45 days after PO",
    )
    min_delivery_days_review: int = Field(
        default=31,
        description="Review if delivery promised between 31 and 45 days",
    )
    min_credit_days_review: int = Field(
        default=30,
        description="Review if credit payment term < 30 days after delivery",
    )
    max_credit_days_review: int = Field(
        default=60,
        description="Review if credit payment term > 60 days after delivery",
    )
    min_quotation_validity_days: int = Field(
        default=30,
        description="Review if quotation valid for less than 30 days",
    )
    standard_vat_rate: Decimal = Field(
        default=Decimal("0.15"),
        description="VAT must be shown separately at 15%",
    )
    currency_tolerance: Decimal = Field(
        default=Decimal("0.01"),
        description="Allowed discrepancy in financial arithmetic (0.01 BDT)",
    )
    extraction_confidence_threshold: float = Field(
        default=0.85,
        description="Confidence required for confirmed rejection (below triggers human review)",
    )


# Singleton settings instance
settings = VerificationSettings()

