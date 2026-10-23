# V3 adapter, retrieved examples and a larger model

Run date: 2026-10-23. All generations ran locally through MLX-LM on the same Mac.

## Results

V3 passed **12/12**, the larger original model **11/12**, the original model with retrieved examples **10/12 after code-fence-only cleanup**, and the original 0.5B model **7/12**.

| Variant | Strict raw-response passes | SQL passes after fence-only cleanup |
| --- | ---: | ---: |
| Original 0.5B | 7/12 | 7/12 |
| 0.5B + RAG | 7/12 | 10/12 |
| Original 3B | 11/12 | 11/12 |
| 0.5B + v3 | 12/12 | 12/12 |

The following table uses the separate SQL diagnostic. A pass requires correct results on all three fixture databases. **†** marks a response wrapped in Markdown; its raw strict result fails even when the SQL is correct.

| Question | Original 0.5B | 0.5B + RAG | Original 3B | 0.5B + v3 |
| --- | --- | --- | --- | --- |
| How many different badge holders entered? | Pass | Pass | Pass | Pass |
| How many different guests visited the hotel? | Pass | Pass | Pass | Pass |
| How many donations exceed 100? | Pass | Pass† | Pass | Pass |
| Count receipts with a non-null reference. | Pass | Pass | Pass | Pass |
| List entrant names from lowest mark to highest. | Fail | Fail | Pass | Pass |
| Give model names ordered by efficiency from largest to smallest. | Pass | Pass | Pass | Pass |
| Which presenter has show_date May 16, 2004? | Fail | Pass | Pass | Pass |
| List captain for departure_date October 3, 2010. | Fail | Pass | Fail | Pass |
| Show each department and the sum of earned points. | Fail | Pass† | Pass | Pass |
| For every team, show how many work log rows it has. | Fail | Fail† | Pass | Pass |
| What is the total charge of bills with status 'settled'? | Pass | Pass† | Pass | Pass |
| What is the minimum depth? | Pass | Pass | Pass | Pass |

**Interpretation:** the 3B model fixes the original model's ordering and grouping mistakes without extra project training. Its only failed case changes `October 3, 2010` to `2010-10-03`, which does not match the fixture's stored month-name text. It preserves the other question's month-name date, so its date behaviour is not consistent across these two prompts.

RAG corrects both date cases and the department grouping query. It still outputs descending order for a lowest-to-highest question and a distinct-team count instead of counts per team. Relevant examples were retrieved for both failures. Three otherwise-correct RAG responses fail only because of code fences; the fourth fenced response also has the wrong SQL.

Excluding the two date cases as a descriptive diagnostic, the SQL scores are original **7/10**, RAG **8/10**, larger **10/10**, and v3 **10/10**. V3's one-question lead over 3B on this set is therefore a date-format convention result, rather than evidence of stronger general SQL reasoning.

Both publisher checkpoints ran without quantization. The larger checkpoint required about 6.17 GB of weight downloads and is now cached on this Mac. RAG prompts used 231–309 tokens versus 52–66 for the original and v3 prompts. No controlled latency benchmark was performed.

## Generated SQL and expected queries

Only the original Markdown fence is omitted from the inline SQL display below; **†** records its presence. Full raw responses remain in the JSON reports. No SQL token was corrected.

