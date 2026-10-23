# SQL fine-tuning with MLX

- Run this project's commands from the repository root using `uv run ...` directly. This is an independent MLX project; QTMS validation wrappers and CI restrictions do not apply.
- Validate Python changes with `uv run python -m unittest discover -s tests`. Run model generation and training jobs one at a time on this Mac to limit memory pressure.
- Preserve existing `data/`, `adapters/` and `results/` artifacts. Documentation or folder changes must not retrain models or replace saved datasets, weights or reports.
- Run Python entry points as `uv run python -m sql_finetune.<module>` from the repository root. Configs and committed database scenarios live in `configs/` and `fixtures/`.
- Start with `README.md` for setup and operation; use `docs/architecture.md`, `docs/data.md` and `docs/experiments.md` for implementation, data inventory and recorded evidence.
