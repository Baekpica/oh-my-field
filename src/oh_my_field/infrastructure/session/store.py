from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from oh_my_field.domain.session.models import AgentSession


@dataclass
class SessionNotFoundError(Exception):
    session_id: str
    sessions_dir: Path

    def __str__(self) -> str:
        return f"session {self.session_id!r} not found in {self.sessions_dir}"


@dataclass
class SessionExistsError(Exception):
    session_id: str
    sessions_dir: Path

    def __str__(self) -> str:
        return f"session {self.session_id!r} already exists in {self.sessions_dir}"


@dataclass
class SessionParseError(Exception):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse session file {self.path}: {self.reason}"


def session_path(session_id: str, sessions_dir: Path) -> Path:
    return sessions_dir / f"{session_id}.json"


def write_session(
    session: AgentSession,
    sessions_dir: Path,
    *,
    overwrite: bool,
) -> Path:
    path = session_path(session.id, sessions_dir)
    if path.exists() and not overwrite:
        raise SessionExistsError(session_id=session.id, sessions_dir=sessions_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_session(session_id: str, sessions_dir: Path) -> AgentSession:
    path = session_path(session_id, sessions_dir)
    if not path.exists():
        raise SessionNotFoundError(session_id=session_id, sessions_dir=sessions_dir)
    try:
        return AgentSession.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise SessionParseError(path=path, reason=str(exc)) from exc
