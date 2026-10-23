"""Retrieval supplies relevant training examples without exposing test answers."""
import json
from pathlib import Path
import tempfile
import unittest

from sql_finetune.common import messages
from sql_finetune.retrieval import ExampleRetriever, retrieval_messages


class RetrievalTests(unittest.TestCase):
    def test_retrieves_by_input_and_excludes_the_exact_target(self):
        examples = [
            messages("CREATE TABLE items (name TEXT)", "Count distinct names.")
            + [{"role": "assistant", "content": "SELECT COUNT(DISTINCT name) FROM items"}],
            messages("CREATE TABLE goods (name TEXT)", "Count distinct names.")
            + [{"role": "assistant", "content": "SELECT COUNT(DISTINCT name) FROM goods"}],
            messages("CREATE TABLE values_table (price REAL)", "Find the maximum price.")
            + [{"role": "assistant", "content": "SELECT MAX(price) FROM values_table"}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            corpus = Path(directory) / "train.jsonl"
            corpus.write_text("\n".join(json.dumps({"messages": row}) for row in examples))
            retriever = ExampleRetriever(corpus)
            selected = retriever.retrieve("CREATE TABLE items (name TEXT)", "Count distinct names.", 1)
            self.assertEqual(selected[0]["line"], 2)
            self.assertEqual(selected[0]["sql"], "SELECT COUNT(DISTINCT name) FROM goods")
            self.assertEqual(selected, retriever.retrieve("CREATE TABLE items (name TEXT)", "Count distinct names.", 1))

    def test_context_keeps_the_system_and_final_question_and_uses_only_selected_examples(self):
        example = {"input": "Schema:\nCREATE TABLE goods (name TEXT)\n\nQuestion:\nCount names.",
                   "sql": "SELECT COUNT(*) FROM goods", "line": 2, "score": 1.0}
        original = messages("CREATE TABLE staff (name TEXT)", "Count staff.")
        augmented = retrieval_messages("CREATE TABLE staff (name TEXT)", "Count staff.", [example])
        self.assertEqual(augmented[0], original[0])
        self.assertTrue(augmented[1]["content"].endswith(original[1]["content"]))
        self.assertIn(example["sql"], augmented[1]["content"])
        self.assertNotIn("SELECT COUNT(*) FROM staff", augmented[1]["content"])
        self.assertEqual(retrieval_messages("schema", "question", []), messages("schema", "question"))


if __name__ == "__main__":
    unittest.main()
