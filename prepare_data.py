"""Download a public SQL dataset and make small table-disjoint chat splits."""
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from common import MODEL, messages

DATASET = "b-mc2/sql-create-context"
REVISION = "9d80a6a118b838d9defc3798d659a54a2ac2ff37"


def split_by_table(rows, sizes, seed=42):
    groups = defaultdict(list)
    for row in rows:
        groups[row["table"]].append(row)
    rng = random.Random(seed)
    tables = sorted(groups)
    rng.shuffle(tables)
    result = {}
    for name, size in sizes.items():
        selected = []
        while len(selected) < size:
            if not tables:
                raise ValueError("Not enough distinct tables to fill disjoint splits")
            selected.extend(groups[tables.pop()])
        rng.shuffle(selected)
        result[name] = selected[:size]
    return result


def main():
    from huggingface_hub import hf_hub_download
    from transformers import AutoTokenizer

    output = Path("data")
    if output.exists():
        raise SystemExit("data/ already exists; keep it fixed for this experiment. Use a new directory for a new split.")
    source = hf_hub_download(
        repo_id=DATASET, repo_type="dataset", revision=REVISION,
        filename="sql_create_context_v4.json",
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    source_rows = json.loads(Path(source).read_text())
    rows, seen = [], set()
    for row in source_rows:
        schema, question, answer = (row[k].strip() for k in ("context", "question", "answer"))
        table = re.fullmatch(r"CREATE TABLE\s+([a-zA-Z_]\w*)\s*\([^;]+\)\s*;?", schema, re.I)
        if not table or not answer.upper().startswith("SELECT ") or len(answer) > 200:
            continue
        key = (schema, question)
        if key in seen:
            continue
        seen.add(key)
        chat = messages(schema, question) + [{"role": "assistant", "content": answer}]
        if len(tokenizer.apply_chat_template(chat, return_dict=False)) > 512:
            continue
        rows.append({"table": table[1].lower(), "messages": chat})
    splits = split_by_table(rows, {"train": 1000, "valid": 100, "test": 100})
    output.mkdir()
    for name, split in splits.items():
        (output / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in split))
    metadata = {
        "dataset": DATASET, "revision": REVISION, "seed": 42,
        "source_rows": len(source_rows), "eligible_rows": len(rows),
        "splits": {name: len(split) for name, split in splits.items()},
        "split_strategy": "disjoint table names; whole table groups assigned then sampled",
        "max_tokens": 512, "model": MODEL,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))
    print("Example training conversation:")
    print(json.dumps(splits["train"][0]["messages"], indent=2))


if __name__ == "__main__":
    main()
