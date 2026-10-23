"""Build versioned SQL lessons with expected answers computed independently in Python."""
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from common import MODEL, messages
from execution import grade_query

def expected_rows(family, rows, threshold, tag):
    numbers = [row[1] for row in rows if row[1] is not None]
    if family == "rows": return [[len(rows)]]
    if family == "filtered_count": return [[sum(row[1] is not None and row[1] > threshold for row in rows)]]
    if family == "distinct_count": return [[len({row[0] for row in rows if row[0] is not None})]]
    if family == "nonnull_count": return [[sum(row[0] is not None for row in rows)]]
    if family == "maximum": return [[max(numbers) if numbers else None]]
    if family == "minimum": return [[min(numbers) if numbers else None]]
    if family == "average": return [[sum(numbers) / len(numbers) if numbers else None]]
    if family == "filtered_sum":
        selected = [r[1] for r in rows if r[2] == tag and r[1] is not None]
        return [[sum(selected) if selected else None]]
    if family == "group_sum":
        groups = defaultdict(list)
        for row in rows:
            groups[row[2]].append(row[1])
        result = []
        for key, group in groups.items():
            values = [value for value in group if value is not None]
            result.append([key, sum(values) if values else None])
        return result
    if family == "group_count":
        return [[key, count] for key, count in Counter(r[2] for r in rows).items()]
    if family in ("descending", "ascending"):
        return [[r[0]] for r in sorted(rows, key=lambda r: (r[1] is not None, r[1] or 0), reverse=family == "descending")]
    if family == "text_filter": return [[r[0]] for r in rows if r[2] == tag]
    if family == "numeric_filter": return [[r[0]] for r in rows if r[1] is not None and r[1] > threshold]
    raise ValueError(f"Unknown family: {family}")


