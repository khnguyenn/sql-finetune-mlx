# Improve SQL training with measured experiments

Goal: improve SQL result correctness over the original Qwen2.5-0.5B-Instruct model, without changing its inference prompt or the evaluation rules.

## Changes fixed before training

| Change | Reason |
| --- | --- |
| Start from the original model with a fresh adapter | Preserve the original and v1; avoid carrying the first adapter's mistakes forward |
| Replace the noisy sample with 672 rule-generated training examples | Use clear, consistent targets rather than ambiguous public reference labels |
| Balance 14 SQL task families, 48 examples each | Give distinct counts, ordinary counts, aggregates, grouping and ordering explicit coverage |
| Validate targets against independent Python answers on duplicate, NULL, boundary and empty data | Check the intended semantics before asking the model to imitate the SQL |
| Lower learning rate from 0.0001 to 0.00002 | Make smaller updates to reduce disruption of existing behaviour |
| Train 600 updates and save each 100 | Cover more examples and compare checkpoints rather than assuming the last one is best |

The new dataset is synthetic and narrow. It demonstrates adaptation to single-table SQL patterns; it does not represent broad real-world SQL capability. Multiple training choices change together, so a successful result will not isolate the contribution of any one change.

## Selection and evaluation rules

1. Keep the existing eight execution questions as the development set because their failures have already informed this recipe.
2. Select from updates 100, 200, 400 and 600 using development execution passes. Prefer the earliest checkpoint on a tie. If one reaches 8/8, later checkpoints cannot improve that development score and need not be evaluated.
3. Freeze `execution_holdout.json` before training. It contains 16 new questions with separate table names and wording, three databases per question. Training and validation data cannot use its schemas/questions or tables.
4. After selecting a checkpoint, compare that checkpoint and the original model on the same frozen holdout. Do not use holdout failures to select another checkpoint in this experiment.
5. Count a question as correct only when every database returns the right rows. Require strictly more correct holdout questions than the original to claim a holdout win. Report a tie or loss honestly.

The holdout tests transfer to new wording, schemas and data within the same SQL task families. They are not an external benchmark or a statistically conclusive generalisation study. The original public 100-row test split stays reserved.

## Reproduce

```bash
uv run python prepare_curriculum.py --version 2
~/.local/bin/qtms-validate uv run mlx_lm.lora --config train-v2.yaml
```

The data script refuses to replace `data/v2`. Adapters and generated data remain local and ignored by Git, while the generator, configuration and evaluation cases are committed.

For evaluation, the existing eight questions remain the default. Use `--fixtures execution_holdout.json` to select the frozen holdout, and use new report filenames to preserve earlier results.

## V2 results

Updates 100, 200, 400 and 600 all passed 7/8 development questions. The predeclared tie rule selected update 100. On the frozen 16-question holdout, both the original model and v2 passed 14/16: v2 corrected ascending order but regressed on a distinct-count question phrased as "different readers". This was a tie, not a holdout win.

## One further round: v3, fixed before training

The opened 16 questions are now development evidence, not a fresh test for selecting v3. Version 3 adds counting paraphrases that name entities rather than exact column names, and a fifteenth family for this project's convention of storing dates as literal month-name text. That convention is application-specific, not a universal SQL rule.

V3 has 720 training examples and 120 validation examples, balanced across 15 families. It starts another fresh adapter from the original model, uses learning rate 0.00001, and trains 300 updates. Select from updates 100, 200 and 300 using total execution passes over the old eight questions plus the opened sixteen. Prefer the earliest checkpoint on a tie; stop evaluating later checkpoints if one passes all 24.

`execution_holdout_v3.json` contains twelve newly fixed questions, with separate tables, wording and date values. Its hash is recorded when preparing v3 data, before training. Only after checkpoint selection will we compare the selected model and original on that file. Require strictly more correct questions than the original for a fresh-set win, and do not select or alter the model based on those final results.

```bash
uv run python prepare_curriculum.py --version 3
~/.local/bin/qtms-validate uv run mlx_lm.lora --config train-v3.yaml
```

