import csv
from decimal import Decimal
from pathlib import Path
from typing import Dict
from src.interfaces.base import BasePRLoader
from src.models.schemas import PurchaseRequest, PurchaseRequestItem


class PurchaseRequestLoader(BasePRLoader):
    """Loads and validates the benchmark Purchase Request from CSV."""

    def load(self, csv_path: Path) -> PurchaseRequest:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Purchase request CSV not found at: {path}")

        items: Dict[str, PurchaseRequestItem] = {}
        pr_number: str = ""

        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                current_pr = row["PR number"].strip()
                if not pr_number:
                    pr_number = current_pr

                item_code = row["Item"].strip()
                desc = row["Description"].strip()
                unit = row["Unit"].strip()
                qty_raw = row["Quantity requested"].strip().replace(",", "")
                price_raw = row["Maximum unit price (BDT)"].strip().replace(",", "")

                item = PurchaseRequestItem(
                    item_code=item_code,
                    description=desc,
                    unit=unit,
                    quantity_requested=Decimal(qty_raw),
                    maximum_unit_price=Decimal(price_raw),
                )
                items[item_code] = item

        if not items:
            raise ValueError(f"No line items found in purchase request CSV: {path}")

        return PurchaseRequest(pr_number=pr_number, items=items)


def load_purchase_request(csv_path: Path | str) -> PurchaseRequest:
    """Helper function to load Purchase Request from CSV."""
    return PurchaseRequestLoader().load(Path(csv_path))


