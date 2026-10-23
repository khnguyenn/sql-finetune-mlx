"""Generate SQL once per question, then check its results on several fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
from importlib.metadata import version
import time

from .common import FIXTURES_DIR, MODEL
from .execution import grade_query
from .retrieval import ExampleRetriever, retrieval_messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--revision", help="Optional pinned Hugging Face model revision")
    parser.add_argument("--adapter")
    parser.add_argument("--retrieval-corpus", type=Path, help="Trusted training JSONL only; never test answers")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_DIR / "execution_cases.json")
    parser.add_argument("--case")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    source = args.fixtures
    cases = json.loads(source.read_text())
    if not cases or len({case["id"] for case in cases}) != len(cases):
        parser.error("Fixture file must contain cases with unique IDs")
    output = Path(args.out)
    if output.exists():
        parser.error(f"{output} exists; choose a new filename to preserve previous results")
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error("--case does not match a case in the fixture file")
    # Fail on a broken fixture before loading the model or reporting a score.
    for case in cases:
        grade_query(case, case["reference_sql"])
    retriever = ExampleRetriever(args.retrieval_corpus) if args.retrieval_corpus else None

    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler
    from huggingface_hub import try_to_load_from_cache

    mx.random.seed(42)
    model, tokenizer, config = load(args.model, adapter_path=args.adapter, revision=args.revision, return_config=True)
    cached_config = try_to_load_from_cache(args.model, "config.json", revision=args.revision or "main")
    resolved_revision = Path(cached_config).parent.name if isinstance(cached_config, str) else args.revision
    predictions = []
    for case in cases:
        examples = retriever.retrieve(case["schema"], case["question"], args.top_k) if retriever else []
        conversation = retrieval_messages(case["schema"], case["question"], examples)
        prompt = tokenizer.apply_chat_template(
            conversation, tokenize=False, add_generation_prompt=True,
        )
        started = time.perf_counter()
        sql = generate(model, tokenizer, prompt=prompt, max_tokens=128, sampler=make_sampler(temp=0))
        generation_seconds = time.perf_counter() - started
        result = grade_query(case, sql)
        predictions.append({
            "id": case["id"], "schema": case["schema"], "question": case["question"],
            "generated": sql, "reference_sql": case["reference_sql"], **result,
            "messages": conversation, "prompt": prompt, "retrieved_examples": examples,
            "prompt_tokens": len(tokenizer.encode(prompt)), "generation_seconds": generation_seconds,
        })
        passed = sum(fixture["passed"] for fixture in result["fixtures"])
        print(f"{case['id']}: {passed}/{len(result['fixtures'])} fixtures; case_passed={result['passed']}", flush=True)
        mx.clear_cache()
    correct = sum(result["passed"] for result in predictions)
    report = {
        "model": args.model, "model_revision": resolved_revision, "adapter": args.adapter,
        "adapter_sha256": hashlib.sha256((Path(args.adapter) / "adapters.safetensors").read_bytes()).hexdigest() if args.adapter else None,
        "decoding": {"seed": 42, "temperature": 0, "max_tokens": 128},
        "mlx_lm_version": version("mlx-lm"), "mlx_version": version("mlx"),
        "quantization": config.get("quantization"),
        "retrieval": {"method": "BM25", "k1": 1.5, "b": 0.75, "top_k": args.top_k,
                      "corpus": str(args.retrieval_corpus), "corpus_sha256": retriever.sha256,
                      "corpus_examples": len(retriever.documents)} if retriever else None,
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
