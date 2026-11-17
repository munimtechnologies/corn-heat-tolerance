# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. (MV2). Made with AI agents working in MV2's name.
import io
import os
import tempfile
import unittest
import zipfile

import inspect_fsa as m


PAGE = """<html><body>
<a href="/documents/arcco-2025-data-2026-11-02">2025 ARC-County Benchmark Yields and Revenues as of November 02, 2026 (Excel format, 2.9MB)</a>
<a href="/documents/2024-arcco-pdf">2024 ARC-CO PDF</a>
<a href="/news/press">News</a>
<a href="/documents/arcic-2024">ARC-IC Assigned County Trend Adjusted Yields for Program Year 2024</a>
<a href="mailto:x@y.z">mail</a>
<a href="https://www.fsa.usda.gov/sites/default/files/documents/Detailed_ARCCO_NASS_RMA_2009_2017.xlsx">Detailed ARC-CO NASS and RMA County Yields - 2009-2017</a>
</body></html>"""


class TestLinks(unittest.TestCase):
    def test_parse_and_select(self):
        links = m.parse_links(PAGE, "https://www.fsa.usda.gov/resources/programs/arc-plc/program-data")
        self.assertEqual(len(links), 5)  # mailto dropped
        sel = m.select_links(links)
        urls = [u for u, _ in sel]
        self.assertIn("https://www.fsa.usda.gov/documents/arcco-2025-data-2026-11-02", urls)
        self.assertNotIn("https://www.fsa.usda.gov/news/press", urls)
        self.assertNotIn("https://www.fsa.usda.gov/documents/arcic-2024", urls)
        # PDF sorted last
        self.assertTrue(urls[-1].endswith("2024-arcco-pdf"))
        self.assertEqual(len(sel), 3)


class TestSniff(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(m.sniff(b"PK\x03\x04rest"), "zip")
        self.assertEqual(m.sniff(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1xx"), "xls")
        self.assertEqual(m.sniff(b"%PDF-1.7"), "pdf")
        self.assertEqual(m.sniff(b"  <!DOCTYPE html><html>"), "html")
        self.assertEqual(m.sniff(b"a,b,c"), "other")

    def test_zip_kind_docx(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.docx")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("word/document.xml", "<w:document><w:p><w:t>Hello</w:t></w:p><w:p><w:t>RMA</w:t></w:p></w:document>")
            self.assertEqual(m.zip_kind(p), "docx")
            self.assertEqual(m.docx_text(p).split(), ["Hello", "RMA"])


ROWS = [
    ["2025 ARC-County Benchmark Yields", None, None, None, None, None],
    [None, None, None, None, "Benchmark", "Actual"],
    ["State Name", "County Name", "Crop", "Practice", "Yield", "2025 Yield"],
    ["Nebraska", "Adams", "CORN", "Irrigated", 210.5, 220.1],
    ["Nebraska", "Adams", "CORN", "Non-Irrigated", 140.2, None],
    ["Kansas", "Finney", "SOYBEANS", "All", 40.0, 41.0],
    ["Iowa", "Story", "CORN", "All", 190.0, 200.0],
    ["NEBRASKA", "Hall", "POPCORN", "All", 5000, 5100],
]


class TestInspect(unittest.TestCase):
    def test_header(self):
        self.assertEqual(m.find_header_row(ROWS), 2)
        names = m.column_names(ROWS, 2)
        self.assertEqual(names[4], "Benchmark | Yield")
        self.assertEqual(names[0], "State Name")
        self.assertEqual(m.year_columns(names), {5: ["2025"]})

    def test_counts_no_values(self):
        info = m.inspect_rows(ROWS, "s")
        self.assertEqual(info["header_row_index"], 2)
        self.assertEqual(info["state_col_used"], "State Name")
        self.assertEqual(info["ne_ks_rows"], {"NE|corn|Irrigated": 1, "NE|corn|Non-Irrigated": 1,
                                              "KS|soybeans|All": 1})
        ne = info["ne_ks_nonempty_numeric_cells"]
        self.assertEqual(ne["NE|corn|Irrigated|Actual | 2025 Yield"], 1)
        self.assertNotIn("NE|corn|Non-Irrigated|Actual | 2025 Yield", ne)
        self.assertEqual(info["practice_values"]["All"], 3)
        self.assertEqual(info["crop_values_top"]["CORN"], 3)
        # no yield value anywhere in the summary
        flat = repr(info)
        for v in ("210.5", "220.1", "140.2", "41.0", "5100"):
            self.assertNotIn(v, flat)

    def test_state_crop(self):
        self.assertEqual(m.state_of(31), "NE")
        self.assertEqual(m.state_of(20.0), "KS")
        self.assertEqual(m.state_of("31001"), "NE")
        self.assertIsNone(m.state_of("Iowa"))
        self.assertEqual(m.crop_of("Corn"), "corn")
        self.assertIsNone(m.crop_of("Sweet Corn"))
        self.assertEqual(m.crop_of("Soybeans"), "soybeans")

    def test_xlsx_roundtrip(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Corn"
            for r in ROWS:
                ws.append(r)
            wb.save(p)
            with open(p, "rb") as f:
                self.assertEqual(m.sniff(f.read(8)), "zip")
            self.assertEqual(m.zip_kind(p), "xlsx")
            sheets = m.read_xlsx(p)
            self.assertEqual(sheets[0]["sheet"], "Corn")
            self.assertEqual(sheets[0]["ne_ks_rows"]["KS|soybeans|All"], 1)


if __name__ == "__main__":
    unittest.main()
