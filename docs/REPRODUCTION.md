# Reproduction

Run `uv sync --extra dev`, then `uv run qianscope demo run --size 10000 --seed 2026`. The data generator, respondent split, graph, treatment assignment, and simulation use recorded seeds. Inspect `artifacts/demo/data_manifest.json`, `run_manifest.json`, `evaluation.json`, and `replay.jsonl`.

External LLM calls are not part of the default reproduction path. If enabled, raw structured responses are content-addressed in `artifacts/llm_cache` and reused offline.
