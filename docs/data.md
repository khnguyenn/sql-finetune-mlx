# Data inventory

The project has three versioned training datasets, three committed execution suites, saved adapters and local experiment reports. This inventory describes their contents and roles; none of the generated conversations or trained adapters is included in a fresh Git clone.

## Training and validation datasets

| Version | Train / validation / test conversations | Source and use |
| --- | --- | --- |
| V1, `data/` | 1,000 / 100 / 100 | Public SQL Create Context sample for the first adapter. The 100-example test split remains reserved and unscored. |
| V2, `data/v2/` | 672 / 112 / none | Fourteen rule-generated SQL families, 48 training and 8 validation examples each. Used for the v2 adapter. |
| V3, `data/v3/` | 720 / 120 / none | Fifteen families, with counting paraphrases and literal-text dates. Used for the selected v3 adapter and as the RAG corpus. |

V1 was selected from 78,577 source records at dataset revision `9d80a6a118b838d9defc3798d659a54a2ac2ff37`; 76,560 met the recorded eligibility checks. The selection deduplicates schema/question pairs, retains short single-table SELECT examples and assigns whole table-name groups to disjoint splits. The source has schemas, questions and answer SQL, not the original populated databases. Source: [SQL Create Context](https://huggingface.co/datasets/b-mc2/sql-create-context), CC BY 4.0.

V2/v3 use synthetic table names and six column-name groups representing items, assets, records, members, devices and products. Training and validation use distinct table names. Generated reference SQL is executed against independently calculated Python answers on duplicate, NULL, boundary and empty data. The generator checks token length and separation from the relevant committed evaluation tables. These are variations of a small set of SQL patterns, not broad database coverage.

### The fifteen v3 task families

Examples below use the actual generated schema `lesson_v3_train_0(item_name TEXT, amount REAL, status TEXT)`; the date family has a separate date column.

| Family | Requested operation | Target pattern |
| --- | --- | --- |
| `rows` | Count every row | `COUNT(*)` |
| `filtered_count` | Count rows with amount above a threshold | `COUNT(*) WHERE amount > -15` |
| `distinct_count` | Count different items | `COUNT(DISTINCT item_name)` |
| `nonnull_count` | Count populated item names | `COUNT(item_name)` |
| `maximum` | Highest amount | `MAX(amount)` |
| `minimum` | Lowest amount | `MIN(amount)` |
| `average` | Average amount | `AVG(amount)` |
| `filtered_sum` | Total amount for paid records | `SUM(amount) WHERE status = 'paid'` |
| `group_sum` | Separate amount total for each status | `status, SUM(amount) GROUP BY status` |
| `group_count` | Separate row count for each status | `status, COUNT(*) GROUP BY status` |
| `ascending` | Item names from lowest to highest amount | `ORDER BY amount ASC` |
| `descending` | Item names from highest to lowest amount | `ORDER BY amount DESC` |
| `text_filter` | Item names with paid status | `WHERE status = 'paid'` |
| `numeric_filter` | Item names above an amount threshold | `WHERE amount > -15` |
| `literal_date` | Match a stored month-name date | `WHERE event_date = 'January 2, 2005'` |

Month-name date storage is this curriculum's local convention. The schema's `TEXT` type alone does not communicate that convention to a model. No joins, subqueries or multi-table relations are represented in these generated families.

### Conversation format

Each JSONL line contains `messages`, and generated versions also retain `family` and `table` metadata. The sequence is system instruction → user schema/question → assistant target SQL. MLX-LM trains on assistant answer tokens with prompt masking enabled.

```json
{
  "family": "rows",
  "table": "lesson_v3_train_0",
  "messages": [
    {"role": "system", "content": "Write a SQLite SELECT query for the given schema and question. Return only SQL, without explanations or Markdown."},
    {"role": "user", "content": "Schema:\nCREATE TABLE lesson_v3_train_0 (item_name TEXT, amount REAL, status TEXT);\n\nQuestion:\nHow many rows are in lesson_v3_train_0?"},
    {"role": "assistant", "content": "SELECT COUNT(*) FROM lesson_v3_train_0"}
  ]
}
```

The RAG retriever reuses the 720 v3 training conversations. It does not index validation/test answers or fixture rows. Answers and family metadata are excluded from ranking; the chosen examples' answers become prompt context.

## Execution datasets

| Suite | Questions / fixture databases | Content and current role |
| --- | --- | --- |
| `fixtures/execution_cases.json` | 8 / 24 | Unique bikes, employee counts, maximum price, numeric/text-date filters, status totals, grouped sales and ordering. Original development diagnostics. |
| `fixtures/execution_holdout.json` | 16 / 48 | Separate schemas and paraphrases for counts, aggregates, filtering, grouping and ordering. Initially v2 holdout, then opened for v3 development. |
| `fixtures/execution_holdout_v3.json` | 12 / 36 | Badge/guest counts, donations, receipt references, contestant/engine order, show/sailing dates, department points, work-log counts, bill totals and minimum depth. Original v3 holdout; now an opened comparison suite. |

Each case stores an ID, question, `CREATE TABLE` schema, allowed table name, reference SQL, ordering requirement and three fixtures. A fixture contains row values plus handwritten expected query results. It is instantiated in memory when grading; there is no persistent `.sqlite` database file to download.

The original 8 plus opened 16 form the 24-question development population used for v3 checkpoint selection. The files retain their historical `holdout` names; that does not make them untouched tests today. There is no exact schema/question pair or table-name overlap between the generated curriculum and these suites, but there is substantial task-template overlap.

## Generate missing datasets

Run from the repository root. V3 is the default operational dataset:

```bash
mkdir -p data
uv run python -m sql_finetune.prepare_curriculum --version 3
```

For the historical v2 dataset, use `--version 2`. Both commands refuse to overwrite the selected version. `metadata.json` records split sizes, family counts, seed 42 and the evaluation-file hash.

The historical public-data generator is `uv run python -m sql_finetune.prepare_data`. It requires `data/` to be absent, so it must run before generating v2/v3 in a clean checkout. Do not delete an existing data directory to rerun it; copy existing artifacts or use a separate checkout for historical reproduction. The old text-match evaluator is `python -m sql_finetune.evaluate`; it reads the original public-data splits and does not measure execution correctness.

## Model and report assets

| Asset | Contents | Git availability |
| --- | --- | --- |
| Hugging Face cache | Qwen2.5-0.5B-Instruct (~1 GB) and Qwen2.5-3B-Instruct (~6.17 GB) weights, tokenizers and configs | Outside the repository; downloaded on first use |
| `adapters/sql-v1` | First 100-update adapter and configuration | Local only |
| `adapters/sql-v2` | Selected 100-update adapter and retained training snapshots | Local only |
| `adapters/sql-v3` | Selected 300-update adapter and retained snapshots | Local only |
| `results/` | Raw predictions, expected/actual rows, errors, model revisions, prompts, selection records and logs | Local only; summary tables and full twelve-case SQL are preserved in [experiments](experiments.md) |

The selected adapter weights are approximately 5.61 MiB and depend on the 0.5B checkpoint. A standalone merged v3 model, original public-dataset databases, independent large SQL benchmark, production schema catalogue and production data are not supplied.
