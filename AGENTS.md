# SQL fine-tuning with MLX

- Run this project's commands from the repository root using `uv run ...` directly. This is an independent MLX learning project; QTMS validation wrappers and CI restrictions do not apply.
- Validate Python changes with `uv run python -m unittest discover`. Run model generation and training jobs one at a time on this Mac to limit memory pressure.
- Preserve existing `data/`, `adapters/` and `results/` artifacts. Documentation or folder changes must not retrain models or replace saved datasets, weights or reports.
- Start with `README.md` for current commands and `MODEL_COMPARISON.md` for the four-model experiment.