| Question ID | Expected query | Original 0.5B | 0.5B + RAG | Original 3B | 0.5B + v3 |
| --- | --- | --- | --- | --- | --- |
| badge-holders | `SELECT COUNT(DISTINCT badge_code) FROM entry_scans` | `SELECT COUNT(DISTINCT badge_code) FROM entry_scans` | `SELECT COUNT(DISTINCT badge_code) FROM entry_scans` | `SELECT COUNT(DISTINCT badge_code) FROM entry_scans` | `SELECT COUNT(DISTINCT badge_code) FROM entry_scans` |
| different-guests | `SELECT COUNT(DISTINCT guest_name) FROM hotel_visits` | `SELECT COUNT(DISTINCT guest_name) FROM hotel_visits` | `SELECT COUNT(DISTINCT guest_name) FROM hotel_visits` | `SELECT COUNT(DISTINCT guest_name) FROM hotel_visits` | `SELECT COUNT(DISTINCT guest_name) FROM hotel_visits` |
| large-donations | `SELECT COUNT(*) FROM donations WHERE amount > 100` | `SELECT COUNT(*) FROM donations WHERE amount > 100` | `SELECT COUNT(*) FROM donations WHERE amount > 100`† | `SELECT COUNT(*) FROM donations WHERE amount > 100` | `SELECT COUNT(*) FROM donations WHERE amount > 100` |
| assigned-reference | `SELECT COUNT(reference) FROM receipts` | `SELECT COUNT(reference) FROM receipts WHERE reference IS NOT NULL` | `SELECT COUNT(reference) FROM receipts` | `SELECT COUNT(*) FROM receipts WHERE reference IS NOT NULL` | `SELECT COUNT(reference) FROM receipts` |
| lowest-mark-first | `SELECT entrant FROM contestants ORDER BY mark ASC` | `SELECT entrant FROM contestants ORDER BY mark DESC` | `SELECT entrant FROM contestants ORDER BY mark DESC` | `SELECT entrant FROM contestants ORDER BY mark ASC` | `SELECT entrant FROM contestants ORDER BY mark ASC` |
| efficiency-order | `SELECT model FROM engines ORDER BY efficiency DESC` | `SELECT model FROM engines ORDER BY efficiency DESC` | `SELECT model FROM engines ORDER BY efficiency DESC` | `SELECT model FROM engines ORDER BY efficiency DESC` | `SELECT model FROM engines ORDER BY efficiency DESC` |
| show-date | `SELECT presenter FROM shows WHERE show_date = 'May 16, 2004'` | `SELECT presenter FROM shows WHERE show_date = '2004-05-16'` | `SELECT presenter FROM shows WHERE show_date = 'May 16, 2004'` | `SELECT presenter FROM shows WHERE show_date = 'May 16, 2004'` | `SELECT presenter FROM shows WHERE show_date = 'May 16, 2004'` |
| departure-date | `SELECT captain FROM sailings WHERE departure_date = 'October 3, 2010'` | `SELECT captain FROM sailings WHERE departure_date = '2010-10-03'` | `SELECT captain FROM sailings WHERE departure_date = 'October 3, 2010'` | `SELECT captain FROM sailings WHERE departure_date = '2010-10-03'` | `SELECT captain FROM sailings WHERE departure_date = 'October 3, 2010'` |
| department-points | `SELECT department, SUM(earned) FROM points GROUP BY department` | `SELECT department, SUM(earned) FROM points` | `SELECT department, SUM(earned) FROM points GROUP BY department`† | `SELECT department, SUM(earned) FROM points GROUP BY department` | `SELECT department, SUM(earned) FROM points GROUP BY department` |
| work-log-counts | `SELECT team, COUNT(*) FROM work_logs GROUP BY team` | `SELECT COUNT(DISTINCT team) FROM work_logs` | `SELECT COUNT(DISTINCT team) AS num_teams FROM work_logs;`† | `SELECT team, COUNT(*) FROM work_logs GROUP BY team` | `SELECT team, COUNT(*) FROM work_logs GROUP BY team` |
| settled-bills | `SELECT SUM(charge) FROM bills WHERE status = 'settled'` | `SELECT SUM(charge) FROM bills WHERE status = 'settled'` | `SELECT SUM(charge) FROM bills WHERE status = 'settled'`† | `SELECT SUM(charge) FROM bills WHERE status = 'settled'` | `SELECT SUM(charge) FROM bills WHERE status = 'settled'` |
| minimum-depth | `SELECT MIN(depth) FROM soundings` | `SELECT MIN(depth) FROM soundings` | `SELECT MIN(depth) FROM soundings` | `SELECT MIN(depth) FROM soundings` | `SELECT MIN(depth) FROM soundings` |

## What changed between the four variants

| Variant | Model | Additional input or learned weights |
| --- | --- | --- |
| Original | Qwen/Qwen2.5-0.5B-Instruct | Schema and question only |
| V3 | Same 0.5B checkpoint | Existing selected `adapters/sql-v3`, unchanged |
| RAG | Same 0.5B checkpoint | Three automatically retrieved training examples |
| Larger | Qwen/Qwen2.5-3B-Instruct | Schema and question only; no project fine-tuning |

Both original checkpoints are instruction models. “No fine-tuning” here means no additional project training. They already received training from their publisher. Increasing nominal model size from 0.5B to 3B also changes the publisher's checkpoint; this experiment cannot attribute every difference solely to parameter count.

The model revisions are pinned:

- 0.5B: `7ae557604adf67be50417f59c2c2f167def9a775`
- 3B: `aa8e72537993ba99e69dfaafa59ed015b17504d1`

