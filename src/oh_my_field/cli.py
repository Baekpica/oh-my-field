import typer

app = typer.Typer(
    help="oh-my-field turns tacit know-how into reusable capabilities.",
    no_args_is_help=True,
)


def _main() -> None:
    pass


app.callback()(_main)
