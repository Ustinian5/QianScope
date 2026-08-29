# Reproduction

Run `uv sync --extra dev`, then `uv run qianscope demo run --size 10000 --seed 2026`. The data generator, respondent split, graph, treatment assignment, and simulation use recorded seeds. Inspect `artifacts/demo/data_manifest.json`, `run_manifest.json`, `evaluation.json`, and `replay.jsonl`.

Pure numerical reproduction may set `QIANSCOPE_LLM_REQUIRED=false` and omit a provider key. Public-product runs use live DeepSeek calls with cache disabled, so their prose and bounded semantic assumptions are intentionally variable; the statistical path remains replayable once the compiled request is persisted. Explicit adapter tests may still opt into the content-addressed cache.
