"""Message Service CLI commands for managing topic grants."""

from enum import Enum
from typing import Optional

import typer

from cli.helpers.custom_typer import CustomTyper
from cli.helpers.api_client import APIClient
from cli.config import BASE_URL_BY_ENV


class GrantRole(str, Enum):
    PRODUCER = "producer"
    CONSUMER = "consumer"


ms_app = CustomTyper(help="Message Service commands for managing topics and grants.")

grants_app = CustomTyper(help="Manage topic grants (producer/consumer access).")
ms_app.add_typer(grants_app, name="grants")


def get_messaging_api_url(env: str) -> str:
    """Get the messaging API URL for the given environment."""
    base_url = BASE_URL_BY_ENV.get(env)
    if not base_url:
        typer.secho(f"Unknown environment: {env}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    return f"{base_url}/messaging/api/v1"


@grants_app.command("create")
def grants_create(
    topic: str = typer.Argument(..., help="Topic name (e.g., cx.myapp.events.v1)"),
    app_id: str = typer.Option(..., "--app-id", "-a", help="Application ID to grant access to"),
    role: GrantRole = typer.Option(..., "--role", "-r", help="Role to grant: producer or consumer"),
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Consumer group name (required for consumer role). Use '*' to allow all groups.",
    ),
    env: str = typer.Option(..., "--env", "-e", help="Environment: sbx, dev, nprd, prod"),
    creds_path: Optional[str] = typer.Option(
        None, "--creds", "-c", help="Path to credentials file"
    ),
):
    """
    Create a grant for an application to access a topic.

    For consumer role, --group is required. Use --group '*' to allow all consumer groups.

    Examples:
        cx-cli ms grants create cx.myapp.events.v1 --app-id my-app --role producer --env sbx
        cx-cli ms grants create cx.myapp.events.v1 --app-id my-app --role consumer --group my-group --env sbx
        cx-cli ms grants create cx.myapp.events.v1 --app-id my-app --role consumer --group '*' --env sbx
    """
    # Validate consumer group requirement
    if role == GrantRole.CONSUMER and not group:
        typer.secho(
            "Error: Consumer group is required for consumer role.\n"
            "  Use --group <group_name> for a specific group\n"
            '  Use --group "*" to allow all consumer groups',
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(1)

    api = APIClient(base_url=get_messaging_api_url(env), env=env, creds_path=creds_path)

    payload = {
        "app_id": app_id,
        "role": role.value,
    }
    if group:
        payload["consumer_group"] = group

    typer.secho(f"Creating {role.value} grant for {app_id} on topic {topic}...", fg=typer.colors.BRIGHT_BLUE)

    response = api.post(f"/topics/{topic}/grants", json=payload)

    if response.status_code == 201:
        typer.secho(f"Grant created successfully.", fg=typer.colors.BRIGHT_GREEN, bold=True)
    elif response.status_code == 409:
        typer.secho(f"Grant already exists.", fg=typer.colors.BRIGHT_YELLOW)
    else:
        typer.secho(
            f"Failed to create grant: {response.status_code} - {response.text}",
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(1)


@grants_app.command("delete")
def grants_delete(
    topic: str = typer.Argument(..., help="Topic name (e.g., cx.myapp.events.v1)"),
    app_id: str = typer.Option(..., "--app-id", "-a", help="Application ID to revoke access from"),
    role: GrantRole = typer.Option(..., "--role", "-r", help="Role to revoke: producer or consumer"),
    env: str = typer.Option(..., "--env", "-e", help="Environment: sbx, dev, nprd, prod"),
    creds_path: Optional[str] = typer.Option(
        None, "--creds", "-c", help="Path to credentials file"
    ),
):
    """
    Delete a grant for an application from a topic.

    Examples:
        cx-cli ms grants delete cx.myapp.events.v1 --app-id my-app --role producer --env sbx
        cx-cli ms grants delete cx.myapp.events.v1 --app-id my-app --role consumer --env sbx
    """
    api = APIClient(base_url=get_messaging_api_url(env), env=env, creds_path=creds_path)

    typer.secho(f"Deleting {role.value} grant for {app_id} on topic {topic}...", fg=typer.colors.BRIGHT_BLUE)

    response = api.delete(f"/topics/{topic}/grants/{app_id}?role={role.value}")

    if response.status_code == 204:
        typer.secho(f"Grant deleted successfully.", fg=typer.colors.BRIGHT_GREEN, bold=True)
    elif response.status_code == 404:
        typer.secho(f"Grant not found.", fg=typer.colors.BRIGHT_YELLOW)
    else:
        typer.secho(
            f"Failed to delete grant: {response.status_code} - {response.text}",
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(1)


@grants_app.command("list")
def grants_list(
    topic: str = typer.Argument(..., help="Topic name (e.g., cx.myapp.events.v1)"),
    env: str = typer.Option(..., "--env", "-e", help="Environment: sbx, dev, nprd, prod"),
    creds_path: Optional[str] = typer.Option(
        None, "--creds", "-c", help="Path to credentials file"
    ),
):
    """
    List all grants for a topic.

    Examples:
        cx-cli ms grants list cx.myapp.events.v1 --env sbx
    """
    api = APIClient(base_url=get_messaging_api_url(env), env=env, creds_path=creds_path)

    typer.secho(f"Fetching grants for topic {topic}...", fg=typer.colors.BRIGHT_BLUE)

    response = api.get(f"/topics/{topic}/grants")

    if response.status_code == 200:
        data = response.json()
        grants = data.get("grants", [])

        if not grants:
            typer.secho("No grants found for this topic.", fg=typer.colors.BRIGHT_YELLOW)
            return

        typer.secho(f"\nGrants for topic: {topic}", fg=typer.colors.BRIGHT_MAGENTA, bold=True)
        typer.secho("-" * 60)

        for grant in grants:
            app_id = grant.get("app_id", "N/A")
            role = grant.get("role", "N/A")
            consumer_group = grant.get("consumer_group", "-")

            role_color = typer.colors.BRIGHT_GREEN if role == "producer" else typer.colors.BRIGHT_CYAN
            typer.secho(f"  App ID: {app_id}", fg=typer.colors.BRIGHT_WHITE)
            typer.secho(f"    Role: {role}", fg=role_color)
            if role == "consumer":
                typer.secho(f"    Group: {consumer_group}", fg=typer.colors.BRIGHT_WHITE)
            typer.echo()

    elif response.status_code == 404:
        typer.secho(f"Topic not found: {topic}", fg=typer.colors.BRIGHT_YELLOW)
    else:
        typer.secho(
            f"Failed to fetch grants: {response.status_code} - {response.text}",
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(1)
