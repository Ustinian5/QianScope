.PHONY: setup lint typecheck test prediction-demo generate-demo-data train-demo evaluate-demo simulate-demo serve demo

setup:
	uv sync --extra dev

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy src

test:
	uv run pytest

prediction-demo:
	uv run qianscope predict demo --paths 8

generate-demo-data:
	uv run qianscope demo generate --size 10000 --seed 2026

train-demo:
	uv run qianscope demo train

evaluate-demo:
	uv run qianscope demo evaluate

simulate-demo:
	uv run qianscope demo simulate

demo:
	uv run qianscope demo run --size 10000 --seed 2026

serve:
	uv run qianscope serve
