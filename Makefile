.PHONY: install test lint format demo api clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=marginmesh --cov-report=term-missing

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

demo:
	python -m marginmesh demo --out marginmesh-demo

api:
	uvicorn marginmesh.api:app --host 127.0.0.1 --port 8000

clean:
	rm -rf build dist .pytest_cache .ruff_cache .coverage htmlcov marginmesh-output marginmesh-demo
