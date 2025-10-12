"""Tests for session-based variable persistence."""

import tempfile
from pathlib import Path
import pytest
import yaml

from noctua.session import SessionManager, SessionData


@pytest.fixture
def temp_session_dir():
    """Create a temporary directory for sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def session_manager(temp_session_dir):
    """Create a SessionManager with a temp directory."""
    return SessionManager(session_dir=temp_session_dir)


def test_session_data_serialization():
    """Test SessionData to/from dict conversion."""
    data = SessionData(
        name="test",
        model_id="gomodel:123",
        variables={"ras": "ind-001", "raf": "ind-002"},
        metadata={"created": "2024-01-01"}
    )

    # Convert to dict
    as_dict = data.to_dict()
    assert as_dict["name"] == "test"
    assert as_dict["model_id"] == "gomodel:123"
    assert as_dict["variables"] == {"ras": "ind-001", "raf": "ind-002"}
    assert as_dict["metadata"] == {"created": "2024-01-01"}

    # Convert back from dict
    restored = SessionData.from_dict(as_dict)
    assert restored.name == data.name
    assert restored.model_id == data.model_id
    assert restored.variables == data.variables
    assert restored.metadata == data.metadata


def test_session_file_creation(session_manager, temp_session_dir):
    """Test that session files are created correctly."""
    session = session_manager.load_session("test_session")
    assert session.name == "test_session"
    assert session.model_id is None
    assert session.variables == {}

    # Save and check file exists
    session_manager.save_session(session)
    session_file = temp_session_dir / "test_session.yaml"
    assert session_file.exists()

    # Check file contents
    with open(session_file, 'r') as f:
        data = yaml.safe_load(f)
    assert data["name"] == "test_session"


def test_set_and_get_variable(session_manager):
    """Test setting and getting variables."""
    model_id = "gomodel:123"

    # Set variables
    session_manager.set_variable("test", model_id, "ras", "ind-001")
    session_manager.set_variable("test", model_id, "raf", "ind-002")

    # Get individual variables
    assert session_manager.get_variable("test", model_id, "ras") == "ind-001"
    assert session_manager.get_variable("test", model_id, "raf") == "ind-002"
    assert session_manager.get_variable("test", model_id, "unknown") is None

    # Get all variables for model
    vars = session_manager.get_variables("test", model_id)
    assert vars == {"ras": "ind-001", "raf": "ind-002"}


def test_model_scoped_variables(session_manager):
    """Test that variables are properly scoped to models."""
    model1 = "gomodel:123"
    model2 = "gomodel:456"

    # Set same variable name for different models
    session_manager.set_variable("test", model1, "ras", "ind-001")
    session_manager.set_variable("test", model2, "ras", "ind-999")

    # Variables should be different per model
    assert session_manager.get_variable("test", model1, "ras") == "ind-001"
    assert session_manager.get_variable("test", model2, "ras") == "ind-999"

    # Get variables per model
    assert session_manager.get_variables("test", model1) == {"ras": "ind-001"}
    assert session_manager.get_variables("test", model2) == {"ras": "ind-999"}


def test_session_persistence(temp_session_dir):
    """Test that sessions persist across SessionManager instances."""
    # Create first manager and set variables
    sm1 = SessionManager(session_dir=temp_session_dir)
    sm1.set_variable("persist", "gomodel:123", "ras", "ind-001")
    sm1.set_variable("persist", "gomodel:123", "raf", "ind-002")

    # Create new manager and check variables persist
    sm2 = SessionManager(session_dir=temp_session_dir)
    assert sm2.get_variable("persist", "gomodel:123", "ras") == "ind-001"
    assert sm2.get_variable("persist", "gomodel:123", "raf") == "ind-002"


def test_list_sessions(session_manager):
    """Test listing available sessions."""
    # Initially empty
    assert session_manager.list_sessions() == []

    # Create some sessions
    session_manager.save_session(SessionData(name="alpha"))
    session_manager.save_session(SessionData(name="beta"))
    session_manager.save_session(SessionData(name="gamma"))

    # List should be sorted
    assert session_manager.list_sessions() == ["alpha", "beta", "gamma"]


def test_delete_session(session_manager):
    """Test deleting sessions."""
    # Create a session
    session_manager.set_variable("to_delete", "gomodel:123", "ras", "ind-001")
    assert "to_delete" in session_manager.list_sessions()

    # Delete it
    deleted = session_manager.delete_session("to_delete")
    assert deleted is True
    assert "to_delete" not in session_manager.list_sessions()

    # Try to delete non-existent
    deleted = session_manager.delete_session("never_existed")
    assert deleted is False


def test_clear_session(session_manager):
    """Test clearing session variables."""
    model_id = "gomodel:123"

    # Set up variables
    session_manager.set_variable("test", model_id, "ras", "ind-001")
    session_manager.set_variable("test", model_id, "raf", "ind-002")
    assert len(session_manager.get_variables("test", model_id)) == 2

    # Clear the session
    session_manager.clear_session("test")

    # Session should exist but be empty
    assert "test" in session_manager.list_sessions()
    assert session_manager.get_variables("test", model_id) == {}


def test_copy_to_from_client(session_manager):
    """Test copying variables to/from BaristaClient."""
    from noctua.barista import BaristaClient

    model_id = "gomodel:123"

    # Set up session variables
    session_manager.set_variable("test", model_id, "ras", "ind-001")
    session_manager.set_variable("test", model_id, "raf", "ind-002")

    # Create a client and copy variables to it
    client = BaristaClient(token="test-token", track_variables=True)
    session_manager.copy_variables_to_client("test", model_id, client)

    # Check variables were copied
    assert client.get_variable(model_id, "ras") == "ind-001"
    assert client.get_variable(model_id, "raf") == "ind-002"

    # Modify client variables
    client.set_variable(model_id, "mek", "ind-003")
    client.set_variable(model_id, "ras", "ind-001-modified")  # Change existing

    # Copy back to session
    session_manager.copy_variables_from_client("test2", model_id, client)

    # Check session has updated variables
    assert session_manager.get_variable("test2", model_id, "ras") == "ind-001-modified"
    assert session_manager.get_variable("test2", model_id, "raf") == "ind-002"
    assert session_manager.get_variable("test2", model_id, "mek") == "ind-003"


def test_session_name_sanitization(session_manager, temp_session_dir):
    """Test that session names are sanitized for filesystem safety."""
    # Names with special characters
    weird_names = [
        "test/session",
        "test\\session",
        "../../../etc/passwd",
        "test:session",
        "test session with spaces",
    ]

    for name in weird_names:
        session_manager.set_variable(name, "gomodel:123", "var", "val")

        # Check that files are created with safe names
        files = list(temp_session_dir.glob("*.yaml"))
        for f in files:
            # No path traversal or special chars
            assert ".." not in f.name
            assert "/" not in f.name
            assert "\\" not in f.name


def test_empty_session_handling(session_manager):
    """Test handling of empty/new sessions."""
    # Load non-existent session creates new one
    session = session_manager.load_session("new_session")
    assert session.name == "new_session"
    assert session.variables == {}
    assert session.model_id is None

    # Getting variables from empty session returns empty
    assert session_manager.get_variables("new_session", "gomodel:123") == {}
    assert session_manager.get_variable("new_session", "gomodel:123", "anything") is None


@pytest.mark.parametrize("session_name,model_id,var_name,actual_id", [
    ("simple", "gomodel:123", "ras", "ind-001"),
    ("with-dash", "gomodel:456", "my_var", "ind-002"),
    ("123numeric", "gomodel:789", "x1", "gomodel:789/individual-123"),
    ("UPPERCASE", "gomodel:abc", "VAR", "ind-upper"),
])
def test_various_identifiers(session_manager, session_name, model_id, var_name, actual_id):
    """Test various valid identifier formats."""
    session_manager.set_variable(session_name, model_id, var_name, actual_id)
    assert session_manager.get_variable(session_name, model_id, var_name) == actual_id