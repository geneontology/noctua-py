# Testing

## Running Tests

```bash
# All tests
just test

# Python tests only
just pytest

# Type checking
just mypy

# Linting
just format
```

## Test Structure

```
tests/
├── test_barista.py      # API client tests
├── test_cli.py          # CLI tests
└── test_simple.py       # Basic tests
```

## Writing Tests

Use pytest style:

```python
def test_create_model():
    client = BaristaClient()
    response = client.create_model(title="Test")
    assert response.ok
    assert response.model_id
```

## Integration Tests

Set environment for integration tests:
```bash
# Set your dev token for integration tests
export BARISTA_TOKEN=your-dev-token-here
pytest tests/test_barista.py::test_integration
```

## Coverage

```bash
pytest --cov=noctua tests/
```