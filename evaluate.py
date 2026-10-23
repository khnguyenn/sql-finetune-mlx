"""Save a small, repeatable SQL generation comparison, using greedy decoding."""
import argparse
import json
from pathlib import Path

import mlx.core as mx
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from common import MODEL


def normalise(text):
    # Deliberately strict: equivalent SQL can still have a different text match.
    return " ".join(text.strip().rstrip(";").split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter")
    parser.add_argument("--split", choices=["valid", "test"], default="valid")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out)
    if output.exists():
        raise SystemExit(f"{output} exists; choose a new output file to keep previous results.")
    rows = [json.loads(line) for line in Path(f"data/{args.split}.jsonl").read_text().splitlines()]
    if not 1 <= args.limit <= len(rows):
        parser.error(f"--limit must be between 1 and {len(rows)}")
    mx.random.seed(42)
    model, tokenizer = load(MODEL, adapter_path=args.adapter)
    sampler = make_sampler(temp=0)
    predictions = []
    for i, row in enumerate(rows[:args.limit], 1):
        chat = row["messages"]
        prompt = tokenizer.apply_chat_template(chat[:-1], tokenize=False, add_generation_prompt=True)
        prediction = generate(model, tokenizer, prompt=prompt, max_tokens=128, sampler=sampler)
        expected = chat[-1]["content"]
        matched = normalise(prediction) == normalise(expected)
        predictions.append({"input": chat[:-1], "expected": expected, "generated": prediction, "text_match": matched})
        print(f"{i}/{args.limit}: text_match={matched}", flush=True)
        mx.clear_cache()
    matched_count = sum(row["text_match"] for row in predictions)
    report = {
        "model": MODEL, "adapter": args.adapter, "split": args.split,
        "examples": len(predictions), "text_matches": matched_count,
        "text_match_rate": matched_count / len(predictions),
        "metric_limit": "Whitespace and final semicolon normalised; not SQL execution accuracy.",
        "predictions": predictions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Text matches: {matched_count}/{len(predictions)}; saved {output}")


if __name__ == "__main__":
    main()
