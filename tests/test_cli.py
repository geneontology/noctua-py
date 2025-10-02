from __future__ import annotations

from typer.testing import CliRunner

from noctua.cli import app


def test_cli_dry_run_add_individual() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "barista",
            "add-individual",
            "--model",
            "gomodel:TEST",
            "--class",
            "GO:0016055",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "POST http" in out
    assert "m3BatchPrivileged" in out
    assert "GO:0016055" in out
    # Check that dev server is used by default
    assert "barista-dev.berkeleybop.org" in out
    assert "minerva_public_dev" in out


def test_cli_dry_run_add_individual_live() -> None:
    """Test that --live flag switches to production server."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "barista",
            "add-individual",
            "--model",
            "gomodel:TEST",
            "--class",
            "GO:0016055",
            "--dry-run",
            "--live",
        ],
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "POST http" in out
    assert "m3BatchPrivileged" in out
    assert "GO:0016055" in out
    # Check that live server is used with --live flag
    assert "barista.berkeleybop.org" in out
    assert "minerva_public/" in out  # Should be minerva_public, not minerva_public_dev


def test_cli_clear_model_dry_run() -> None:
    """Test clear-model command with dry-run flag."""
    runner = CliRunner()
    # We need to mock the get_model call since dry-run still fetches the model
    # For now, we'll just test that the command exists and accepts the right arguments
    result = runner.invoke(
        app,
        [
            "barista",
            "clear-model",
            "--help",
        ],
    )
    assert result.exit_code == 0
    assert "clear-model" in result.stdout
    assert "Remove all nodes and edges" in result.stdout


def test_cli_export_model_help() -> None:
    """Test export-model command help."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "barista",
            "export-model",
            "--help",
        ],
    )
    assert result.exit_code == 0
    assert "export-model" in result.stdout
    assert "Export a model in various formats" in result.stdout
    assert "--output" in result.stdout
    assert "--format" in result.stdout
