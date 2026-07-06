.PHONY: install test lint format clean docker-build docker-run docs security

install:
	pip install -e ".[all,dev]"

test:
	pytest tests/ -v --cov=omnimodal --cov-report=term-missing

lint:
	ruff check src/omnimodal
	mypy src/omnimodal

format:
	black src/ tests/ examples/
	ruff check --fix src/ tests/ examples/

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-build:
	docker build -t omnimodal:latest .

docker-run:
	docker-compose up -d

docker-down:
	docker-compose down -v

benchmark:
	pip install pytest-benchmark
	pytest tests/benchmarks/ -v --benchmark-only --benchmark-json=benchmark.json

docs:
	mkdocs serve

security:
	pip-audit
	bandit -r src/omnimodal
