"""Check the split boundary that makes the experiment meaningful."""
import unittest

from prepare_data import split_by_table


class SplitTests(unittest.TestCase):
    def test_keeps_related_table_rows_out_of_other_splits(self):
        rows = [
            {"table": table, "question": f"{table}-{i}"}
            for table in ("people", "orders", "products", "schools", "books")
            for i in range(4)
        ]
        splits = split_by_table(rows, {"train": 5, "valid": 3, "test": 3})
        self.assertEqual([len(splits[k]) for k in splits], [5, 3, 3])
        table_sets = [{r["table"] for r in group} for group in splits.values()]
        for i, left in enumerate(table_sets):
            for right in table_sets[i + 1:]:
                self.assertFalse(left & right)
        self.assertEqual(splits, split_by_table(rows, {"train": 5, "valid": 3, "test": 3}))

    def test_fails_instead_of_reusing_a_table_to_fill_a_split(self):
        rows = [{"table": "people", "question": str(i)} for i in range(20)]
        with self.assertRaisesRegex(ValueError, "Not enough"):
            split_by_table(rows, {"train": 2, "valid": 2, "test": 2})


if __name__ == "__main__":
    unittest.main()
