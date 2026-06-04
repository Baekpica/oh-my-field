from pydantic import BaseModel
from typer import echo


def emit_json(model: BaseModel) -> None:
    """Render a workflow result model as a single JSON line on stdout."""
    echo(model.model_dump_json())
