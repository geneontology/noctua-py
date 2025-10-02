# Contributing

## Development Setup

```bash
# Clone repository
git clone https://github.com/geneontology/noctua-py
cd noctua-py

# Install with uv
uv sync

# Run tests
just test
```

## Code Style

- Use `ruff` for linting and formatting
- Type hints for all public functions
- Docstrings for all classes and methods

## Testing

Run all tests:
```bash
just test
```

Individual test types:
```bash
just pytest      # Python tests
just mypy       # Type checking
just format     # Linting
```

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `just test` to verify
5. Submit pull request

## Documentation

Build docs locally:
```bash
just _serve
```

View at http://localhost:8000