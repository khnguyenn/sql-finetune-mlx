# Learn SQL fine-tuning with MLX-LM

Goal: give a small model a database schema and an English question, then produce SQL. Compare the same model before and after training a LoRA adapter.

This project uses Python 3.12, MLX-LM 0.32.2, Qwen2.5-0.5B-Instruct and a small subset of `b-mc2/sql-create-context`. It is intended for the Apple M4 Mac with 16 GB unified memory checked during this walkthrough.

The first run is complete; see [RESULTS.md](RESULTS.md) for measured results and examples. The numbered steps below record the workflow. When repeating it, skip existing data preparation and choose new result filenames and a new adapter directory to preserve the first experiment.

Private GitHub repository: [khnguyenn/sql-finetune-mlx](https://github.com/khnguyenn/sql-finetune-mlx). To set up another checkout, clone that repository and run `uv sync --locked` inside it. Downloaded data, adapters and local reports are excluded from Git and can be reproduced with the commands below.

## 1. Enter the project

```bash
cd /Users/kianguyen/Documents/ChatGPT/personal/sql-finetune
```

`cd` chooses the folder where commands run and generated files are saved. The project lives inside the existing personal workspace; no new remote repository is required.

## 2. Install the isolated Python environment

```bash
uv sync --locked
```

`uv` reads `pyproject.toml` and `uv.lock`, chooses Python 3.12 and installs the recorded dependencies into `.venv/`. This leaves the Mac's system Python packages alone. The first setup used `uv sync` to generate the lockfile.

MLX is the computation framework for Apple silicon. MLX-LM supplies model loading, text generation and fine-tuning. You do not have to clone its source repository to use its Python package.

Verify that the GPU is available:

```bash
uv run python -c 'import mlx.core as mx; print(mx.default_device()); print(mx.metal.is_available())'
```

Expected: a GPU device and `True`.

Transformers may print a message that PyTorch is not installed. In this setup, Transformers supplies tokenization and MLX supplies model computation, so that message does not require installing PyTorch.

## 3. Prepare the examples

```bash
uv run python prepare_data.py
```

This downloads the public dataset and tokenizer. It keeps short single-table SELECT examples, removes duplicate schema/question pairs, and excludes examples above 512 tokens. It makes three files:

| File | Rows | Purpose |
| --- | ---: | --- |
| `data/train.jsonl` | 1,000 | Examples used to update adapter weights |
| `data/valid.jsonl` | 100 | Examples for checking training and choosing settings |
| `data/test.jsonl` | 100 | Reserved for the final comparison after choosing settings |

All examples for a given table name stay in one split, reducing leakage from related tables. The script pins the dataset revision and uses seed 42. It refuses to replace an existing `data/` directory, so later experiments keep the same comparison data.

Each JSONL line contains a conversation:

```json
{"messages":[{"role":"system","content":"Write a SQLite SELECT query for the given schema and question. Return only SQL, without explanations or Markdown."},{"role":"user","content":"Schema:\nCREATE TABLE employees (name TEXT, salary INTEGER);\n\nQuestion:\nHow many employees earn more than 80000?"},{"role":"assistant","content":"SELECT COUNT(*) FROM employees WHERE salary > 80000;"}]}
```

The system message describes the task, the user message supplies the schema and question, and the assistant message supplies the correct SQL. The tokenizer converts those messages into the token sequence consumed by the model.

The script also saves table metadata for auditing splits. MLX-LM trains on `messages`; the extra `table` field is not part of the model's prompt.

## 4. Try the original model

Run model work through the Mac's shared queue so it does not overlap heavy work in another project:

```bash
~/.local/bin/qtms-validate uv run python ask.py
```

The first invocation downloads roughly 1 GB of model weights to the Hugging Face cache. Later commands reuse the cache. This is inference only: the original model generates SQL without learning from this request.

The default example asks how many employees earn more than 80,000. A correct query is:

```sql
SELECT COUNT(*) FROM employees WHERE salary > 80000;
```

Try a different input:

```bash
~/.local/bin/qtms-validate uv run python ask.py \
  --schema 'CREATE TABLE products (name TEXT, price REAL);' \
  --question 'What is the highest product price?'
```

## 5. Record a baseline

```bash
~/.local/bin/qtms-validate uv run python evaluate.py \
  --split valid --limit 20 --out results/before-valid.json
```

This generates SQL for the first 20 fixed validation examples and saves inputs, expected SQL and actual output. Temperature 0 uses greedy decoding, making the comparison less dependent on sampling.

The initial metric is **normalised SQL text match**, not execution accuracy: it ignores repeated whitespace and a final semicolon, but equivalent SQL written differently can count as incorrect. Inspect saved predictions as well as the number. These 20 examples are a small learning experiment, not a reliable benchmark.

## 6. Train a first LoRA adapter

```bash
~/.local/bin/qtms-validate uv run mlx_lm.lora --config train.yaml
```

MLX-LM loads the model, freezes its original parameters and trains small added matrices. It saves the result under `adapters/sql-v1/`; this adapter is loaded alongside the original model for generation.

| Setting | Value | What it controls |
| --- | --- | --- |
| `iters` | 100 | Number of training batches/updates in this starter run |
| `batch_size` | 1 | One example per update; lower peak memory |
| `learning_rate` | 0.0001 | Size of parameter updates |
| `num_layers` | 8 | Add adapters to the last eight model blocks |
| `lora_parameters.rank` | 8 | Size of the added trainable matrices |
| `max_seq_length` | 512 | Maximum token sequence length |
| `mask_prompt` | true | Compute training loss on the answer tokens |
| `grad_checkpoint` | true | Recompute some intermediate values to reduce memory |

100 updates with batch size 1 is not a full pass through 1,000 examples. It is a small first run to check the workflow, not an optimized training recipe.

Training loss measures how well the model predicts the training answers. Validation loss measures answer prediction on examples held out of training. Lower loss does not automatically mean the generated SQL is more often correct.

For another experiment, use a new adapter path, for example `--adapter-path adapters/sql-v2`. Keep the dataset fixed. Do not overwrite the first run if you want to compare it later.

## 7. Use the adapter and compare

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v1

~/.local/bin/qtms-validate uv run python evaluate.py \
  --adapter adapters/sql-v1 \
  --split valid --limit 20 --out results/after-valid.json
```

The prompt, base model and decoding are the same as before; the adapter is the changed part. Compare the saved `text_matches` counts and read the examples where predictions changed. The adapted model can improve, stay the same or get worse.

## 8. Make the evaluation stronger

Change one setting at a time using validation results. Once settings are settled, run both models on the untouched test split, using distinct result filenames and the same `--limit 100`. Avoid selecting settings from test results.

Execution-based evaluation is now implemented. Follow [Check SQL by running it](EXECUTION_EVALUATION.md) for the full walkthrough and the measured comparison.

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --out results/execution-before-v1.json

~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --adapter adapters/sql-v1 --out results/execution-after-v1.json
```

The evaluator generates SQL for eight curated questions and runs each answer on three small SQLite databases. A question passes only when its returned rows match on all three fixtures. These are constructed regression examples, not the original dataset databases or a held-out benchmark. The first comparison scored 6/8 before and 4/8 with the adapter, exposing regressions hidden by the earlier text-match score.

## Files to understand

| File | Job |
| --- | --- |
| `common.py` | Defines the shared model ID and prompt |
| `prepare_data.py` | Downloads, filters, splits and formats examples |
| `ask.py` | Generates SQL for one schema/question pair |
| `evaluate.py` | Saves predictions and the strict text-match score |
| `execution_cases.json` | Curated questions, reference queries, database rows and expected answers |
| `execution.py` | Executes restricted SQL and compares returned rows |
| `evaluate_execution.py` | Compares the original and adapted models using execution results |
| `test_execution.py` | Checks result semantics, the bike regression and execution restrictions |
| `train.yaml` | Controls the MLX-LM training run |
| `test_prepare_data.py` | Checks that table groups cannot cross split boundaries |
| `uv.lock` | Records dependency versions |

## Sources

- [MLX-LM repository](https://github.com/ml-explore/mlx-lm)
- [MLX-LM training guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
- [Qwen2.5-0.5B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
- [SQL Create Context dataset, CC BY 4.0](https://huggingface.co/datasets/b-mc2/sql-create-context)

Dataset revision: `9d80a6a118b838d9defc3798d659a54a2ac2ff37`. The downloaded/generated dataset and model artifacts stay outside Git; retain source attribution when sharing data-derived artifacts.