Both v2 and v3 data versions and all attempted reports are retained. Multiple data and training changes occur together, so this experiment measures their combined effect rather than isolating a single cause.

## Final measured result

V3 updates 100 and 200 scored 23/24 on development; update 300 scored 24/24 and was selected before the fresh twelve-question evaluation.

| Set | Original model | Selected v3 |
| --- | ---: | ---: |
| Original eight development questions | 6/8 | 8/8 |
| Opened sixteen questions, now development | 14/16 | 16/16 |
| Fresh twelve questions, not used for selection | 7/12 | 12/12 |

Every correct question must pass all three database fixtures. The fresh-set result is therefore 36/36 fixture passes for v3, versus 24/36 for the original. This is a win on a small, synthetic, single-table SQL task distribution, not evidence of better performance on SQL in general or all language-model tasks.

The final holdout stayed unchanged from preparation through evaluation: `8b476283687a05cba94c7d781851552a1e08f059ba1feebcb1f9d96d8c148db6`. No model change or checkpoint selection followed those final results. The original public dataset test split remains reserved.

Actual improvements included:

| Question | Original output problem | V3 behaviour |
| --- | --- | --- |
| Entrants from lowest mark to highest | Used `DESC` | Uses `ASC` |
| Presenter on a month-name date | Converted the stored text value to ISO | Keeps the project's literal date text |
| Department point totals | Omitted `GROUP BY department` | Returns a separate total per department |
| Work-log rows per team | Counted distinct teams instead of returning each team's row count | Uses `team, COUNT(*) ... GROUP BY team` |

The date lessons encode this project's data convention. A real application should expose its date-storage rules or sample values rather than assume all databases share this format.

As a descriptive breakdown, excluding the two application-specific date questions leaves 7/10 for the original and 10/10 for v3. That breakdown was not used to select the model or change the fixed twelve-question score.

## Use the selected adapter

The final `adapters/sql-v3/adapters.safetensors` is byte-identical to the selected 300-step checkpoint. The simple usage path is:

```bash
~/.local/bin/qtms-validate uv run python ask.py --adapter adapters/sql-v3
```

To reproduce the fresh comparison after preparing/training v3:

```bash
~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --fixtures execution_holdout_v3.json --out results/v3-original-repeat.json

~/.local/bin/qtms-validate uv run python evaluate_execution.py \
  --adapter adapters/sql-v3 --fixtures execution_holdout_v3.json \
  --out results/v3-adapted-repeat.json
```

Those filenames are new examples; use different names if they already exist. Repeating an opened set does not make it fresh again.

To inspect intermediate checkpoints, MLX-LM needs an adapter directory containing its expected filenames. After training, the following creates links without replacing saved weights:

```python
from pathlib import Path

for version, steps in [(2, (100, 200, 400, 600)), (3, (100, 200, 300))]:
    root = Path(f"adapters/sql-v{version}")
    for step in steps:
        folder = root / f"checkpoint-{step:04d}"
        folder.mkdir(exist_ok=True)
        for name, target in [("adapters.safetensors", f"../{step:07d}_adapters.safetensors"),
                             ("adapter_config.json", "../adapter_config.json")]:
            if not (folder / name).exists():
                (folder / name).symlink_to(target)
```

## Evidence and verification

- `results/v2/`: all four development comparisons, the original/v2 holdout tie, training log and selection record.
- `results/v3/`: all three development comparisons, final original/v3 holdout reports, training log and selection record written before the final evaluation.
- `data/v2/metadata.json` and `data/v3/metadata.json`: recipe sizes, balanced family counts and pre-training holdout hashes.
- Four focused `test_curriculum.py` checks passed. They verify family balance, split boundaries, target queries against independent expected rows, and separation from every evaluation set.
- Reproducing v2 from the versioned generator matched its saved training and validation files exactly after adding v3.

The prompt, base model, decoding settings and SQL grading rules were the same for original and adapted model comparisons. No extra Python dependency was added.
