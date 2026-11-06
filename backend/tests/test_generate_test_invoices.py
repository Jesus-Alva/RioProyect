import tempfile
import unittest
from datetime import date

from backend.app.branches import BRANCHES
from backend.scripts.generate_test_invoices import (
    DISCLAIMER,
    INVOICE_COUNT_PER_BRANCH,
    build_test_invoices,
    generate_test_invoices,
    render_invoice_pdf,
)


class GenerateTestInvoicesTests(unittest.TestCase):
    def test_builds_five_simulated_invoices_per_branch_from_cleaning_catalog(self):
        invoices = build_test_invoices(generated_on=date(2026, 11, 6))

        self.assertEqual(len(invoices), len(BRANCHES) * INVOICE_COUNT_PER_BRANCH)
        self.assertEqual({invoice.branch for invoice in invoices}, set(BRANCHES))
        for invoice in invoices:
            self.assertEqual(len(invoice.lines), 3)
            self.assertEqual(
                {line.sku for line in invoice.lines},
                {"PROD-001", "PROD-002", "PROD-003"},
            )
            self.assertGreater(invoice.total, invoice.subtotal)

    def test_generates_valid_pdf_files_with_simulation_disclaimer(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = generate_test_invoices(
                output_directory=temporary_directory,
                generated_on=date(2026, 11, 6),
            )

            self.assertEqual(len(paths), 25)
            self.assertTrue(all(path.is_file() for path in paths))
            self.assertEqual(
                {path.name for path in paths},
                {
                    f"factura_{branch}_{number:02d}.pdf"
                    for branch in BRANCHES
                    for number in range(1, 6)
                },
            )
            pdf_bytes = paths[0].read_bytes()
            self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
            self.assertTrue(pdf_bytes.endswith(b"%%EOF\n"))
            self.assertIn(DISCLAIMER.encode("cp1252"), pdf_bytes)
            self.assertIn(b"PROD-001", pdf_bytes)
            self.assertIn(b"PROD-002", pdf_bytes)
            self.assertIn(b"PROD-003", pdf_bytes)
            startxref = int(pdf_bytes.rsplit(b"startxref\n", 1)[1].splitlines()[0])
            self.assertEqual(pdf_bytes[startxref : startxref + 4], b"xref")
            xref_entries = pdf_bytes[startxref:].splitlines()[3:8]
            for entry in xref_entries:
                object_offset = int(entry[:10])
                self.assertIn(b" obj\n", pdf_bytes[object_offset : object_offset + 16])
            self.assertEqual(render_invoice_pdf(build_test_invoices()[0])[:8], b"%PDF-1.4")


if __name__ == "__main__":
    unittest.main()
