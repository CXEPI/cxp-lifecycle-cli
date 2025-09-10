import uuid
from cli.helpers.custom_typer import CustomTyper
import os
import requests
import typer
from cli.config import get_deployment_base_url, ENABLE_ALL_ENVIRNMENTS
from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config, load_env, inject_env_into_json_schema
from pathlib import Path
from cli.helpers.errors import handle_env_error

deploy_commands_app = CustomTyper(name="deploy", help="Manage deployment functions")


def upload_services_config_to_s3(
    deployment_id, app_id, env: str, creds_path: str = None, deploy_all: bool = False
) -> tuple[dict, list]:
    try:
        config = load_config()
        lifecycle_path = Path("lifecycle")
        env_path = os.path.join(lifecycle_path / "lifecycle_envs", f"{env}.env")
        env_vars = load_env(env_path)
        services_payload = {}
        services_to_deploy = []

        for service, folder_path in config.get("core_services", {}).items():
            if deploy_all or typer.confirm(
                f"Do you want to deploy '{service}'?", default=True
            ):
                services_to_deploy.append(service)
                key_prefix = f"lifecycle/{app_id}/{deployment_id}/{service}"
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        if os.path.isfile(full_path):
                            api = APIClient(
                                base_url=get_deployment_base_url(env),
                                env=env,
                                creds_path=creds_path,
                            )
                            response = api.post(
                                "s3/generate_presigned_url",
                                json={
                                    "key": os.path.join(
                                        key_prefix,
                                        os.path.relpath(full_path, folder_path),
                                    )
                                },
                                headers={"Content-Type": "application/json"},
                            )
                            if response.status_code != 200:
                                typer.secho(
                                    f"Failed to generate presigned URL for {file}: {response.text}",
                                    fg=typer.colors.BRIGHT_RED,
                                )
                                raise typer.Exit(1)
                            presigned_url = response.json().get("url")
                            # Inject env vars if JSON schema
                            if file.endswith(".json"):
                                injected_content = inject_env_into_json_schema(
                                    full_path, env_vars
                                )
                                upload_response = requests.put(
                                    presigned_url,
                                    data=injected_content.encode(),
                                    headers={
                                        "Content-Type": "application/octet-stream",
                                        "x-amz-server-side-encryption": "aws:kms",
                                    },
                                )
                            else:
                                with open(full_path, "rb") as file_data:
                                    upload_response = requests.put(
                                        presigned_url,
                                        data=file_data,
                                        headers={
                                            "Content-Type": "application/octet-stream",
                                            "x-amz-server-side-encryption": "aws:kms",
                                        },
                                    )
                            if upload_response.status_code != 200:
                                typer.secho(
                                    f"Internal error",
                                    fg=typer.colors.BRIGHT_RED,
                                )
                                raise typer.Exit(1)
                services_payload[service] = {"configuration_file_path": key_prefix}

    except Exception as e:
        typer.secho(f"An error occurred: {str(e)}", fg=typer.colors.BRIGHT_RED)
        raise typer.Exit(1)

    if not services_to_deploy:
        typer.secho(
            "No services were selected for deployment. At least one service must be selected.",
            fg=typer.colors.BRIGHT_MAGENTA,
        )
        raise typer.Exit(0)

    return services_payload, services_to_deploy


