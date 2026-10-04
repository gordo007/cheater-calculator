import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from clean_data import clean, main, parse_number, read_table, unique_headers  # noqa: E402


class ParseNumberTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_number("$1,250.00"), 1250.0)
        self.assertEqual(parse_number("(45.50)"), -45.5)
        self.assertEqual(parse_number("€ 7"), 7.0)
        self.assertEqual(parse_number("12 USD"), 12.0)
        self.assertIsNone(parse_number("TBD"))
        self.assertIsNone(parse_number("1,23"))


class HeadersTest(unittest.TestCase):
    def test_snake_case_and_unique(self):
        self.assertEqual(unique_headers(["Order ID", " Name ", "name", ""]), ["order_id", "name", "name_2", "column"])


class CleanTest(unittest.TestCase):
    def test_sample_file(self):
        headers, data, report = clean(read_table(ROOT / "samples" / "messy_sales.csv"))
        self.assertEqual(headers, ["order_id", "customer_name", "order_date", "amount", "region", "notes"])
        self.assertEqual(len(data), 5)  # blank row and duplicate removed
        self.assertEqual(data[0], ["1001", "Alice Smith", "2024-03-14", "1250", "North", ""])
        self.assertEqual(data[2][1:4], ["Carol White", "2024-03-16", "-45.5"])
        self.assertEqual(data[3][3], "TBD")  # unparseable value kept, and flagged
        text = "\n".join(report)
        self.assertIn("Exact duplicate rows removed: 1", text)
        self.assertIn("`TBD`", text)

    def test_dayfirst_detected(self):
        rows = [["d"], ["25/12/2024"], ["01/02/2024"]]
        _, data, _ = clean(rows)
        self.assertEqual([r[0] for r in data], ["2024-12-25", "2024-02-01"])

    def test_ambiguous_dates_flagged(self):
        rows = [["d"], ["01/02/2024"], ["03/04/2024"]]
        _, data, report = clean(rows, dayfirst=True)
        self.assertEqual(data[0][0], "2024-02-01")
        self.assertIn("ambiguous", "\n".join(report))

    def test_text_column_untouched(self):
        rows = [["code"], ["A1"], ["B2"], ["C3"]]
        _, data, _ = clean(rows)
        self.assertEqual([r[0] for r in data], ["A1", "B2", "C3"])


class CliTest(unittest.TestCase):
    def test_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, rep = Path(tmp) / "o.csv", Path(tmp) / "r.md"
            main([str(ROOT / "samples" / "messy_sales.csv"), "-o", str(out), "-r", str(rep)])
            self.assertTrue(out.read_text().startswith("order_id,customer_name"))
            self.assertIn("# Cleaning report", rep.read_text())


if __name__ == "__main__":
    unittest.main()
