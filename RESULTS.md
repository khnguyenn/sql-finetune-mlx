# First experiment: 2026-10-23

Completed locally on Apple M4 with 16 GB unified memory, Python 3.12.14, MLX-LM 0.32.2 and the Metal GPU.

## What ran

- Prepared 1,000 training examples, 100 validation examples and 100 reserved test examples. Confirmed no table-name overlap; the longest selected conversation was 174 tokens.
- Ran two focused data-split regression checks successfully.
- Generated SQL using the original Qwen2.5-0.5B-Instruct model.
- Saved a baseline on the first 20 validation examples using greedy decoding.
- Trained `adapters/sql-v1` for 100 updates with batch size 1. The run trained 1.466 million parameters, 0.297% of 494.033 million model parameters. The final adapter is approximately 5.61 MiB.
- Generated SQL using the same model with the saved adapter, then evaluated the same 20 validation examples.

## Results

| Metric | Before | After |
| --- | ---: | ---: |
| Normalised SQL text matches | 5/20 | 9/20 |

The metric ignores repeated whitespace and a final semicolon. It counts equivalent queries with different text as mismatches; it does not measure query execution accuracy. Several gains were changes from single quotes to the dataset's double-quote convention. This small validation comparison does not establish general SQL improvement.

The training command reported validation loss of 1.282 at its initial evaluation and 0.169 at update 100, evaluating ten validation batches per check. These reported losses do not establish generated-query correctness.

## Actual before and after

Same prompt in both cases:

```text
Schema: CREATE TABLE employees (name TEXT, salary INTEGER);
Question: How many employees earn more than 80000?
```

Original model output:

```sql
SELECT COUNT(name) FROM employees WHERE salary > 80000
```

Same model with adapter:

```sql
SELECT COUNT(*) FROM employees WHERE salary > 80000
```

`COUNT(name)` excludes rows where the name is NULL; `COUNT(*)` counts all matching employees. The schema permits NULL names, so the distinction matters.

## A regression that the aggregate score hides

Validation example 8 asks for the number of unique bikes in a trip table.

```sql
-- Before: counts unique bikes
SELECT COUNT(DISTINCT bike_id) FROM trip

-- After: counts every trip
SELECT COUNT(*) FROM trip
```

Executed both on an illustrative local in-memory SQLite fixture with bike IDs `bike-a`, `bike-a`, `bike-b`. The original query returned 2, correctly; the adapted query returned 3. These are constructed demonstration rows, not the original dataset database. See `results/unique-bikes-fixture.json` for the saved check.

## Saved evidence

- `data/metadata.json`: pinned dataset revision and split sizes
- `results/before-valid.json`: original predictions and scores
- `results/after-valid.json`: adapted predictions and scores
- `results/unique-bikes-fixture.json`: execution check for the unique-bikes regression
- `adapters/sql-v1/adapter_config.json`: actual training settings
- `adapters/sql-v1/adapters.safetensors`: trained adapter

The test split has not been scored.

## Execution-based follow-up

The existing model and `sql-v1` adapter were evaluated on eight curated questions with three constructed SQLite fixtures per question. A question passes only if every fixture returns the correct rows. Fixture definitions are committed in `execution_cases.json`; this is a diagnostic regression suite, not a held-out benchmark or the original populated dataset databases.

| Question | Original | With adapter |
| --- | --- | --- |
| Unique bikes | Pass | Fail |
| Employee count | Fail | Pass |
| Maximum price | Pass | Pass |
| Age filter | Pass | Pass |
| Text date filter | Fail | Pass |
| Completed-order total | Pass | Fail |
| Grouped sales | Pass | Fail |
| Price ordering | Pass | Fail |
| **All-fixture passes** | **6/8** | **4/8** |

Reports: `results/execution-before-v1.json` and `results/execution-after-v1.json`. Both record fixture hash `eae1740438eae4e3108558bf7f9308f77bd1c41d5a7d06cc3c57064966806b6e`. The focused evaluator regression checks passed.

An independent read-only security review found a JSON reporting failure for BLOB query results. Unsupported result types are now counted as query failures, and streamed result payloads are capped at 65,536 encoded bytes per query. All thirteen focused evaluator checks pass, including regressions for report serialization and payload limits.

The bike answer passes the duplicate, NULL and empty fixtures before fine-tuning; with the adapter it passes only the empty fixture. The completed-order answer changes the stored status value from `completed` to `Completed`, losing qualifying rows. The grouped-sales and price-ordering answers become invalid SQL, and all their fixtures are scored as failures.

The available training answers contain 23 `COUNT(*)` examples, 104 other non-DISTINCT count examples and 2 `COUNT(DISTINCT ...)` examples. This imbalance and ambiguous count labels are possible contributors to the bike regression, not established causes. Training optimized answer-token prediction rather than executed results. See [the walkthrough](EXECUTION_EVALUATION.md) for the mechanism and evidence limits.
