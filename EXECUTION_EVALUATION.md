# Check SQL by running it

The private repository is [khnguyenn/sql-finetune-mlx](https://github.com/khnguyenn/sql-finetune-mlx). The first execution comparison is complete on the existing Qwen model and `sql-v1` adapter.

## 1. Define a question with known answers

`execution_cases.json` contains eight manually reviewed questions. Each includes a schema, a reference query, three sets of database rows and explicit expected results.

For example:

```text
Question: From the trip record, find the number of unique bikes.
Rows:     bike-a, bike-a, bike-b
Expected: 2
```

The original public dataset contains schemas and queries, not the original populated databases. These are constructed test databases. They let us test meaningful behaviour, but passing them does not prove correctness for every possible database.

## 2. Generate one SQL query per question

`evaluate_execution.py` uses `common.messages()` to give the model exactly the same kind of prompt as training: schema plus question. The fixture rows, reference query and expected results are not included in that prompt.

The model generates a single query for each question using greedy decoding. That same query is then checked on all three databases for the question.

## 3. Create a disposable database

`execution.run_query()` creates an in-memory SQLite database for one fixture. It creates the reviewed schema and inserts the fixture rows using parameters.

For model-generated SQL, the connection permits reads from the fixture's table and a small set of built-in functions. It rejects writes, attachments, PRAGMAs, metadata reads, extension loading and multiple statements. SQLite instruction/time, SQL length, value length and output-row limits bound supported work. Rows are streamed with an aggregate encoded-row payload limit of 65,536 bytes per query; binary values and non-finite numbers are reported as unsupported query results instead of breaking JSON report generation. This is a restricted local fixture runner, not a general-purpose SQL service.

## 4. Compare returned rows

`execution.grade_query()` first runs the reference SQL and checks that it agrees with the handwritten expected results. A broken reference fixture stops evaluation, rather than being counted against the model.

It then runs the generated query and compares the actual rows and column count with the reference result:

- For questions without an order requirement, row order can differ. Duplicate rows still count, so `DISTINCT` cannot silently remove legitimate duplicates.
- For questions explicitly requesting sorted output, row order must match.
- NULL values and empty results are included.
- A query error or execution limit counts as a failed fixture.
- A question passes only if every fixture passes. Passing the empty table alone is insufficient.

This measures result agreement on the supplied fixtures. It does not compare column aliases or prove SQL equivalence for all data. The current fixtures use values that compare directly without floating-point tolerances.

## 5. Compare the original model and adapter

From the project directory:

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --out results/execution-before-v1.json

~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --adapter adapters/sql-v1 \
  --out results/execution-after-v1.json
```

These commands already ran. Choose new result filenames when repeating them, because the script preserves existing reports.

To check just the bike question:

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --adapter adapters/sql-v1 --case unique-bikes \
  --out results/bikes-execution-v1.json
```

Saved reports include generated SQL, expected and actual rows, errors, pass/fail for each fixture, and a hash identifying the exact fixture definitions.

## Actual results

Each row passes only if all three databases return the right result.

| Question | Original | With adapter |
| --- | --- | --- |
| Unique bikes | Pass | Fail |
| Employee count | Fail | Pass |
| Maximum price | Pass | Pass |
| Age filter | Pass | Pass |
| Text date filter | Fail | Pass |
| Completed-order total | Pass | Fail |
| Sales grouped by category | Pass | Fail |
| Products ordered by price | Pass | Fail |
| **Total** | **6/8** | **4/8** |

This is a small diagnostic regression suite containing known examples, including the bike regression that motivated it. It is not an untouched held-out benchmark, and its denominator differs from the earlier 20-question text-match comparison. The reserved 100-row test split remains unscored.

## Why unique bikes got worse

The observed change is concrete:

```sql
-- Original model: 2 on bike-a, bike-a, bike-b
SELECT COUNT(DISTINCT bike_id) FROM trip

-- With adapter: 3 on the same rows
SELECT COUNT(*) FROM trip
```

`COUNT(DISTINCT bike_id)` counts different non-NULL IDs. `COUNT(*)` counts every trip row. Both return 0 on an empty table, which explains why testing only empty or all-distinct rows can miss the bug.

Fine-tuning updates shared adapter parameters to make the training answer tokens more likely. The training objective does not execute SQL or reward the right count. The same parameter updates can help one question and weaken a distinction the original model handled correctly.

The original weights remain frozen with LoRA. This behaviour changes when the adapter is loaded; omitting `--adapter` uses the original model again, including its original answer to the bike question.

We inspected the available 1,000 training answers: 23 use `COUNT(*)`, 104 use other non-DISTINCT counts, and only 2 use `COUNT(DISTINCT ...)`. Some references use ordinary counts despite wording such as "different amounts" or "different teams", which can also make the desired distinction ambiguous without the original database constraints.

This makes overgeneralising a common count pattern a plausible explanation. It is not a proven causal diagnosis: the run used only 100 updates, and we have not established which of those examples affected this particular output or isolated the effects of data balance, learning rate and checkpoint choice. Falling token loss and better text matching do not guarantee better result correctness.

The new evaluator makes that trade-off visible before another training experiment. A later experiment could add carefully labelled distinct-count examples and compare checkpoints using execution results while keeping the test split reserved.

## Verification and reading path

The focused check is:

```bash
~/.local/bin/qtms-validate uv run python -m unittest test_execution.py
```

It covers the actual unique-bikes regression, duplicate preservation, row ordering, empty result shapes, bad reference fixtures, read-only restrictions, multiple statements, runaway queries, output limits, report serialization and SQL errors. An independent read-only review found that BLOB results could abort JSON report generation; the focused regression reproduced that issue before the fix, and all thirteen checks pass with the fix.

Read `execution_cases.json` first to see the data, `execution.py` next to see how one answer is judged, and `evaluate_execution.py` last to see model generation connected to scoring. No new Python dependency is needed; Python includes SQLite support.

Sources: [Python SQLite API](https://docs.python.org/3.12/library/sqlite3.html), [SQLite aggregate semantics](https://www.sqlite.org/lang_aggfunc.html), [MLX-LM training loss](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py).
