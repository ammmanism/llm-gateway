.PHONY: install test lint format clean docker run docs benchmark security

PYTHON := python3
PIP := pip3

# ---------------------------------------------
# Development
# ---------------------------------------------

install:
	$(PIP) install -e ".[all,dev]"

install-pre-commit:
	pre-commit install

test:
	pytest tests/ -v --cov=omnimodal --cov-report=term-missing

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v -m integration

test-coverage:
	pytest tests/ --cov=omnimodal --cov-report=html --cov-report=xml
	@echo "Coverage report: htmlcov/index.html"

benchmark:
	pytest tests/benchmarks/ -v --benchmark-only

lint:
	ruff check src/omnimodal
	mypy src/omnimodal

format:
	black src/ tests/ examples/
	ruff check --fix src/ tests/ examples/

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------
# Docker
# ---------------------------------------------

docker-build:
	docker build -t omnimodal:latest .

docker-run:
	docker-compose up -d

docker-logs:
	docker-compose logs -f gateway

docker-down:
	docker-compose down -v

# ---------------------------------------------
# Documentation
# ---------------------------------------------

docs:
	mkdocs serve

docs-build:
	mkdocs build

# ---------------------------------------------
# Security
# ---------------------------------------------

security:
	pip-audit
	bandit -r src/omnimodal

# ---------------------------------------------
# Release
# ---------------------------------------------

bump-patch:
	bump2version patch

bump-minor:
	bump2version minor

bump-major:
	bump2version major
