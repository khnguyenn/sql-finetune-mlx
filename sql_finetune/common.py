"""Use the same model and prompt before training, during training and after."""
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
SYSTEM = "Write a SQLite SELECT query for the given schema and question. Return only SQL, without explanations or Markdown."


def messages(schema, question):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Schema:\n{schema}\n\nQuestion:\n{question}"},
    ]
