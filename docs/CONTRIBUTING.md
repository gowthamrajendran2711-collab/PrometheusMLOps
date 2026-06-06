# Contributing

## Development Setup

```bash
git clone <repo>
cd <project>
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

## Running Tests

```bash
make test
```

## Code Style

- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy`

Run all: `make lint`

## Pull Request Process

1. Fork the repo and create a feature branch: `git checkout -b feat/your-feature`
2. Write tests for your changes
3. Ensure `make test` passes with no regressions
4. Open a PR with a clear description of what and why

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` test changes
- `refactor:` code refactoring
- `perf:` performance improvement
