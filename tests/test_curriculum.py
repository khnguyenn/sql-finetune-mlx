"""Check independent expected answers and separation of the new training data."""
import json
import unittest
from collections import Counter
from sql_finetune.common import FIXTURES_DIR

from sql_finetune.execution import grade_query
from sql_finetune.prepare_curriculum import build_examples


class CurriculumTests(unittest.TestCase):
    def test_balanced_families_and_distinct_split_tables(self):
        train, valid = build_examples("train"), build_examples("valid")
        self.assertEqual(len(Counter(row["family"] for row in train)), 14)
        self.assertEqual(set(Counter(row["family"] for row in train).values()), {48})
        self.assertEqual(set(Counter(row["family"] for row in valid).values()), {8})
        self.assertFalse({r["table"] for r in train} & {r["table"] for r in valid})

    def test_every_target_agrees_with_independent_python_answers(self):
        for row in build_examples("train") + build_examples("valid"):
            with self.subTest(family=row["family"], table=row["table"]):
                self.assertTrue(grade_query(row, row["reference_sql"])["passed"])

    def test_no_training_prompt_or_table_matches_evaluation_cases(self):
        train = build_examples("train") + build_examples("valid")
        for name in ("execution_cases.json", "execution_holdout.json"):
            cases = json.loads((FIXTURES_DIR / name).read_text())
            self.assertFalse({row["table"] for row in train} & {case["table"] for case in cases})
            self.assertFalse({(row["schema"], row["question"]) for row in train} & {(case["schema"], case["question"]) for case in cases})
            for case in cases:
                self.assertTrue(grade_query(case, case["reference_sql"])["passed"])

    def test_v3_adds_balanced_paraphrases_and_dates_without_reusing_evaluation(self):
        rows = build_examples("train", 3) + build_examples("valid", 3)
        counts = Counter(row["family"] for row in build_examples("train", 3))
        self.assertEqual(len(counts), 15)
        self.assertEqual(set(counts.values()), {48})
        cases = [case for name in ("execution_cases.json", "execution_holdout.json", "execution_holdout_v3.json") for case in json.loads((FIXTURES_DIR / name).read_text())]
        self.assertFalse({r["table"] for r in rows} & {c["table"] for c in cases})
        self.assertFalse({(r["schema"], r["question"]) for r in rows} & {(c["schema"], c["question"]) for c in cases})
        for row in rows + cases:
            self.assertTrue(grade_query(row, row["reference_sql"])["passed"])


if __name__ == "__main__":
    unittest.main()
