import typer
import uuid
import json

from cli.config import get_deployment_base_url
from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config
from cli.helpers.errors import handle_env_error
from cli.deploy.deploy import upload_services_config_to_s3

try:
    from sseclient import SSEClient

    HAS_SSE = True
except ImportError:
    HAS_SSE = False


def _get_status_color(status: str) -> str:
    """Get the appropriate color for a status"""
    if not status:
        return typer.colors.BRIGHT_CYAN

    if "Done" in status or "Succeeded" in status or "Completed" in status:
        return typer.colors.BRIGHT_GREEN
    elif "Failed" in status or "REJECTED" in status or "ERROR" in status:
        return typer.colors.BRIGHT_RED
    elif (
        "Progress" in status
        or "Pending" in status
        or "RECEIVED" in status
        or "Validating" in status
    ):
        return typer.colors.BRIGHT_YELLOW
    elif "Cancel" in status:
        return typer.colors.BRIGHT_MAGENTA
    else:
        return typer.colors.BRIGHT_CYAN


def _stream_validation_status(
    validation_id: str, env: str, api: APIClient, services: list
) -> dict:
    """Stream validation status using SSE until completion or failure"""
    if not HAS_SSE:
        typer.secho(
            "SSE streaming not available.",
            fg=typer.colors.BRIGHT_YELLOW,
        )
        return None

    try:
        typer.secho(
            f"\nWaiting for validation to complete...",
            fg=typer.colors.BRIGHT_CYAN,
        )

        stream_url = (
            f"{get_deployment_base_url(env)}/status/deployment/stream/{validation_id}"
        )
        headers = api.get_headers()

        completed_services = set()
        last_status = None

        for event in SSEClient(stream_url, headers=headers):
            if not event.data:
                continue

            try:
                status_data = json.loads(event.data)

                if "info" in status_data and "Connection closed" in status_data["info"]:
                    typer.secho(
                        f"\n\nStream closed by server.",
                        fg=typer.colors.BRIGHT_YELLOW,
                    )
                    if last_status:
                        return last_status
                    break

                if (
                    "error" in status_data
                    and status_data["error"] == "Deployment not found"
                ):
                    typer.secho(
                        f"\n\nValidation not found.",
                        fg=typer.colors.BRIGHT_RED,
                    )
                    return None

                services_status = status_data.get("services", {})
                last_status = services_status

                if not services_status:
                    continue

                for service in services:
                    if service in services_status and service not in completed_services:
                        service_data = services_status[service]
                        service_status = service_data.get("deployment_status", "")

                        is_complete = False
                        if (
                            "Done" in service_status
                            or "Succeeded" in service_status
                            or "Completed" in service_status
                        ):
                            is_complete = True
                            status_color = typer.colors.BRIGHT_GREEN
                            icon = "✅"
                        elif (
                            "Failed" in service_status
                            or "REJECTED" in service_status
                            or "ERROR" in service_status
                        ):
                            is_complete = True
                            status_color = typer.colors.BRIGHT_RED
                            icon = "❌"

                        if is_complete:
                            completed_services.add(service)
                            typer.secho("")
                            message = f"{icon} {service.upper()}: {service_status}"
                            if service_data.get("failure_reason"):
                                message += f" - {service_data['failure_reason']}"
                            typer.secho(message, fg=status_color)

                all_done = len(completed_services) == len(services)

                if all_done:
                    typer.secho("")
                    return services_status

                # Show progress indicator
                typer.secho(".", nl=False, fg=typer.colors.BRIGHT_CYAN)

            except json.JSONDecodeError:
                typer.secho(
                    f"\nError parsing status update: {event.data}",
                    fg=typer.colors.BRIGHT_RED,
                )
                continue

        if last_status and len(completed_services) == len(services):
            return last_status
        else:
            typer.secho(
                f"\n\nStream closed before all services completed validation.",
                fg=typer.colors.BRIGHT_YELLOW,
            )
            return None

    except KeyboardInterrupt:
        typer.secho(
            f"\n\nValidation status monitoring cancelled by user.",
            fg=typer.colors.BRIGHT_YELLOW,
        )
        return None
    except Exception as e:
        typer.secho(
            f"\n\nError streaming validation status: {str(e)}",
            fg=typer.colors.BRIGHT_RED,
        )
        return None


