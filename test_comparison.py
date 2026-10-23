"""Formatting diagnostics must not rewrite SQL or accept arbitrary prose."""
import unittest
import hashlib
import json
from pathlib import Path
import tempfile

from compare_results import compare_reports, sql_without_fence


class FormattingTests(unittest.TestCase):
    def test_removes_only_a_single_whole_response_code_fence(self):
        self.assertEqual(sql_without_fence("```sql\nSELECT COUNT(*) FROM items\n```"), "SELECT COUNT(*) FROM items")
        self.assertEqual(sql_without_fence("```\nSELECT 1\n```"), "SELECT 1")
        for text in ("SELECT 1", "Here is SQL:\n```sql\nSELECT 1\n```", "```python\nSELECT 1\n```",
                     "```sql\nSELECT 1\n```\n```sql\nSELECT 2\n```"):
            self.assertEqual(sql_without_fence(text), text)

    def test_diagnostic_preserves_strict_scores_and_rejects_other_fixture_versions(self):
        case = {"id": "count", "schema": "CREATE TABLE items (n INTEGER)", "table": "items",
                "question": "Count all rows.", "reference_sql": "SELECT COUNT(*) FROM items", "ordered": False,
                "fixtures": [{"name": "two", "rows": [[1], [2]], "expected": [[2]]}]}
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text(json.dumps([case]))
            report = {"model": "test", "adapter": None, "correct_cases": 0,
                      "fixture_source_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                      "predictions": [{"id": "count", "generated": "```sql\nSELECT COUNT(*) FROM items\n```", "passed": False}]}
            path = Path(directory) / "report.json"
            original = json.dumps(report)
            path.write_text(original)
            comparison = compare_reports(fixture, [path])
            self.assertEqual(comparison["reports"]["report"]["strict_correct"], 0)
            self.assertEqual(comparison["reports"]["report"]["sql_only_correct"], 1)
            self.assertEqual(path.read_text(), original)
            report["fixture_source_sha256"] = "other"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "unchanged fixture"):
                compare_reports(fixture, [path])


if __name__ == "__main__":
    unittest.main()
