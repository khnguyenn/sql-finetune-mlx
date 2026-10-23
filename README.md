# SQL fine-tuning on a Mac

Learn how to adapt a small language model to turn an English question and a database schema into SQL, then check whether the SQL returns the right results.

The project runs locally on Apple silicon using **MLX-LM** and **Qwen2.5-0.5B-Instruct**. LoRA trains a small adapter while keeping the original model weights frozen.

```text
Schema + question -> original model + optional adapter -> SQL
SQL + SQLite test rows -> actual results -> correctness check
```

Private repository: [khnguyenn/sql-finetune-mlx](https://github.com/khnguyenn/sql-finetune-mlx).

## Current local checkout

```text
/Users/kianguyen/Dev/sql-finetune-mlx
```

This checkout includes copies of the saved training data, adapters and experiment reports. The original checkout under Documents has been retained.

Git tracks the source, configurations and evaluation definitions. It excludes `data/`, `adapters/`, `results/` and `.venv/`. Another Git clone will need to recreate the generated data and adapters, or copy them from an existing checkout.

## Recorded results

The selected adapter is **v3 at 300 updates**, saved locally in `adapters/sql-v3`.

| Evaluation set | Original model | Selected v3 |
| --- | ---: | ---: |
| Original eight questions, used for development | 6/8 | 8/8 |
| Opened sixteen questions, subsequently used for development | 14/16 | 16/16 |
| Final twelve questions, not used for training or model selection | 7/12 | 12/12 |

A question passes only if its SQL returns the correct results on all three test databases. These are small, synthetic, single-table SQL tests. The date questions include this project's convention of storing month-name dates as text.

The first adapter performed worse than the original, and the next recipe tied on its new evaluation set. The full attempt history, selection rules and limits are recorded in [RESULTS.md](RESULTS.md) and [TRAINING_EXPERIMENTS.md](TRAINING_EXPERIMENTS.md).

## 1. Set up Python

Developed on an Apple M4 Mac with 16 GB memory. The project uses Python 3.12 and MLX-LM 0.32.2, with dependency versions recorded in `uv.lock`.

You need `uv` installed. Run:

```bash
cd /Users/kianguyen/Dev/sql-finetune-mlx
uv sync --locked
```

`uv` creates a Python environment in `.venv/` and installs the locked dependencies. Use `uv run` for project commands so they use that environment.

Check the GPU:

```bash
uv run python -c 'import mlx.core as mx; print(mx.default_device()); print(mx.metal.is_available())'
```

Expected on this Mac: `Device(gpu, 0)` and `True`.

Model commands below use `qtms-validate`, the shared work queue on this Mac. It prevents heavy jobs from overlapping; it is separate from MLX-LM. On another Mac without that local wrapper, run the `uv run ...` portion.

## 2. Try the original and trained models

Original model:

```bash
~/.local/bin/qtms-validate uv run python ask.py
```

Same model with the saved v3 adapter:

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v3
```

Both receive the same schema and question. Loading the adapter changes the model's behaviour; generating an answer does not train it.

The default question asks how many employees earn more than 80,000. A correct query is:

```sql
SELECT COUNT(*) FROM employees WHERE salary > 80000;
```

Try your own schema and question:

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v3 --schema 'CREATE TABLE products (name TEXT, price REAL);' --question 'What is the highest product price?'
```

The first model use downloads about 1 GB of weights to the shared Hugging Face cache. This Mac already has that cache; changing the checkout does not require another copy of the base model.

## 3. Understand the training data

The improved recipe uses **720 training examples** and **120 validation examples**, balanced across 15 SQL task types. These include row counts, non-null counts, distinct counts, filters, aggregates, grouping, ordering and the local date convention.

Each example pairs a schema and question with correct SQL:

```text
Schema:   CREATE TABLE trip (bike_id TEXT);
Question: How many different bikes appear in the trip records?
Target:   SELECT COUNT(DISTINCT bike_id) FROM trip;
```

The generator checks targets on databases containing duplicates, NULLs, boundaries and empty tables, using independently computed expected answers. Evaluation tables and exact schema/question pairs are excluded from the training examples.

The data already exists in this checkout. To generate it in a clean checkout:

```bash
mkdir -p data
uv run python prepare_curriculum.py --version 3
```

This writes `data/v3/train.jsonl`, `valid.jsonl` and `metadata.json`. The script refuses to replace an existing `data/v3/`; reuse the existing data when comparing training settings.

## 4. Train another adapter

The v3 configuration uses:

| Setting | Value | Purpose |
| --- | --- | --- |
| Learning rate | 0.00001 | Smaller updates than the first attempt |
| Updates | 300 | Number of training steps |
| Batch size | 1 | One example per update |
| LoRA layers / rank | 8 / 8 | Size and placement of the trainable adapter |
| Maximum sequence length | 512 tokens | Bound input size |
| Prompt masking | Enabled | Train on answer tokens |
| Gradient checkpointing | Enabled | Reduce peak memory |

Choose an unused output directory to preserve the selected adapter:

```bash
~/.local/bin/qtms-validate uv run mlx_lm.lora --config train-v3.yaml --adapter-path adapters/sql-v3-repeat
```

This starts a fresh adapter from the original model. It saves weights and configuration under the chosen directory, with snapshots every 100 updates. Give each later run a new directory name.

Training loss measures prediction of the labelled SQL tokens. Use execution results to decide whether the generated SQL actually improved. See [the experiment guide](TRAINING_EXPERIMENTS.md) for checkpoint selection.

## 5. Compare query results

Evaluate the original model:

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py --fixtures execution_holdout_v3.json --out results/manual-original.json
```

Evaluate the selected v3 adapter:

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py --adapter adapters/sql-v3 --fixtures execution_holdout_v3.json --out results/manual-v3.json
```

Reports save generated SQL, expected and actual rows, errors and per-question results. Existing reports are protected: choose a new output filename when repeating a command. To evaluate your repeat training run, change `--adapter` to its output directory.

The evaluator generates one query per question, then runs it on three disposable SQLite databases. It checks duplicates, NULLs, result shape and requested row ordering. Invalid or unsupported queries count as failures. Read-only restrictions and resource limits bound execution; details are in [EXECUTION_EVALUATION.md](EXECUTION_EVALUATION.md).

These twelve questions were reserved during the recorded v3 experiment. They are now opened evidence: repeating them does not make them a fresh test. Further model selection should use development examples and reserve another fixed set for the final comparison.

## Files to read

| File | Responsibility |
| --- | --- |
| `common.py` | Shared model ID and prompt |
| `ask.py` | Generate SQL for one schema/question pair |
| `prepare_curriculum.py` | Generate and check versioned training lessons |
| `train-v3.yaml` | Selected training recipe |
| `evaluate_execution.py` | Generate answers and score their execution results |
| `execution.py` | Restricted SQLite execution and row comparison |
| `execution_cases.json` | Original eight development questions |
| `execution_holdout.json` | Sixteen questions initially reserved for v2 |
| `execution_holdout_v3.json` | Twelve questions reserved for the recorded v3 comparison |
| `TRAINING_EXPERIMENTS.md` | Recipes, checkpoint choices and reproduction commands |
| `RESULTS.md` | Measured outcomes and evidence paths |
| `prepare_data.py`, `train.yaml`, `evaluate.py` | Original public-dataset experiment and text-match evaluation |

The original experiment uses [SQL Create Context](https://huggingface.co/datasets/b-mc2/sql-create-context), licensed CC BY 4.0, at revision `9d80a6a118b838d9defc3798d659a54a2ac2ff37`. The later curriculum is rule-generated within this project. Retain source attribution when sharing data-derived artifacts.

## Focused checks

Run the check relevant to what you changed:

```bash
# Training-data balance, target correctness and split separation
~/.local/bin/qtms-validate uv run python -m unittest test_curriculum.py

# SQLite result comparison and execution restrictions
~/.local/bin/qtms-validate uv run python -m unittest test_execution.py
```

## Common setup issues

- **Adapter not found:** run commands from the project folder and check that `adapters/sql-v3/adapters.safetensors` exists. A Git clone alone does not include trained weights.
- **Data already exists:** skip data generation and reuse that version for the next training run.
- **Report already exists:** choose a new output filename.
- **PyTorch not installed message:** this setup uses Transformers for tokenization and MLX for model computation; the message does not require installing PyTorch.
- **Different SQL text, same result:** execution evaluation compares returned data; text-match evaluation can count equivalent queries as mismatches.

References: [MLX-LM](https://github.com/ml-explore/mlx-lm), [LoRA training guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct).
