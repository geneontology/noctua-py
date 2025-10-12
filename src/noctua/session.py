"""Session management for persistent variable tracking in the CLI.

Sessions allow CLI users to persist variables between commands,
similar to how the Python API tracks variables in memory.

Variables are stored in a .noctua/ directory with session-specific YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING
import yaml
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .barista import BaristaClient


@dataclass
class SessionData:
    """Data stored for a CLI session.

    Attributes:
        name: Session name
        model_id: Associated model ID (if any)
        variables: Dictionary mapping variable names to actual IDs
        metadata: Optional metadata (e.g., creation time, last modified)
    """
    name: str
    model_id: Optional[str] = None
    variables: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'model_id': self.model_id,
            'variables': self.variables,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionData:
        """Create from dictionary."""
        return cls(
            name=data.get('name', 'default'),
            model_id=data.get('model_id'),
            variables=data.get('variables', {}),
            metadata=data.get('metadata', {})
        )


class SessionManager:
    """Manages persistent sessions for CLI variable tracking.

    Sessions are stored in .noctua/ directory in the current working directory
    or in the user's home directory (~/.noctua/).

    Examples:
        >>> sm = SessionManager()
        >>> sm.set_variable("test", "model123", "ras", "ind-001")
        >>> sm.get_variable("test", "model123", "ras")
        'ind-001'
        >>> sm.get_variables("test", "model123")
        {'ras': 'ind-001'}
        >>> sm.clear_session("test")
        >>> sm.get_variable("test", "model123", "ras") is None
        True
    """

    def __init__(self, session_dir: Optional[Path] = None):
        """Initialize session manager.

        Args:
            session_dir: Directory to store sessions. Defaults to .noctua/ in cwd,
                        falls back to ~/.noctua/ if cwd is not writable.
        """
        if session_dir:
            self.session_dir = Path(session_dir)
        else:
            # Try current directory first
            cwd_sessions = Path.cwd() / ".noctua"
            if self._can_write_dir(Path.cwd()):
                self.session_dir = cwd_sessions
            else:
                # Fall back to home directory
                self.session_dir = Path.home() / ".noctua"

        # Create session directory if it doesn't exist
        self.session_dir.mkdir(exist_ok=True, parents=True)

    def _can_write_dir(self, path: Path) -> bool:
        """Check if directory is writable."""
        try:
            test_file = path / ".noctua_test"
            test_file.touch()
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def _session_file(self, session_name: str) -> Path:
        """Get the file path for a session."""
        # Sanitize session name for filesystem
        # Replace path separators and special chars with underscores
        safe_name = session_name
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
            safe_name = safe_name.replace(char, '_')
        # Remove any leading dots or path traversal attempts
        safe_name = safe_name.lstrip('.').replace('..', '_')
        # Keep only alphanumeric, dash, underscore
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
        # Default to 'default' if empty after sanitization
        if not safe_name:
            safe_name = "default"
        return self.session_dir / f"{safe_name}.yaml"

    def load_session(self, session_name: str) -> SessionData:
        """Load a session, creating if it doesn't exist.

        Args:
            session_name: Name of the session

        Returns:
            SessionData object
        """
        session_file = self._session_file(session_name)

        if session_file.exists():
            with open(session_file, 'r') as f:
                data = yaml.safe_load(f) or {}
                return SessionData.from_dict(data)
        else:
            # Create new session
            return SessionData(name=session_name)

    def save_session(self, session: SessionData) -> None:
        """Save a session to disk.

        Args:
            session: SessionData to save
        """
        session_file = self._session_file(session.name)

        with open(session_file, 'w') as f:
            yaml.dump(session.to_dict(), f, default_flow_style=False)

    def set_variable(self, session_name: str, model_id: str, var_name: str, actual_id: str) -> None:
        """Set a variable in a session.

        Args:
            session_name: Session name
            model_id: Model ID (for scoping variables)
            var_name: Variable name (e.g., "ras")
            actual_id: Actual ID (e.g., "gomodel:123/individual-456")
        """
        session = self.load_session(session_name)

        # Update model_id if not set
        if not session.model_id:
            session.model_id = model_id

        # Store variable with model scoping (key format: "model:var")
        key = f"{model_id}:{var_name}"
        session.variables[key] = actual_id

        self.save_session(session)

    def get_variable(self, session_name: str, model_id: str, var_name: str) -> Optional[str]:
        """Get a variable from a session.

        Args:
            session_name: Session name
            model_id: Model ID
            var_name: Variable name

        Returns:
            Actual ID or None if not found
        """
        session = self.load_session(session_name)
        key = f"{model_id}:{var_name}"
        return session.variables.get(key)

    def get_variables(self, session_name: str, model_id: str) -> Dict[str, str]:
        """Get all variables for a model in a session.

        Args:
            session_name: Session name
            model_id: Model ID

        Returns:
            Dictionary of variable name to actual ID
        """
        session = self.load_session(session_name)
        prefix = f"{model_id}:"

        result = {}
        for key, value in session.variables.items():
            if key.startswith(prefix):
                var_name = key[len(prefix):]
                result[var_name] = value

        return result

    def list_sessions(self) -> list[str]:
        """List all available sessions.

        Returns:
            List of session names
        """
        sessions = []
        for file in self.session_dir.glob("*.yaml"):
            sessions.append(file.stem)
        return sorted(sessions)

    def delete_session(self, session_name: str) -> bool:
        """Delete a session.

        Args:
            session_name: Session name

        Returns:
            True if deleted, False if didn't exist
        """
        session_file = self._session_file(session_name)
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    def clear_session(self, session_name: str) -> None:
        """Clear all variables in a session but keep the session.

        Args:
            session_name: Session name
        """
        session = self.load_session(session_name)
        session.variables.clear()
        self.save_session(session)

    def copy_variables_to_client(self, session_name: str, model_id: str, client: 'BaristaClient') -> None:
        """Copy session variables to a BaristaClient instance.

        Args:
            session_name: Session name
            model_id: Model ID
            client: BaristaClient instance
        """
        variables = self.get_variables(session_name, model_id)
        for var_name, actual_id in variables.items():
            client.set_variable(model_id, var_name, actual_id)

    def copy_variables_from_client(self, session_name: str, model_id: str, client: 'BaristaClient') -> None:
        """Copy variables from a BaristaClient instance to session.

        Args:
            session_name: Session name
            model_id: Model ID
            client: BaristaClient instance
        """
        variables = client.get_variables(model_id)
        for var_name, actual_id in variables.items():
            self.set_variable(session_name, model_id, var_name, actual_id)