.PHONY: dev test lint typecheck format docker-up docker-down benchmark-cache benchmark-router

dev:
	uvicorn src.main:app --reload --port 8000

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

benchmark-cache:
	python benchmarks/cache_benchmark.py

benchmark-router:
	python benchmarks/router_benchmark.py

all-checks: format lint typecheck test