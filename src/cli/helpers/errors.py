import typer
from cli.config import ENVIRONMENTS


def handle_request_error(error):
    """
    Handle API request errors and display appropriate messages.
    """
    typer.secho(f"Error: {error}", fg=typer.colors.RED)
    if hasattr(error, "response") and error.response is not None:
        typer.secho(
            f"Server response: {error.response.status_code} {error.response.reason}",
            fg=typer.colors.RED,
        )
        try:
            typer.secho(str(error.response.json()), fg=typer.colors.RED)
        except Exception:
            typer.secho(error.response.text, fg=typer.colors.RED)


def handle_env_error(env: str):
    if env not in ENVIRONMENTS:
        typer.secho(
            f"Error: env must be one of: {', '.join(ENVIRONMENTS)}",
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(code=1)
