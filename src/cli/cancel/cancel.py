import typer
from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config
from cli.config import get_deployment_base_url

def cancel(
    deployment_id: str = typer.Argument(
        ...,
        help=f"The deploymentId you want to cancel",
        show_default=False,
        case_sensitive=False,
    ),
        env: str = typer.Argument("dev")
):
    """
    Terminate the running deployment when it is in the validation phase.
    """
    typer.secho(f"Try to Cancel the deployment for: {deployment_id}", fg=typer.colors.BRIGHT_BLUE)
    api = APIClient(base_url=get_deployment_base_url(env), env=env)
    response = api.post(
        f"/cancel/", deployment_id=deployment_id, headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        typer.secho(
            f"Failed to cancel deployment for {deployment_id}: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )
        return

    typer.secho(f"Deployment cancel successfully for: {deployment_id}", fg=typer.colors.BRIGHT_GREEN)