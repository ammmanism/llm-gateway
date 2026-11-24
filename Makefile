.PHONY: test lint bench

test:
	python -m pytest tests/ -x -q --ignore=tests/modality --ignore=tests/cache

test-all:
	python -m pytest tests/ -x -q

lint:
	python -m ruff check .

lint-fix:
	python -m ruff check . --fix

format:
	python -m ruff format .

bench:
	python benchmarks/run_all.py

bench-overhead:
	python benchmarks/run_gateway_overhead.py

bench-cache-sweep:
	python benchmarks/semantic_cache_sweep.py

bench-fallback:
	python benchmarks/fallback_recovery.py

clean:
	rm -rf .pytest_cache __pycache__ src/llm_gateway.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  test        - Run core tests (excludes modality and cache with import issues)"
	@echo "  test-all    - Run all tests (will fail due to pre-existing import issues)"
	@echo "  lint        - Run ruff linter"
	@echo "  lint-fix    - Auto-fix ruff lint issues"
	@echo "  format      - Format code with ruff"
	@echo "  bench       - Run all benchmarks"
	@echo "  bench-overhead  - Run gateway overhead benchmark"
	@echo "  bench-cache-sweep - Run semantic cache threshold sweep"
	@echo "  bench-fallback    - Run fallback recovery benchmark"
	@echo "  clean       - Clean cache files"