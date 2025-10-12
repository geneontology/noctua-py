"""Test CLI delete-edge with session support."""

from typer.testing import CliRunner
from unittest.mock import patch
from noctua.cli import app


def test_delete_edge_with_session_variables():
    """Test delete-edge resolves variables from session."""
    runner = CliRunner()

    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.get_variable.side_effect = lambda session, model, var: {
            ("test", "gomodel:TEST", "ras"): "ind-001",
            ("test", "gomodel:TEST", "raf"): "ind-002"
        }.get((session, model, var))

        result = runner.invoke(app, [
            "barista", "delete-edge",
            "--model", "gomodel:TEST",
            "--subject", "ras",
            "--object", "raf",
            "--predicate", "RO:0002413",
            "--session", "test",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "Using session: test" in result.stdout
        assert "subject 'ras' -> 'ind-001'" in result.stdout
        assert "object 'raf' -> 'ind-002'" in result.stdout
        # Check that the request contains resolved IDs
        assert '"subject": "ind-001"' in result.stdout
        assert '"object": "ind-002"' in result.stdout