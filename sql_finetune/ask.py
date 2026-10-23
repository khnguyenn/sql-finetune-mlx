"""Try the identical SQL prompt with the original model or a saved adapter."""
import argparse

import mlx.core as mx
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from .common import MODEL, messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", help="Saved LoRA directory, e.g. adapters/sql-v1")
    parser.add_argument("--schema", default="CREATE TABLE employees (name TEXT, salary INTEGER);")
    parser.add_argument("--question", default="How many employees earn more than 80000?")
    args = parser.parse_args()
    mx.random.seed(42)
    model, tokenizer = load(MODEL, adapter_path=args.adapter)
    prompt = tokenizer.apply_chat_template(
        messages(args.schema, args.question), tokenize=False, add_generation_prompt=True,
    )
    print(generate(model, tokenizer, prompt=prompt, max_tokens=128, sampler=make_sampler(temp=0)))


if __name__ == "__main__":
    main()
