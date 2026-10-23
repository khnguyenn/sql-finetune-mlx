# Learn language-model fine-tuning with SQL

This project teaches a small language model to turn an English question into SQL.

You give it the table structure and a question:

```text
Table:    employees(name, salary)
Question: How many employees earn more than 80000?
```

It should generate:

```sql
SELECT COUNT(*) FROM employees WHERE salary > 80000;
```

We compare the original model with a version that received extra training, then run their SQL on small SQLite databases to check the answers.

Choose what you want to do:

- [Use the saved model now](#start-here-use-the-model-we-already-trained)
- [Train your own adapter](#train-your-own-adapter)
- [Set up a clean checkout](#set-up-another-checkout)

## Start here: use the model we already trained

Your project folder is:

```text
/Users/kianguyen/Dev/sql-finetune-mlx
```

The Python environment, training data and saved adapters are already available in this local checkout.

To try the selected model, run:

```bash
cd /Users/kianguyen/Dev/sql-finetune-mlx
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v3
```

This generates an answer. It does not start training.

To ask the original model the same default question:

```bash
~/.local/bin/qtms-validate uv run python ask.py
```

You can use the existing model immediately. Training a new version is a separate, optional step described below.

## What is being trained?

| Term | Meaning in this project |
| --- | --- |
| Original model | `Qwen2.5-0.5B-Instruct`, an existing model with language and SQL ability |
| Fine-tuning | Extra training on examples of questions and correct SQL |
| LoRA adapter | Small files containing the changes learned during training |
| Schema | The table names, columns and types supplied with a question |
| Inference | Asking the model to generate an answer |
| Checkpoint | A saved adapter snapshot from a particular training step |

The original model's weights remain frozen during LoRA training. To use the learned changes, load the original model with the adapter:

```text
Without --adapter: question + schema -> original model -> SQL
With --adapter:    question + schema -> original model + learned adapter -> SQL
```

The selected adapter lives in `adapters/sql-v3/`.

## What improved?

The recorded final comparison used twelve new questions that were excluded from training and checkpoint selection:

| Model | Questions answered correctly |
| --- | ---: |
| Original model | 7/12 |
| Original model with the selected v3 adapter | 12/12 |

Each question had three small test databases. Its generated SQL had to return the right results on all three.

For example, the original model omitted `GROUP BY department` when asked for totals per department. The adapted model included it and returned a separate total for each department.

These results cover small, synthetic, single-table SQL tasks. Two questions test this project's date-storage convention. Full results, earlier failed attempts and evaluation limits are in [RESULTS.md](RESULTS.md).

## What each tool does

| Tool | Job |
| --- | --- |
| `uv` | Creates the Python environment and runs project commands |
| MLX | Performs model computations on the Apple GPU |
| MLX-LM | Loads the model, trains adapters and generates text |
| SQLite | Executes the generated SQL so we can check its results |
| `qtms-validate` | Queues heavy jobs on this Mac so they do not overlap |

`qtms-validate` is a local work-queue wrapper, separate from MLX-LM. On another Mac without that wrapper, run the `uv run ...` portion of the model commands.

## Try your own question

Supply both the table definition and the question:

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v3 --schema 'CREATE TABLE products (name TEXT, price REAL);' --question 'What is the highest product price?'
```

The expected query is:

```sql
SELECT MAX(price) FROM products;
```

`ask.py` prints SQL. It does not connect to your own databases.

## Train your own adapter

Use this section when you want to learn by making another training run.

### 1. Check that the training data exists

The current data is in `data/v3/`:

| File | Purpose |
| --- | --- |
| `train.jsonl` | 720 examples available for learning |
| `valid.jsonl` | 120 examples used to check training |
| `metadata.json` | Dataset version, example counts and evaluation-file hash |

Each training example contains a schema, an English question and the correct SQL. The examples cover 15 SQL skills equally, including ordinary counts, unique counts, filters, grouping and ordering.

The generator checks the target SQL against independently calculated answers, including duplicates, NULLs and empty tables.

If `data/v3/` already exists, reuse it. In a clean checkout where it is missing, create it with:

```bash
mkdir -p data
uv run python prepare_curriculum.py --version 3
```

The script refuses to replace an existing dataset.

### 2. Train into a new directory

Run:

```bash
~/.local/bin/qtms-validate uv run mlx_lm.lora --config train-v3.yaml --adapter-path adapters/my-sql-run-01
```

Choose an unused directory name for each run. This keeps the selected `adapters/sql-v3` adapter available for comparison.

The command loads the original model and trains a fresh adapter using the settings in `train-v3.yaml`:

| Setting | Value | Meaning |
| --- | --- | --- |
| Learning rate | 0.00001 | Controls the size of training updates |
| Training steps | 300 | Number of updates |
| Batch size | 1 | One training example per update |
| LoRA layers / rank | 8 / 8 | Where the adapter is attached and its size |
| Maximum input length | 512 tokens | Limits the length of each example |

With batch size 1, 300 steps is less than a full pass through 720 examples.

Training saves `adapters.safetensors`, `adapter_config.json` and snapshots every 100 steps in your chosen output directory. A lower training loss means better prediction of the training answer text; execution checks tell us whether the SQL produces the right results.

### 3. Try your new adapter

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/my-sql-run-01
```

Change the directory in this command if you chose a different name.

### 4. Compare it with the original

Run both models on the same eight development questions:

```bash
# Original model
~/.local/bin/qtms-validate uv run python evaluate_execution.py --out results/my-original-dev.json

# Your new adapter
~/.local/bin/qtms-validate uv run python evaluate_execution.py --adapter adapters/my-sql-run-01 --out results/my-sql-dev.json
```

Compare `correct_cases` in the two JSON reports. Read the saved SQL and failed fixtures to understand mistakes. Choose new report filenames when repeating a comparison; the script protects existing files.

The evaluator creates disposable SQLite databases and compares returned rows. It preserves duplicates and checks ordering when requested. Invalid or unsupported SQL counts as a failure.

Use development questions to choose training settings or checkpoints. Reserve a separate set of new questions for the final comparison. The project's recorded twelve-question test has already been inspected, so rerunning it does not make it a new, untouched test.

[TRAINING_EXPERIMENTS.md](TRAINING_EXPERIMENTS.md) explains how we selected v3. [EXECUTION_EVALUATION.md](EXECUTION_EVALUATION.md) explains the SQLite checks and execution restrictions.

## Set up another checkout

The current Dev checkout is ready to use. For another checkout, you need an Apple silicon Mac and `uv`.

From the project folder, run:

```bash
uv sync --locked
uv run python -c 'import mlx.core as mx; print(mx.default_device()); print(mx.metal.is_available())'
```

`uv` creates `.venv/` using Python 3.12 and the dependency versions in `uv.lock`. On this Mac, the GPU check returns `Device(gpu, 0)` and `True`. The setup was verified on an Apple M4 with 16 GB memory.

Git includes the source and configuration files. It excludes:

- `data/`: generated training data.
- `adapters/`: learned adapter files.
- `results/`: local experiment reports.
- `.venv/`: the local Python environment.

The saved artifacts were copied into this Dev checkout. Another clone must copy them from an existing checkout or generate data and train its own adapter. The original model is downloaded from Hugging Face when needed and cached outside the repository.

Private repository: [khnguyenn/sql-finetune-mlx](https://github.com/khnguyenn/sql-finetune-mlx).

## Where to look in the code

| File | Responsibility |
| --- | --- |
| `common.py` | Defines the shared model ID and prompt |
| `ask.py` | Generates SQL for one question |
| `prepare_curriculum.py` | Builds and checks training examples |
| `train-v3.yaml` | Controls the selected training recipe |
| `evaluate_execution.py` | Connects model generation to result checking |
| `execution.py` | Runs restricted SQL and compares returned rows |
| `execution_cases.json` | The original eight development questions |
| `execution_holdout.json` | Sixteen questions first used to evaluate v2 |
| `execution_holdout_v3.json` | Twelve questions used for the recorded v3 comparison |

Start by reading `ask.py`, then `common.py`. When those make sense, read `train-v3.yaml` and `prepare_curriculum.py`.

## Common questions

**Do I need to retrain before using the model?**

No. This checkout already contains `adapters/sql-v3`.

**Why did a previous fine-tuned version get worse?**

Training changes behaviour, but improvement must be measured. Our first adapter regressed; clearer examples, more varied wording and smaller updates helped the later recipe. See [the experiment history](TRAINING_EXPERIMENTS.md).

**Why is there a PyTorch warning?**

This project uses Transformers for tokenization and MLX for model computation. The warning does not require installing PyTorch.

**What if a dataset or report already exists?**

Reuse the dataset and choose a new report filename. Use a different adapter directory for a new training run.

**How do I check code changes?**

For training-data changes, run `~/.local/bin/qtms-validate uv run python -m unittest test_curriculum.py`. For SQL execution changes, run the corresponding `test_execution.py` file through the same queue.

## Data and references

The first experiment used [SQL Create Context](https://huggingface.co/datasets/b-mc2/sql-create-context), licensed CC BY 4.0, at revision `9d80a6a118b838d9defc3798d659a54a2ac2ff37`. The improved curriculum is rule-generated in this project. The original public-dataset scripts remain available as `prepare_data.py`, `train.yaml` and `evaluate.py`.

References: [MLX-LM](https://github.com/ml-explore/mlx-lm), [LoRA training guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct).
