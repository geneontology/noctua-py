"""Tests for CLI commands for protein complexes and entity sets."""

from typer.testing import CliRunner
from noctua.cli import app


runner = CliRunner()


def test_add_protein_complex_dry_run():
    """Test add-protein-complex command in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-protein-complex",
        "--model", "gomodel:test123",
        "--component", "UniProtKB:P12345",
        "--component", "UniProtKB:P67890|label=Ras protein",
        "--component", "UniProtKB:P99999|label=RAF1|evidence=ECO:0000314|ref=PMID:12345",
        "--var", "my_complex",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "Would create protein complex" in result.output
    assert "gomodel:test123" in result.output
    assert "GO:0032991" in result.output
    assert "my_complex" in result.output
    assert "UniProtKB:P12345" in result.output
    assert "Ras protein" in result.output
    assert "RAF1" in result.output
    assert "ECO:0000314" in result.output
    assert "PMID:12345" in result.output


def test_add_entity_set_dry_run():
    """Test add-entity-set command in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-entity-set",
        "--model", "gomodel:test456",
        "--member", "UniProtKB:P27361|label=MAPK3 (ERK1)",
        "--member", "UniProtKB:P28482|label=MAPK1 (ERK2)|evidence=ECO:0000314|ref=PMID:99999",
        "--var", "erk_paralogs",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "Would create entity set" in result.output
    assert "gomodel:test456" in result.output
    assert "CHEBI:33695" in result.output
    assert "erk_paralogs" in result.output
    assert "UniProtKB:P27361" in result.output
    assert "MAPK3 (ERK1)" in result.output
    assert "UniProtKB:P28482" in result.output
    assert "MAPK1 (ERK2)" in result.output
    assert "ECO:0000314" in result.output
    assert "PMID:99999" in result.output


def test_add_protein_complex_custom_class():
    """Test add-protein-complex with custom class."""
    result = runner.invoke(app, [
        "barista", "add-protein-complex",
        "--model", "test",
        "--component", "UniProtKB:P12345",
        "--class", "GO:1990904",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "GO:1990904" in result.output


def test_add_entity_set_simple():
    """Test add-entity-set with minimal arguments."""
    result = runner.invoke(app, [
        "barista", "add-entity-set",
        "--model", "test",
        "--member", "UniProtKB:P27361",
        "--member", "UniProtKB:P28482",
        "--dry-run"
    ])

    assert result.exit_code == 0
    assert "UniProtKB:P27361" in result.output
    assert "UniProtKB:P28482" in result.output


def test_protein_complex_help():
    """Test that help text is available for add-protein-complex."""
    result = runner.invoke(app, ["barista", "add-protein-complex", "--help"], color=False)

    assert result.exit_code == 0
    output = result.output
    # More flexible assertions that work with or without formatting
    assert "protein complex" in output.lower()
    assert "--component" in output or "component" in output.lower()
    assert "pipe-delimited" in output.lower() or "pipe" in output.lower()


def test_entity_set_help():
    """Test that help text is available for add-entity-set."""
    result = runner.invoke(app, ["barista", "add-entity-set", "--help"], color=False)

    assert result.exit_code == 0
    output = result.output
    # More flexible assertions that work with or without formatting
    assert "entity set" in output.lower()
    assert "--member" in output or "member" in output.lower()
    assert "functionally interchangeable" in output.lower() or "interchangeable" in output.lower()
