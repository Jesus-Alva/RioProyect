"""Canonical file names for uploaded and batch-indexed invoices."""

import hashlib
import os
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Any


def _filename_date(invoice_date: Any) -> str:
    if isinstance(invoice_date, (date, datetime)):
        normalized_date = invoice_date.isoformat()
    else:
        normalized_date = str(invoice_date).strip() if invoice_date is not None else ""
    if normalized_date:
        try:
            return date.fromisoformat(normalized_date[:10]).strftime("%Y%m%d")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _filename_vendor(
    vendor_name: Any, vendor_confidence: float | None
) -> str:
    if (
        not isinstance(vendor_name, str)
        or not vendor_name.strip()
        or vendor_confidence is None
        or vendor_confidence < 0.8
    ):
        return "proveedor-pendiente"
    normalized = unicodedata.normalize("NFKD", vendor_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug[:48].rstrip("-") or "proveedor-pendiente"


def generate_invoice_filename(
    original_filename: str,
    branch: str,
    invoice_date: Any,
    vendor_name: Any,
    vendor_confidence: float | None,
    content_hash: str,
    document_number: int = 1,
) -> str:
    extension = os.path.splitext(original_filename)[1].lower()
    document_id = (
        content_hash
        if document_number == 1
        else hashlib.sha256(
            f"{content_hash}:{document_number}".encode("utf-8")
        ).hexdigest()
    )
    return (
        f"FACTURA_{branch}_{_filename_date(invoice_date)}_"
        f"{_filename_vendor(vendor_name, vendor_confidence)}_"
        f"{document_id}{extension}"
    )
