"""Secret redaction applied to captured text before it enters an evidence record."""

import re
from typing import Final

REDACTED_PLACEHOLDER: Final = "[REDACTED]"

# Key/value secrets. The key may be a bare keyword (api_key=, token:), an
# identifier ending in one (OPENAI_API_KEY=, AWS_SECRET_ACCESS_KEY:), or a
# JSON/YAML-quoted form ("api_key": ...); a keyword followed by more
# identifier characters (max_tokens=, tokenizer=) is not a key.
SECRET_KEY_VALUE_PATTERN: Final = re.compile(
    r"(?i)((?:\b[\w.-]*[_-])?"
    r"(?:api[_-]?key|access[_-]?key|secret|token|password|passwd|pwd|credentials?)"
    r"\b[\"']?\s*[:=]\s*)(\S+)",
)
AWS_ACCESS_KEY_PATTERN: Final = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
BEARER_TOKEN_PATTERN: Final = re.compile(r"(?i)(bearer\s+)\S+")
GITHUB_TOKEN_PATTERN: Final = re.compile(
    r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}\b",
)
SLACK_TOKEN_PATTERN: Final = re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")
OPENAI_STYLE_KEY_PATTERN: Final = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
JWT_TOKEN_PATTERN: Final = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
)
PRIVATE_KEY_BLOCK_PATTERN: Final = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_VALUE_PATTERNS: Final = (
    AWS_ACCESS_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    SLACK_TOKEN_PATTERN,
    OPENAI_STYLE_KEY_PATTERN,
    JWT_TOKEN_PATTERN,
    PRIVATE_KEY_BLOCK_PATTERN,
)


def redact_secrets(
    text: str,
    *,
    extra_patterns: tuple[re.Pattern[str], ...] = (),
) -> tuple[str, bool]:
    """Replace secret-bearing spans with a placeholder; report whether any matched."""
    redacted, total = SECRET_KEY_VALUE_PATTERN.subn(
        rf"\1{REDACTED_PLACEHOLDER}",
        text,
    )
    for pattern in (*_VALUE_PATTERNS, *extra_patterns):
        redacted, count = pattern.subn(REDACTED_PLACEHOLDER, redacted)
        total += count
    redacted, bearer = BEARER_TOKEN_PATTERN.subn(
        rf"\1{REDACTED_PLACEHOLDER}",
        redacted,
    )
    return redacted, bool(total + bearer)
