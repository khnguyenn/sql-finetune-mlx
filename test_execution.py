"""Observable query correctness and the limits around executing model output."""
import unittest
import json
from pathlib import Path

from execution import QueryError, grade_query, run_query


def bikes_case():
    return {
        "schema": "CREATE TABLE trip (bike_id VARCHAR)", "table": "trip",
        "reference_sql": "SELECT COUNT(DISTINCT bike_id) FROM trip", "ordered": False,
        "fixtures": [
            {"name": "duplicates", "rows": [["a"], ["a"], ["b"]], "expected": [[2]]},
            {"name": "null", "rows": [[None], ["a"]], "expected": [[1]]},
            {"name": "empty", "rows": [], "expected": [[0]]},
        ],
    }


class ExecutionTests(unittest.TestCase):
    def test_reproduces_unique_bikes_regression(self):
        case = bikes_case()
        self.assertTrue(grade_query(case, "SELECT COUNT(DISTINCT bike_id) FROM trip")["passed"])
        after = grade_query(case, "SELECT COUNT(*) FROM trip")
        self.assertFalse(after["passed"])
        self.assertEqual(after["fixtures"][0]["actual"], [[3]])
        self.assertEqual(after["fixtures"][0]["expected"], [[2]])
        self.assertTrue(after["fixtures"][2]["passed"])

    def test_equivalent_sql_and_reordered_rows_pass(self):
        case = {
            "schema": "CREATE TABLE items (name TEXT)", "table": "items",
            "reference_sql": "SELECT name FROM items", "ordered": False,
            "fixtures": [{"name": "values", "rows": [["b"], ["a"], ["a"]], "expected": [["b"], ["a"], ["a"]]}],
        }
        self.assertTrue(grade_query(case, 'SELECT name AS label FROM items ORDER BY name')["passed"])
        self.assertFalse(grade_query(case, "SELECT DISTINCT name FROM items")["passed"])

    def test_required_order_is_part_of_correctness(self):
        case = {
            "schema": "CREATE TABLE items (n INTEGER)", "table": "items",
            "reference_sql": "SELECT n FROM items ORDER BY n DESC", "ordered": True,
            "fixtures": [{"name": "order", "rows": [[1], [3], [2]], "expected": [[3], [2], [1]]}],
        }
        self.assertFalse(grade_query(case, "SELECT n FROM items ORDER BY n ASC")["passed"])

    def test_empty_results_still_check_column_count(self):
        case = {
            "schema": "CREATE TABLE items (n INTEGER)", "table": "items",
            "reference_sql": "SELECT n FROM items", "ordered": False,
            "fixtures": [{"name": "empty", "rows": [], "expected": []}],
        }
        self.assertFalse(grade_query(case, "SELECT n, n FROM items")["passed"])

    def test_invalid_reference_fixture_stops_instead_of_scoring_model(self):
        case = bikes_case()
        case["fixtures"][0]["expected"] = [[999]]
        with self.assertRaisesRegex(ValueError, "reference"):
            grade_query(case, "SELECT COUNT(*) FROM trip")

    def test_read_only_boundary_rejects_other_operations(self):
        queries = [
            "DELETE FROM trip", "UPDATE trip SET bike_id = 'x'", "DROP TABLE trip",
            "ATTACH DATABASE ':memory:' AS other", "PRAGMA query_only=OFF",
            "SELECT load_extension('no-such-extension')",
            "SELECT name FROM sqlite_master",
            "SELECT COUNT(*) FROM trip; DELETE FROM trip",
            "WITH x AS (SELECT 1) DELETE FROM trip",
        ]
        for query in queries:
            with self.subTest(query=query):
                with self.assertRaises(QueryError):
                    run_query(bikes_case(), [["a"]], query)

    def test_unbounded_recursive_query_is_interrupted(self):
        query = "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT SUM(x) FROM n"
        with self.assertRaisesRegex(QueryError, "interrupted"):
            run_query(bikes_case(), [], query)

    def test_oversized_results_are_rejected(self):
        query = "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<2000) SELECT x FROM n"
        with self.assertRaisesRegex(QueryError, "row limit"):
            run_query(bikes_case(), [], query)

    def test_sql_errors_are_scored_as_failures(self):
        result = grade_query(bikes_case(), "SELECT nonexistent FROM trip")
        self.assertFalse(result["passed"])
        self.assertTrue(all("error" in fixture for fixture in result["fixtures"]))

    def test_curated_reference_queries_match_hand_written_answers(self):
        cases = json.loads(Path(__file__).with_name("execution_cases.json").read_text())
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(grade_query(case, case["reference_sql"])["passed"])


if __name__ == "__main__":
    unittest.main()
