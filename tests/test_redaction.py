import pytest

from oh_my_field.domain.evidence.redaction import REDACTED_PLACEHOLDER, redact_secrets


@pytest.mark.parametrize(
    "text",
    [
        "api_key=supersecret",
        "API_KEY: supersecret",
        "OPENAI_API_KEY=supersecret",
        "ANTHROPIC_API_KEY=supersecret",
        "AWS_SECRET_ACCESS_KEY=supersecret",
        "MY_SERVICE_ACCESS_KEY: supersecret",
        "GITHUB_TOKEN=supersecret",
        "client_secret = supersecret",
        "db.password: supersecret",
        "CREDENTIALS=supersecret",
    ],
)
def test_redacts_env_var_style_secret_keys(text: str) -> None:
    redacted, changed = redact_secrets(text)

    assert changed
    assert "supersecret" not in redacted
    assert REDACTED_PLACEHOLDER in redacted


@pytest.mark.parametrize(
    "text",
    [
        "max_tokens=4096",
        "input_tokens: 123",
        "tokenizer=cl100k_base",
        "sort_key=name",
        "keyboard=qwerty",
    ],
)
def test_keeps_non_secret_key_values(text: str) -> None:
    redacted, changed = redact_secrets(text)

    assert not changed
    assert redacted == text


def test_redacts_openai_style_key_values_without_key_prefix() -> None:
    redacted, changed = redact_secrets("using sk-proj-abcdefghijklmnop123456 here")

    assert changed
    assert "sk-proj" not in redacted
    assert redacted == f"using {REDACTED_PLACEHOLDER} here"


def test_reports_no_change_for_plain_text() -> None:
    redacted, changed = redact_secrets("pytest run: 2 passed in 0.1s")

    assert not changed
    assert redacted == "pytest run: 2 passed in 0.1s"