Sources: [official 3B model card](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct), [MLX-LM](https://github.com/ml-explore/mlx-lm).

## Retrieval implementation

`retrieval.ExampleRetriever` indexes the 720 examples in `data/v3/train.jsonl`. This is the same available training corpus used for v3, rather than a new collection containing answers to these twelve questions. The generator produced the examples; they are trusted project data.

`retrieve()` ranks the schema/question text with lexical BM25, using `k1=1.5`, `b=0.75` and lowercase alphanumeric tokens. SQL answers and family labels are excluded from ranking. It returns the top three examples, breaking ties by their source line number and excluding an identical input. There is no embedding model, vector database, hand-picked example selection or new Python dependency. Similar training examples can occupy multiple retrieval slots; no diversity reranker was used.

`retrieval_messages()` adds those examples, including their training SQL, before the target schema/question. The system instruction stays the same. Full target schemas are already supplied, so this retrieves examples rather than selecting database tables.

The corpus has no exact question text or table-name overlap with these twelve cases. It still shares SQL task patterns with them. The model never receives evaluation fixture rows, reference SQL or expected results. Its prompt is saved for inspection.

## Evaluation rules and evidence

- Fixed questions: `execution_holdout_v3.json`, twelve questions with three fixture databases each.
- Fixture SHA256: `8b476283687a05cba94c7d781851552a1e08f059ba1feebcb1f9d96d8c148db6`.
- Corpus SHA256: `d9f99415b9040a180ed5eb33de5505493bcbd474e6dc26fee7fbb3a781e897a1`.
- Greedy generation: temperature 0, seed 42, at most 128 generated tokens. One generation per question, no retries or SQL repairs.
- A question passes only when all three fixtures return the expected rows, including duplicates and required ordering.
- The existing `execution.py` restrictions are unchanged. All generated SQL runs only inside restricted, disposable in-memory databases.
- The original strict metric executes the raw response. Markdown code fences therefore fail the SQL-only response contract.
- A separate **post-hoc formatting diagnostic** removes one whole-response SQL or untagged code fence, then executes the inner text using the same restrictions. It does not change SQL, prompts, model outputs or strict reports. It rejects surrounding prose and multiple fenced blocks.

The retrieval method, settings and retrieved examples were saved in `results/comparison-v3-rag-3b/plan.json` before generating any answers. No retrieval or prompt settings were adjusted after scoring. All four variants were freshly evaluated in separate model processes, rather than mixing new runs with older predictions.

Local files under `results/comparison-v3-rag-3b/`:

- `plan.json`: fixed protocol, revisions, source hashes and retrieved examples.
- `original.json`, `v3.json`, `rag.json`, `larger.json`: raw generations, exact prompts, retrieved examples, model revision and fixture outcomes.
- `comparison.json`: strict scores and the separate formatting diagnostic.

Runtime artifacts remain ignored by Git. This document preserves the result tables and SQL in the private repository.

## Reproduce the comparison

Use the existing local v3 adapter and training corpus, or generate the data and train an adapter first. These runtime files are not included in a clean clone. Run the following commands sequentially; no QTMS validation wrapper is needed for this project.

```bash
cd /Users/kianguyen/Dev/sql-finetune-mlx
uv sync --locked

# Choose a new directory to preserve earlier reports.
comparison_out=results/my-comparison-01
mkdir -p results
mkdir "$comparison_out"
small_revision=7ae557604adf67be50417f59c2c2f167def9a775
large_revision=aa8e72537993ba99e69dfaafa59ed015b17504d1

uv run python evaluate_execution.py --revision "$small_revision" --fixtures execution_holdout_v3.json --out "$comparison_out/original.json"
uv run python evaluate_execution.py --revision "$small_revision" --adapter adapters/sql-v3 --fixtures execution_holdout_v3.json --out "$comparison_out/v3.json"
uv run python evaluate_execution.py --revision "$small_revision" --retrieval-corpus data/v3/train.jsonl --top-k 3 --fixtures execution_holdout_v3.json --out "$comparison_out/rag.json"
uv run python evaluate_execution.py --model Qwen/Qwen2.5-3B-Instruct --revision "$large_revision" --fixtures execution_holdout_v3.json --out "$comparison_out/larger.json"

uv run python compare_results.py --fixtures execution_holdout_v3.json --reports "$comparison_out/original.json" "$comparison_out/v3.json" "$comparison_out/rag.json" "$comparison_out/larger.json" --out "$comparison_out/comparison.json"
```

`evaluate_execution.py` generates answers and grades raw responses. `compare_results.py` regrades saved responses without loading a model and keeps the formatting diagnostic separate. Both refuse to overwrite an existing report.

## Limits

These twelve questions were already inspected during the earlier v3 discussion. They were originally excluded from v3 checkpoint selection, but this follow-up is a retrospective comparison on an opened set. It is not a fresh blind benchmark for RAG or model selection.

The tasks are synthetic, single-table queries sharing patterns with the training curriculum. Two questions use a local month-name text-date convention that a `TEXT` schema alone does not specify. More model parameters do not supply that missing database fact. A different retrieval method, prompt, model family or independent test set could change the ranking.
