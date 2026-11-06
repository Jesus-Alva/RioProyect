"""Genera facturas PDF simuladas para pruebas locales; no son CFDI."""

import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.branches import BRANCHES
from backend.scripts.seed_inventory import CATALOG_PATH, load_inventory_catalog


INVOICE_COUNT_PER_BRANCH = 5
TEST_SUPPLIER = "Proveedor Ficticio de Limpieza, S.A. de C.V."
TEST_CUSTOMER = "Distribuidora Rio Claro (empresa ficticia)"
DISCLAIMER = "DOCUMENTO SIMULADO PARA PRUEBAS - NO VALIDO COMO CFDI"


@dataclass(frozen=True)
class InvoiceLine:
    sku: str
    product: str
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class TestInvoice:
    branch: str
    invoice_number: int
    invoice_date: date
    folio: str
    lines: tuple[InvoiceLine, ...]

    @property
    def subtotal(self) -> Decimal:
        return sum(
            (line.line_total for line in self.lines),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def tax(self) -> Decimal:
        return (self.subtotal * Decimal("0.16")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax


def build_test_invoices(
    generated_on: date | None = None,
    catalog_path: str | Path = CATALOG_PATH,
) -> list[TestInvoice]:
    today = generated_on or date.today()
    products = load_inventory_catalog(catalog_path)
    randomizer = random.Random(20261106)
    invoices = []

    for branch_index, branch in enumerate(BRANCHES):
        for invoice_number in range(1, INVOICE_COUNT_PER_BRANCH + 1):
            lines = tuple(
                InvoiceLine(
                    sku=product["sku"],
                    product=product["producto"],
                    quantity=randomizer.randint(1, 8),
                    unit_price=Decimal(product["precio_unitario_prueba_mxn"]),
                )
                for product in products
            )
            invoice_date = today - timedelta(
                days=branch_index * INVOICE_COUNT_PER_BRANCH + invoice_number - 1
            )
            folio = (
                f"SIM-{today:%Y%m%d}-{branch.upper()[:3]}-{invoice_number:02d}"
            )
            invoices.append(
                TestInvoice(
                    branch=branch,
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    folio=folio,
                    lines=lines,
                )
            )
    return invoices


def _escape_pdf_text(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("cp1252", errors="replace")


def _text_command(x: int, y: int, size: int, text: str) -> bytes:
    prefix = f"BT /F1 {size} Tf {x} {y} Td (".encode("ascii")
    return prefix + _escape_pdf_text(text) + b") Tj ET\n"


def render_invoice_pdf(invoice: TestInvoice) -> bytes:
    commands = bytearray()
    commands.extend(_text_command(50, 790, 15, "FACTURA DE PRUEBA"))
    commands.extend(_text_command(50, 770, 9, DISCLAIMER))
    commands.extend(_text_command(50, 742, 10, f"Proveedor: {TEST_SUPPLIER}"))
    commands.extend(_text_command(50, 725, 10, f"Cliente: {TEST_CUSTOMER}"))
    commands.extend(_text_command(50, 708, 10, f"Sucursal: {invoice.branch}"))
    commands.extend(_text_command(50, 691, 10, f"Folio: {invoice.folio}"))
    commands.extend(
        _text_command(50, 674, 10, f"Fecha: {invoice.invoice_date:%Y-%m-%d}")
    )
    commands.extend(
        _text_command(50, 640, 9, "SKU      PRODUCTO                         CANT.   PRECIO     IMPORTE")
    )
    commands.extend(b"0.2 w 50 633 m 545 633 l S\n")

    y = 614
    for line in invoice.lines:
        row = (
            f"{line.sku}  {line.product[:27]:27} "
            f"{line.quantity:>3}   ${line.unit_price:>7.2f}   "
            f"${line.line_total:>8.2f}"
        )
        commands.extend(_text_command(50, y, 9, row))
        y -= 18

    y -= 8
    commands.extend(_text_command(365, y, 10, f"Subtotal: ${invoice.subtotal:.2f}"))
    y -= 16
    commands.extend(_text_command(365, y, 10, f"IVA prueba (16%): ${invoice.tax:.2f}"))
    y -= 18
    commands.extend(_text_command(365, y, 11, f"TOTAL PRUEBA: ${invoice.total:.2f}"))
    commands.extend(
        _text_command(50, 75, 9, "Precios, cantidades y proveedor ficticios. Solo uso interno de pruebas.")
    )
    commands.extend(_text_command(50, 58, 9, DISCLAIMER))

    stream = bytes(commands)
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"endstream",
    )
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def generate_test_invoices(
    output_directory: str | Path = PROJECT_ROOT / "data" / "invoices",
    generated_on: date | None = None,
    catalog_path: str | Path = CATALOG_PATH,
) -> list[Path]:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    invoices = build_test_invoices(generated_on, catalog_path)
    generated_paths = []
    for invoice in invoices:
        destination = output_path / (
            f"factura_{invoice.branch}_{invoice.invoice_number:02d}.pdf"
        )
        destination.write_bytes(render_invoice_pdf(invoice))
        generated_paths.append(destination)
    return generated_paths


def main() -> int:
    try:
        generated_paths = generate_test_invoices()
    except (OSError, ValueError) as error:
        print(f"Error al generar facturas simuladas: {error}", file=sys.stderr)
        return 1
    print(
        f"{len(generated_paths)} facturas simuladas generadas para "
        f"{len(BRANCHES)} sucursales en data/invoices."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