def _display_validation_results(services_status: dict, services: list):
    """Display validation results for all services"""
    typer.secho("\n" + "=" * 60, fg=typer.colors.BRIGHT_BLUE)
    typer.secho("Validation Results", fg=typer.colors.BRIGHT_BLUE, bold=True)
    typer.secho("=" * 60, fg=typer.colors.BRIGHT_BLUE)

    has_failures = False

    for service in services:
        if service in services_status:
            data = services_status[service]
            status = data.get("deployment_status", "Unknown")
            status_color = _get_status_color(status)

            typer.secho(
                f"\n{service.upper()}:", fg=typer.colors.BRIGHT_WHITE, bold=True
            )
            typer.secho(f"  Status: {status}", fg=status_color)

            if data.get("failure_reason"):
                has_failures = True
                typer.secho(
                    f"  Reason: {data['failure_reason']}", fg=typer.colors.BRIGHT_RED
                )

            if data.get("validation_details"):
                typer.secho(
                    f"  Details: {data['validation_details']}",
                    fg=typer.colors.BRIGHT_CYAN,
                )
        else:
            typer.secho(
                f"\n{service.upper()}:", fg=typer.colors.BRIGHT_WHITE, bold=True
            )
            typer.secho(f"  Status: No status available", fg=typer.colors.BRIGHT_YELLOW)

    typer.secho("\n" + "=" * 60, fg=typer.colors.BRIGHT_BLUE)

    if has_failures:
        typer.secho(
            "❌ Validation completed with failures",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
    else:
        typer.secho(
            "✅ Validation completed successfully",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )

    typer.secho("=" * 60, fg=typer.colors.BRIGHT_BLUE)


def validate(
    env: str = typer.Argument("dev"),
    creds_path: str = typer.Option(
        None,
        help="Path to credentials file. If not provided, the default path will be used.",
    ),
    validate_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Validate all services without confirmation prompts",
    ),
) -> None:
    """
    Validate the application configuration without deploying.
    """
    handle_env_error(env)
    config = load_config()
    app_id = config.get("application", {}).get("application_uid")
    app_version = str(config.get("application", {}).get("app_version", {}))

    if not app_id:
        typer.secho(
            "Application ID not found in config. Please run 'register' command first.",
            fg=typer.colors.BRIGHT_RED,
        )
        raise typer.Exit(1)

    deployment_id = uuid.uuid4()
    typer.secho(
        f"Validating application with deployment ID: {deployment_id}",
        fg=typer.colors.BRIGHT_BLUE,
    )

    services_payload, services = upload_services_config_to_s3(
        deployment_id, app_id, env, creds_path=creds_path, deploy_all=validate_all
    )

    payload = {
        "deployment_id": str(deployment_id),
        "services": services_payload,
        "app_id": app_id,
        "app_version": app_version,
        "description": config.get("application", {}).get("description"),
        "lead_developer_email": config.get("application", {}).get("lead_developer_email"),
        "github_url": config.get("application", {}).get("github_url"),
        "app_name": config.get("application", {}).get("display_name"),
    }

    typer.secho(
        f"Validating services: {', '.join(services)}", fg=typer.colors.BRIGHT_YELLOW
    )

    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )

    response = api.post(
        "/dry-run", json=payload, headers={"Content-Type": "application/json"}
    )

    if response.status_code != 200:
        typer.secho(
            f"Failed to initiate validation for {', '.join(services)}: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Validation {deployment_id} initiated successfully.",
        fg=typer.colors.BRIGHT_GREEN,
    )

    services_status = _stream_validation_status(str(deployment_id), env, api, services)

    if services_status:
        _display_validation_results(services_status, services)
    else:
        typer.secho(
            f"Deployment ID: {deployment_id}",
            fg=typer.colors.BRIGHT_CYAN,
        )
        typer.secho(
            f"Check status with: cx-cli deploy get-status {deployment_id} {env}",
            fg=typer.colors.BRIGHT_CYAN,
        )
        raise typer.Exit(1)
