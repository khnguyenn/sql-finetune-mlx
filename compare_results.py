"""Regrade saved responses, separating strict passes from code-fence-only cleanup."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from execution import grade_query


def sql_without_fence(text):
    match = re.fullmatch(r"\s*```(?:sql)?[ \t]*\n(.*?)\n```\s*", text, flags=re.I | re.S)
    if match and "```" not in match[1]:
        return match[1].strip()
    return text


def compare_reports(fixtures, reports):
    fixture_bytes = Path(fixtures).read_bytes()
    cases = json.loads(fixture_bytes)
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Fixtures must be nonempty with unique IDs")
    result = {
        "fixture_sha256": fixture_hash,
        "diagnostic": "Post-hoc: remove one whole-response SQL/untagged code fence only. No SQL repair, prompt changes or new generation. Strict scores are preserved separately.",
        "reports": {},
        "cases": [{"id": case["id"], "question": case["question"], "reference_sql": case["reference_sql"], "outputs": {}} for case in cases],
    }
    for path in map(Path, reports):
        name = path.stem
        if name in result["reports"]:
            raise ValueError("Report filenames must have distinct stems")
        report = json.loads(path.read_text())
        if report["fixture_source_sha256"] != fixture_hash:
            raise ValueError("All reports must use the unchanged fixture file")
        predictions = {row["id"]: row for row in report["predictions"]}
        if len(predictions) != len(report["predictions"]) or set(predictions) != {case["id"] for case in cases}:
            raise ValueError("Reports must contain exactly the same question IDs")
        strict_count = sql_count = 0
        for case, row in zip(cases, result["cases"]):
            prediction = predictions[case["id"]]
            raw = prediction["generated"]
            strict = grade_query(case, raw)
            if strict["passed"] != prediction["passed"]:
                raise ValueError("Saved and freshly graded strict results disagree")
            cleaned = sql_without_fence(raw)
            diagnostic = grade_query(case, cleaned)
            strict_count += strict["passed"]
            sql_count += diagnostic["passed"]
            row["outputs"][name] = {
                "generated": raw, "strict_passed": strict["passed"],
                "code_fence_removed": cleaned != raw, "sql": cleaned,
                "sql_only_passed": diagnostic["passed"], "fixtures": diagnostic["fixtures"],
            }
        if strict_count != report["correct_cases"]:
            raise ValueError("Saved aggregate strict count disagrees")
        result["reports"][name] = {
            "source": str(path), "model": report["model"], "adapter": report["adapter"],
            "strict_correct": strict_count, "sql_only_correct": sql_count, "cases": len(cases),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--reports", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; choose a new file")
    result = compare_reports(args.fixtures, args.reports)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["reports"], indent=2))


if __name__ == "__main__":
    main()
