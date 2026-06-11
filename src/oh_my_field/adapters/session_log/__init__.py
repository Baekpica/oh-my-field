"""Structured session-log parsing for imported agent runs.

``parse_session_log`` picks the dedicated parser for runtimes with a known
session format (claude_code, codex) and falls back to the heuristic JSONL
parser otherwise — including when the dedicated parser recognizes nothing.
Parsers never raise on malformed input; a log with no recognizable events
parses to an empty result and the import proceeds unchanged.
"""

from collections.abc import Callable
from typing import Final

from oh_my_field.adapters.session_log.claude_code import parse_claude_code_session
from oh_my_field.adapters.session_log.codex import parse_codex_session
from oh_my_field.adapters.session_log.events import ParsedSessionEvents
from oh_my_field.adapters.session_log.heuristic import parse_heuristic_session
from oh_my_field.domain.models import AgentImporterName

_DEDICATED_PARSERS: Final[dict[str, Callable[[str], ParsedSessionEvents]]] = {
    "claude_code": parse_claude_code_session,
    "codex": parse_codex_session,
}


def parse_session_log(adapter: AgentImporterName, text: str) -> ParsedSessionEvents:
    dedicated = _DEDICATED_PARSERS.get(adapter)
    if dedicated is not None:
        events = dedicated(text)
        if events.has_content():
            return events
    return parse_heuristic_session(text)


__all__ = [
    "ParsedSessionEvents",
    "parse_claude_code_session",
    "parse_codex_session",
    "parse_heuristic_session",
    "parse_session_log",
]
