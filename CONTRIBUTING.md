# Contributing to OmniModal

Thank you for your interest in OmniModal! This document provides guidelines for contributing to the project.

## Quick Start

1. Fork the repository
2. Clone your fork: `git clone https://github.com/ammmanism/omniModal.git`
3. Install dependencies: `make install`
4. Install pre-commit hooks: `make install-pre-commit`
5. Create a branch: `git checkout -b feature/amazing-feature`

## Testing

All contributions must include tests:

```bash
# Run all tests
make test

# Run specific test suite
pytest tests/unit/test_router.py -v

# Run with coverage
make test-coverage
```

## Code Style

We use `black`, `ruff`, and `mypy`:

```bash
make format  # Auto-format code
make lint    # Check style and types
```

## Architecture Guidelines

- **Gateway Layer**: Keep routing logic provider-agnostic
- **Adapters**: Each provider gets its own adapter in `src/omnimodal/modalities/`
- **Fusion**: New cross-modal patterns go in `src/omnimodal/fusion/`
- **Tests**: 90% coverage required for new features

## PR Checklist

- [ ] Tests pass (`make test`)
- [ ] Code formatted (`make format`)
- [ ] Linting passes (`make lint`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] PR description explains the "why" and "what"

## Reporting Bugs

Use GitHub Issues with:
- Clear reproduction steps
- Expected vs actual behavior
- Environment details (Python version, OS)
- Relevant logs or error messages

## Feature Requests

Open a GitHub Discussion first for major features. For small enhancements, feel free to open a PR directly.

## Recognition

Contributors will be:
- Listed in `CONTRIBUTORS.md`
- Mentioned in release notes
- Invited to the core team after sustained contributions

Let's build the future of multimodal AI together!