def build_examples(split, version=2):
    if split not in ("train", "valid"):
        raise ValueError("Expected train or valid")
    fields = [("item_name", "amount", "status"), ("asset_code", "cost", "zone"), ("record_label", "value", "category"), ("member", "score", "region"), ("device_id", "reading", "location"), ("product_label", "price", "kind")]
    examples = []
    for i in range(48 if split == "train" else 8):
        label, number, group = fields[i % len(fields)]
        table = f"lesson_{split}_{i}" if version == 2 else f"lesson_v3_{split}_{i}"
        schema = f"CREATE TABLE {table} ({label} TEXT, {number} REAL, {group} TEXT);"
        threshold = (i % 9 - 3) * 5
        tag = ["paid", "open", "completed", "west", "April 4, 2002", "June 8, 1999"][i % 6]
        rows = [["alpha", threshold-5, tag], ["alpha", threshold+5, "other"], ["beta", threshold+10, tag], [None, threshold+15, tag], ["gamma", threshold, tag], ["delta", None, None]]
        prefix = f"SELECT {{}} FROM {table}"
        targets = {
            "rows": (f"How many rows are in {table}?", prefix.format("COUNT(*)")),
            "filtered_count": (f"How many records have {number} above {threshold}?", prefix.format("COUNT(*)") + f" WHERE {number} > {threshold}"),
            "distinct_count": (f"How many unique values of {label} are there?", prefix.format(f"COUNT(DISTINCT {label})")),
            "nonnull_count": (f"Count records that have a non-null {label}.", prefix.format(f"COUNT({label})")),
            "maximum": (f"What is the highest {number}?", prefix.format(f"MAX({number})")),
            "minimum": (f"What is the lowest {number}?", prefix.format(f"MIN({number})")),
            "average": (f"What is the average {number}?", prefix.format(f"AVG({number})")),
            "filtered_sum": (f"What is the total {number} for records whose {group} is '{tag}'?", prefix.format(f"SUM({number})") + f" WHERE {group} = '{tag}'"),
            "group_sum": (f"Show each {group} and its total {number}.", prefix.format(f"{group}, SUM({number})") + f" GROUP BY {group}"),
            "group_count": (f"For each {group}, show the number of rows.", prefix.format(f"{group}, COUNT(*)") + f" GROUP BY {group}"),
            "descending": (f"List {label} values from highest to lowest {number}.", prefix.format(label) + f" ORDER BY {number} DESC"),
            "ascending": (f"List {label} values from lowest to highest {number}.", prefix.format(label) + f" ORDER BY {number} ASC"),
            "text_filter": (f"Which {label} has {group} '{tag}'?", prefix.format(label) + f" WHERE {group} = '{tag}'"),
            "numeric_filter": (f"List {label} values for records with {number} greater than {threshold}.", prefix.format(label) + f" WHERE {number} > {threshold}"),
        }
        # Alternate natural phrasings without changing the target SQL rule.
        if i % 2:
            targets["distinct_count"] = (f"Count the different {label} values in {table}.", targets["distinct_count"][1])
            targets["descending"] = (f"Return {label} sorted by {number} descending.", targets["descending"][1])
            targets["group_sum"] = (f"Return each {group} with the sum of {number} for that group.", targets["group_sum"][1])
        if version == 3:
            noun = ["items", "assets", "records", "members", "devices", "products"][i % 6]
            phrases = [f"How many unique values of {label} are there?", f"How many different {noun} are represented by these rows?", f"Count the distinct {label} values.", f"How many different {noun} appear in {table}?"]
            targets["distinct_count"] = (phrases[(i // 6) % 4], targets["distinct_count"][1])
        for family, (question, sql) in targets.items():
            examples.append({
                "family": family, "table": table, "schema": schema, "question": question,
                "reference_sql": sql, "ordered": family in ("ascending", "descending"),
                "fixtures": [
                    {"name": "duplicates-nulls-boundary", "rows": rows, "expected": expected_rows(family, rows, threshold, tag)},
                    {"name": "empty", "rows": [], "expected": expected_rows(family, [], threshold, tag)},
                ],
            })
        if version == 3:
            from datetime import datetime

            date = ["January 2, 2005", "February 11, 2000", "July 9, 2003", "December 12, 2012"][i % 4]
            iso = datetime.strptime(date, "%B %d, %Y").strftime("%Y-%m-%d")
            date_table = f"lesson_v3_{split}_date_{i}"
            examples.append({
                "family": "literal_date", "table": date_table,
                "schema": f"CREATE TABLE {date_table} ({label} TEXT, event_date TEXT);",
                "question": f"Which {label} occurred on {date}?" if i % 2 else f"Show {label} for event_date {date}.",
                "reference_sql": f"SELECT {label} FROM {date_table} WHERE event_date = '{date}'", "ordered": False,
                "fixtures": [
                    {"name": "preserve-stored-text", "rows": [["alpha", date], ["beta", iso], [None, date]], "expected": [["alpha"], [None]]},
                    {"name": "empty", "rows": [], "expected": []},
                ],
            })
    return examples


def main():
    import argparse
    from transformers import AutoTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, choices=[2, 3], default=2)
    version = parser.parse_args().version
    output = Path(f"data/v{version}")
    if output.exists():
        raise SystemExit(f"{output} exists; preserve this dataset and use a new version for changes")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    splits = {split: build_examples(split, version) for split in ("train", "valid")}
    evaluation_files = ["execution_cases.json", "execution_holdout.json"]
    if version == 3:
        evaluation_files.append("execution_holdout_v3.json")
    evaluations = [case for filename in evaluation_files for case in json.loads(Path(filename).read_text())]
    eval_tables = {case["table"] for case in evaluations}
    output_rows = {}
    for split, examples in splits.items():
        assert not {row["table"] for row in examples} & eval_tables
        rows = []
        for case in examples:
            assert grade_query(case, case["reference_sql"])["passed"]
            chat = messages(case["schema"], case["question"]) + [{"role": "assistant", "content": case["reference_sql"]}]
            assert len(tokenizer.apply_chat_template(chat, return_dict=False)) <= 512
            rows.append({"family": case["family"], "table": case["table"], "messages": chat})
        random.Random(42).shuffle(rows)
        output_rows[split] = rows
    output.mkdir()
    for split, rows in output_rows.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    metadata = {
        "recipe": f"balanced-rule-generated-v{version}", "seed": 42,
        "splits": {split: len(rows) for split, rows in output_rows.items()},
        "train_families": dict(Counter(row["family"] for row in output_rows["train"])),
        "holdout_sha256": hashlib.sha256(Path(evaluation_files[-1]).read_bytes()).hexdigest(),
        "target_validation": "Executed against independently computed Python answers, including duplicates, NULLs and empty tables.",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
