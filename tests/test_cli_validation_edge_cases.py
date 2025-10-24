"""Tests for CLI validation edge cases."""

from typer.testing import CliRunner
from noctua.cli import app


runner = CliRunner()


def test_add_protein_complex_missing_entity_id():
    """Test that missing entity_id in component spec is caught."""
    result = runner.invoke(app, [
        "barista", "add-protein-complex",
        "--model", "test",
        "--component", "|label=Something",  # Missing entity_id
        "--dry-run"
    ])

    # Should fail with error message
    assert result.exit_code == 1
    assert "missing entity_id" in result.output.lower()


def test_add_entity_set_missing_entity_id():
    """Test that missing entity_id in member spec is caught."""
    result = runner.invoke(app, [
        "barista", "add-entity-set",
        "--model", "test",
        "--member", "|label=Something",  # Missing entity_id
        "--dry-run"
    ])

    # Should fail with error message
    assert result.exit_code == 1
    assert "missing entity_id" in result.output.lower()
