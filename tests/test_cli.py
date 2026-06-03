from typer.testing import CliRunner

from oh_my_field.cli import app


def test_help_lists_cli_name_when_invoked() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "oh-my-field" in result.stdout
    assert "import-run" in result.stdout
    assert "verify" in result.stdout
    assert "Create or update a regression eval case" in result.stdout
