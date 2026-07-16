# Contributing to Neurocache

First off, thank you for considering contributing to Neurocache! It's people like you that make this open-source proxy robust and cost-saving for everyone.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ammmanism/neurocache.git
   cd neurocache
   ```

2. **Set up the environment**
   We use `uv` or `pip` with Python 3.11+.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```

3. **Start infrastructure dependencies**
   ```bash
   docker-compose up -d redis postgres
   ```

## Development Workflow

- **Testing**: Run `pytest tests/` before submitting a PR.
- **Linting**: We use `ruff`. Run `ruff check src/ tests/` and fix any issues.
- **Type Checking**: We use strict `mypy`. Run `mypy src/`.

## Pull Request Process

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Make your changes, ensuring tests pass.
3. Update documentation if necessary (in `README.md` or `docs/`).
4. Commit your changes with conventional commit messages (e.g., `feat: added amazing feature`, `fix: patched memory leak`).
5. Open a Pull Request against the `main` branch.

## Architecture Decisions

Please review the [Architecture Doc](docs/architecture.md) before proposing major refactors to the Smart Router or Semantic Cache layers.