@deploy_commands_app.command("run")
def deploy(
    env: str = typer.Argument("dev"),
    creds_path: str = typer.Option(
        None,
        help="Path to credentials file. If not provided, the default path will be used.",
    ),
    deploy_all: bool = typer.Option(
        False,
        "--deploy-all",
        "-a",
        help="Deploy all services without confirmation prompts",
    ),
) -> None:
    """
    Deploy the application with the given deployment ID and environment.

    Args:
        env: The environment to deploy to, defaults to 'dev'.
        creds_path: Optional path to credentials file. If not provided, the default path will be used.
        deploy_all: If True, deploy all services without confirmation prompts.
    """
    # if not ENABLE_ALL_ENVIRNMENTS and (env != "dev" and env != "sandbox"):
    #     typer.secho(
    #         f"You can only deploy to 'dev' environment using the cli tool.",
    #         fg=typer.colors.RED,
    #     )
    #     raise typer.Exit(1)
    handle_env_error(env)
    deployment_id = uuid.uuid4()
    typer.secho(
        f"Deploying application with deployment ID: {deployment_id}",
        fg=typer.colors.BRIGHT_BLUE,
    )
    config = load_config()
    app_id = config.get("application", {}).get("application_uid", {})
    if not app_id:
        typer.secho(
            "Application ID not found in config. Please run 'register' command first.",
            fg=typer.colors.BRIGHT_RED,
        )
        raise typer.Exit(1)
    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )
    services_payload, services = upload_services_config_to_s3(
        deployment_id, app_id, env, creds_path=creds_path, deploy_all=deploy_all
    )
    payload = {
        "deployment_id": str(deployment_id),
        "services": services_payload,
        "app_id": app_id,
    }
    typer.secho(f"Deploying services: {services}", fg=typer.colors.BRIGHT_YELLOW)
    response = api.post(
        f"/msk/deploy", json=payload, headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        typer.secho(
            f"Failed to initiate deployment for {services}: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )
        return

    typer.secho("Deployment initiated successfully.", fg=typer.colors.BRIGHT_GREEN)


@deploy_commands_app.command("get-status")
def get_status(
    deployment_id: str = typer.Argument(...),
    env: str = typer.Argument("dev"),
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Watch deployment status in real-time"
    ),
) -> None:
    """
    Get the status of a deployment. Use --watch flag to stream status updates in real-time.
    """
    handle_env_error(env)

    if not watch:
        # Single status request
        typer.secho("Getting Status for deployment", fg=typer.colors.BRIGHT_BLUE)
        _display_deployment_status(deployment_id, env)
        return

    # Streaming mode using SSE
    try:
        import time
        from sseclient import SSEClient
        from datetime import datetime
        import json

        api = APIClient(base_url=get_deployment_base_url(env), env=env)

        typer.secho(
            f"Streaming deployment status for ID: {deployment_id} (Ctrl+C to exit)",
            fg=typer.colors.BRIGHT_BLUE,
        )
        typer.secho("=" * 50, fg=typer.colors.BRIGHT_BLUE)

        # Connect to SSE endpoint
        stream_url = (
            f"{get_deployment_base_url(env)}/status/deployment/stream/{deployment_id}"
        )
        headers = api.get_headers()

        last_update_time = datetime.now()
        for event in SSEClient(stream_url, headers=headers):
            if not event.data:
                continue

            try:
                status_data = json.loads(event.data)

                if "info" in status_data and "Connection closed" in status_data["info"]:
                    typer.secho(
                        "\nStream closed: Connection timeout after 5 minutes",
                        fg=typer.colors.BRIGHT_YELLOW,
                    )
                    break

                if (
                    "error" in status_data
                    and status_data["error"] == "Deployment not found"
                ):
                    typer.secho(
                        "\nDeployment not found",
                        fg=typer.colors.BRIGHT_RED,
                    )
                    break

                # Clear screen for better visibility
                os.system("cls" if os.name == "nt" else "clear")
                typer.secho(
                    f"Deployment ID: {deployment_id} (Environment: {env})",
                    fg=typer.colors.BRIGHT_BLUE,
                )
                typer.secho(
                    "Live status updates. Press Ctrl+C to exit.",
                    fg=typer.colors.BRIGHT_BLUE,
                )
                typer.secho("=" * 50, fg=typer.colors.BRIGHT_BLUE)

                services = status_data.get("services", {})

                if not services:
                    typer.secho(
                        "No services found for this deployment.",
                        fg=typer.colors.BRIGHT_YELLOW,
                    )
                    continue

                # Detect validation failure using the services status map
                has_validation_failed = any(
                    data.get("deployment_status") == "Validation Failed"
                    for data in services.values()
                )

                for service, data in services.items():
                    status_color = _get_status_color(data.get("deployment_status"))
                    failure_reason = (
                        f" - {data['failure_reason']}"
                        if data.get("failure_reason")
                        else ""
                    )
                    message = f" {service}: {data['deployment_status']}{failure_reason}"
                    typer.secho(message, fg=status_color)

                if has_validation_failed:
                    typer.secho(
                        "\nDeployment Failed Due To Validation Failure",
                        fg=typer.colors.BRIGHT_RED,
                    )
                    break

                # Add timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                typer.secho(f"\nLast update: {timestamp}", fg=typer.colors.BRIGHT_BLACK)

            except json.JSONDecodeError:
                typer.secho(
                    f"Error parsing update: {event.data}", fg=typer.colors.BRIGHT_RED
                )

    except ImportError:
        typer.secho(
            "SSE client library not found. Install with: pip install sseclient-py",
            fg=typer.colors.BRIGHT_RED,
        )
        return
    except KeyboardInterrupt:
        typer.secho(
            "\nStopped watching deployment status.", fg=typer.colors.BRIGHT_BLUE
        )
    except Exception as e:
        typer.secho(
            f"Error streaming deployment status: {str(e)}", fg=typer.colors.BRIGHT_RED
        )


def _display_deployment_status(deployment_id: str, env: str) -> None:
    """Display deployment status"""
    api = APIClient(base_url=get_deployment_base_url(env), env=env)
    response = api.get(f"/status/deployment/get/{deployment_id}")

    if response.status_code != 200:
        typer.secho(
            f"Failed to get deployment status: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )
        return

    status = response.json().get("services", {})

    if not status:
        typer.secho(
            "No services found for this deployment.", fg=typer.colors.BRIGHT_YELLOW
        )
        return

    for service, data in status.items():
        status_color = _get_status_color(data.get("deployment_status"))
        failure_reason = (
            f" - {data['failure_reason']}" if data.get("failure_reason") else ""
        )
        message = f" {service}: {data['deployment_status']}{failure_reason}"
        typer.secho(message, fg=status_color)


def _get_status_color(status: str) -> str:
    """Get the appropriate color for a status"""
    if not status:
        return typer.colors.BRIGHT_CYAN

    if "Done" in status or "Succeeded" in status:
        return typer.colors.BRIGHT_GREEN
    elif "Failed" in status or "REJECTED" in status or "ERROR" in status:
        return typer.colors.BRIGHT_RED
    elif "Progress" in status or "Pending" in status or "RECEIVED" in status:
        return typer.colors.BRIGHT_YELLOW
    elif "Cancel" in status:
        return typer.colors.BRIGHT_MAGENTA
    else:
        return typer.colors.BRIGHT_CYAN
