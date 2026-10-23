"""Generate SQL once per question, then check its results on several fixtures."""
import argparse
import hashlib
import json
from pathlib import Path

from common import MODEL, messages
from execution import grade_query


def main():
    source = Path(__file__).with_name("execution_cases.json")
    cases = json.loads(source.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter")
    parser.add_argument("--case", choices=[case["id"] for case in cases])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out)
    if output.exists():
        parser.error(f"{output} exists; choose a new filename to preserve previous results")
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
    # Fail on a broken fixture before loading the model or reporting a score.
    for case in cases:
        grade_query(case, case["reference_sql"])

    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    mx.random.seed(42)
    model, tokenizer = load(MODEL, adapter_path=args.adapter)
    predictions = []
    for case in cases:
        prompt = tokenizer.apply_chat_template(
            messages(case["schema"], case["question"]), tokenize=False, add_generation_prompt=True,
        )
        sql = generate(model, tokenizer, prompt=prompt, max_tokens=128, sampler=make_sampler(temp=0))
        result = grade_query(case, sql)
        predictions.append({
            "id": case["id"], "schema": case["schema"], "question": case["question"],
            "generated": sql, "reference_sql": case["reference_sql"], **result,
        })
        passed = sum(fixture["passed"] for fixture in result["fixtures"])
        print(f"{case['id']}: {passed}/{len(result['fixtures'])} fixtures; case_passed={result['passed']}", flush=True)
        mx.clear_cache()
    correct = sum(result["passed"] for result in predictions)
    report = {
        "model": MODEL, "adapter": args.adapter,
        "cases": len(predictions), "correct_cases": correct,
        "case_pass_rate": correct / len(predictions),
        "fixture_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "metric_limit": "Curated synthetic SQLite fixtures, not the original dataset databases or proof of equivalence for all data.",
        "predictions": predictions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Correct on all fixtures: {correct}/{len(predictions)}; saved {output}")


if __name__ == "__main__":
    main()
