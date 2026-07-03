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
