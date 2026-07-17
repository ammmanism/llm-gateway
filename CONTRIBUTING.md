# Contributing to `llm-gateway`

First off, thank you for considering contributing! We believe that great software is built by a community of passionate people. Whether you're fixing a bug, adding a feature, or improving documentation - your help is invaluable.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and harassment-free environment for everyone.

## Getting Started

### Prerequisites
- Python 3.10+
- Git
- (Optional) Redis, Docker

### Development Setup
```bash
# Clone your fork
git clone https://github.com/your-username/llm-gateway.git
cd llm-gateway

# Create virtual environment
python -m venv venv
source venv/bin/activate   # or .\venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests
```bash
# All tests
pytest tests/

# Specific modules
pytest tests/unit/
pytest tests/integration/
pytest tests/routing/chaos/
```

### Linting & Formatting
We use ruff for lightning-fast linting and formatting.

```bash
ruff check .          # lint
ruff format .         # auto-format
mypy src/             # type checking
```

## How to Contribute

1. **Pick an Issue** - Check the issue tracker for open tasks. Comment that you're working on it so we avoid duplication.

2. **Create a Branch**
```bash
git checkout -b feat/your-feature-name
# or fix/your-bug-fix
```

3. **Make Your Changes** - Write clean, typed, and well-documented code. Add or update tests for any new functionality. Update documentation (README, docs/) accordingly.

4. **Run Checks**
```bash
ruff check .
ruff format .
mypy src/
pytest tests/
```

5. **Commit & Push** - Use Conventional Commits:
```
feat(routing): add cost-aware routing with fallback
fix(cache): resolve redis connection timeout
docs(readme): update benchmark tables
```

6. **Open a Pull Request** - Target the `main` branch. Fill out the PR template. Link any related issues.

## Style Guide
- Python: Follow PEP 8 (enforced by ruff).
- Docstrings: Use Google style.
- Imports: Use isort (included in pre-commit).
- Types: Use type hints for all function signatures.
- Tests: Use pytest; aim for >85% coverage.

## Adding a New Provider
1. Create a new file in `src/llm_gateway/providers/`.
2. Inherit from `BaseProvider` and implement `generate()` and `stream()`.
3. Add the provider to `factory.py`.
4. Add configuration to `configs/models.yaml`.
5. Write unit and integration tests.

## Adding a New Modality
1. Create a new module in `src/llm_gateway/modality/`.
2. Implement `BaseModality` interface.
3. Update the modality registry.
4. Write examples in `examples/`.

## Documentation
We use Markdown for all docs. If you add a new feature, please update the relevant documentation:

- `README.md` - high-level overview, installation, quick start
- `docs/architecture.md` - component diagram and interactions
- `docs/tradeoffs.md` - design decisions
- `docs/failures.md` - incident post-mortems (very important)
- `docs/benchmarking-methodology.md` - how to reproduce benchmarks

## Questions?
Open a Discussion or ping us on the issue tracker. We're happy to help!

Thank you for making llm-gateway better. Every contribution counts.
