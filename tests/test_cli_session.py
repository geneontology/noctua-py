"""Test CLI session functionality."""

import tempfile
from pathlib import Path
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from noctua.cli import app
from noctua.barista import BaristaResponse


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_session_dir():
    """Create a temporary directory for sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_session_list_empty(runner, temp_session_dir):
    """Test listing sessions when none exist."""
    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.list_sessions.return_value = []

        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0
        assert "No sessions found" in result.stdout


def test_session_list_with_sessions(runner):
    """Test listing existing sessions."""
    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.list_sessions.return_value = ["alpha", "beta", "gamma"]
        mock_sm._session_file.side_effect = lambda x: Path(f".noctua/{x}.yaml")

        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0
        assert "Available sessions:" in result.stdout
        assert "alpha" in result.stdout
        assert "beta" in result.stdout
        assert "gamma" in result.stdout


def test_session_show(runner):
    """Test showing session variables."""
    with patch("noctua.cli.SessionManager") as MockSM:
        from noctua.session import SessionData

        mock_sm = MockSM.return_value
        mock_sm.list_sessions.return_value = ["test"]
        mock_sm.load_session.return_value = SessionData(
            name="test",
            model_id="gomodel:123",
            variables={
                "gomodel:123:ras": "ind-001",
                "gomodel:123:raf": "ind-002",
            }
        )
        mock_sm.get_variables.return_value = {
            "ras": "ind-001",
            "raf": "ind-002"
        }

        result = runner.invoke(app, ["session", "show", "test"])
        assert result.exit_code == 0
        assert "Session: test" in result.stdout
        assert "ras" in result.stdout
        assert "ind-001" in result.stdout


def test_session_clear(runner):
    """Test clearing session variables."""
    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.list_sessions.return_value = ["test"]

        result = runner.invoke(app, ["session", "clear", "test", "-y"])
        assert result.exit_code == 0
        assert "Cleared session 'test'" in result.stdout
        mock_sm.clear_session.assert_called_once_with("test")


def test_session_delete(runner):
    """Test deleting a session."""
    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.list_sessions.return_value = ["test"]
        mock_sm.delete_session.return_value = True

        result = runner.invoke(app, ["session", "delete", "test", "-y"])
        assert result.exit_code == 0
        assert "Deleted session 'test'" in result.stdout
        mock_sm.delete_session.assert_called_once_with("test")


def test_add_individual_with_session_dry_run(runner):
    """Test add-individual with session in dry-run mode."""
    result = runner.invoke(app, [
        "barista", "add-individual",
        "--model", "gomodel:TEST",
        "--class", "GO:0016055",
        "--assign", "ras",
        "--session", "test",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "Using session: test" in result.stdout
    assert "m3BatchPrivileged" in result.stdout


def test_add_fact_with_session_dry_run(runner):
    """Test add-fact with session variables in dry-run mode."""
    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.get_variable.side_effect = lambda session, model, var: {
            ("test", "gomodel:TEST", "ras"): "ind-001",
            ("test", "gomodel:TEST", "raf"): "ind-002"
        }.get((session, model, var))

        result = runner.invoke(app, [
            "barista", "add-fact",
            "--model", "gomodel:TEST",
            "--subject", "ras",
            "--object", "raf",
            "--predicate", "RO:0002413",
            "--session", "test",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "subject 'ras' -> 'ind-001'" in result.stdout
        assert "object 'raf' -> 'ind-002'" in result.stdout


def test_add_individual_with_session_saves_variable():
    """Test that add-individual saves variable to session."""
    runner = CliRunner()

    with patch("noctua.cli._make_client") as mock_make_client, \
         patch("noctua.cli.SessionManager") as MockSM:

        # Mock client
        mock_client = MagicMock()
        mock_make_client.return_value = mock_client

        # Mock responses
        mock_client._snapshot_model.return_value = {
            "individuals": set(),
            "facts": set()
        }

        # Mock the response with new individual
        mock_response = BaristaResponse(raw={
            "message-type": "success",
            "data": {
                "id": "gomodel:TEST",
                "individuals": [
                    {"id": "gomodel:TEST/new-ind-123", "type": [{"id": "GO:0016055"}]}
                ],
                "facts": []
            }
        })
        mock_client.m3_batch.return_value = mock_response
        mock_client._track_new_individual.return_value = "gomodel:TEST/new-ind-123"
        mock_client.get_variables.return_value = {"ras": "gomodel:TEST/new-ind-123"}

        # Mock session manager
        mock_sm = MockSM.return_value

        result = runner.invoke(app, [
            "barista", "add-individual",
            "--model", "gomodel:TEST",
            "--class", "GO:0016055",
            "--assign", "ras",
            "--session", "test",
            "--token", "test-token",
        ])

        # Check that variable was saved to session
        mock_sm.set_variable.assert_called_once_with(
            "test", "gomodel:TEST", "ras", "gomodel:TEST/new-ind-123"
        )
        assert "Saved variable 'ras'" in result.stdout


def test_add_fact_evidence_with_session_variables():
    """Test add-fact-evidence with session variable resolution."""
    runner = CliRunner()

    with patch("noctua.cli.SessionManager") as MockSM:
        mock_sm = MockSM.return_value
        mock_sm.get_variable.side_effect = lambda session, model, var: {
            ("test", "gomodel:TEST", "ras"): "ind-001",
            ("test", "gomodel:TEST", "raf"): "ind-002"
        }.get((session, model, var))

        result = runner.invoke(app, [
            "barista", "add-fact-evidence",
            "--model", "gomodel:TEST",
            "--subject", "ras",
            "--object", "raf",
            "--predicate", "RO:0002413",
            "--eco", "ECO:0000353",
            "--source", "PMID:12345",
            "--session", "test",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "subject 'ras' -> 'ind-001'" in result.stdout
        assert "object 'raf' -> 'ind-002'" in result.stdout