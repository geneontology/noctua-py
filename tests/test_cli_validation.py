"""Tests for CLI validation functionality."""

from typer.testing import CliRunner
from noctua.cli import app


runner = CliRunner()


def test_parse_validation_spec():
    """Test parsing validation specifications."""
    from noctua.cli import _parse_validation_spec

    # Test ID only
    result = _parse_validation_spec(["GO:0003924"])
    assert result == [{"id": "GO:0003924"}]

    # Test ID=label format
    result = _parse_validation_spec(["GO:0003924=GTPase activity"])
    assert result == [{"id": "GO:0003924", "label": "GTPase activity"}]

    # Test label only (no colon)
    result = _parse_validation_spec(["GTPase activity"])
    assert result == [{"label": "GTPase activity"}]

    # Test multiple specs
    result = _parse_validation_spec([
        "GO:0003924",
        "GO:0004674=protein kinase activity",
        "cytoplasm"
    ])
    assert result == [
        {"id": "GO:0003924"},
        {"id": "GO:0004674", "label": "protein kinase activity"},
        {"label": "cytoplasm"}
    ]

    # Test empty list
    result = _parse_validation_spec([])
    assert result is None

    # Test None
    result = _parse_validation_spec(None)
    assert result is None


def test_add_individual_with_validation_dry_run():
    """Test add-individual command with validation in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "gomodel:test123",
        "--class", "GO:0003924",
        "--validate", "GO:0003924",
        "--validate", "GO:0003924=GTPase activity",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "POST" in result.output
    assert "GO:0003924" in result.output
    assert "Note: Validation specs would be checked:" in result.output
    assert "['GO:0003924', 'GO:0003924=GTPase activity']" in result.output


def test_add_fact_with_validation_dry_run():
    """Test add-fact command with validation in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-fact",
        "--model", "gomodel:test123",
        "--subject", "ind-123",
        "--object", "ind-456",
        "--predicate", "RO:0002413",
        "--validate", "GO:0004674",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "POST" in result.output
    assert "RO:0002413" in result.output
    assert "Note: Validation specs would be checked:" in result.output


def test_add_fact_evidence_with_validation_dry_run():
    """Test add-fact-evidence command with validation in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-fact-evidence",
        "--model", "gomodel:test123",
        "--subject", "ind-123",
        "--object", "ind-456",
        "--predicate", "RO:0002413",
        "--eco", "ECO:0000314",
        "--source", "PMID:12345",
        "--validate", "GO:0003924=GTPase activity",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "POST" in result.output
    assert "ECO:0000314" in result.output
    assert "PMID:12345" in result.output
    assert "Note: Validation specs would be checked:" in result.output


def test_model_id_normalization_with_validation():
    """Test that model IDs are normalized correctly with validation."""
    # Short hex format
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "6796b94c00003233",
        "--class", "GO:0003924",
        "--validate", "GO:0003924",
        "--dry-run"
    ])

    assert result.exit_code == 0
    output = result.output
    assert "gomodel:6796b94c00003233" in output or "model-id" in output


def test_validation_spec_formats():
    """Test various validation spec formats in CLI."""
    # Test with spaces in label
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "test",
        "--class", "GO:0003924",
        "--validate", "GO:0003924=GTPase activity with spaces",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "GTPase activity with spaces" in result.output

    # Test multiple validation specs
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "test",
        "--class", "GO:0003924",
        "--validate", "GO:0003924",
        "--validate", "GO:0004674=protein kinase activity",
        "--validate", "cytoplasm",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "Note: Validation specs would be checked:" in result.output


def test_add_individual_without_validation():
    """Test that add-individual still works without validation."""
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "test",
        "--class", "GO:0003924",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "Note: Validation specs" not in result.output
    assert "GO:0003924" in result.output


def test_cli_help_shows_validation():
    """Test that help text shows validation options."""
    result = runner.invoke(app, ["barista", "add-individual", "--help"])

    assert result.exit_code == 0
    assert "--validate" in result.output
    assert "Expected types" in result.output

    # Check that examples are shown
    assert "Examples:" in result.output or "validation" in result.output.lower()