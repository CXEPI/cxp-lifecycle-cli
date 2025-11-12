from cli.config import CONFIG_FILE
import uuid
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
import typer
import questionary
from questionary import Style
from sseclient import SSEClient

from cli.helpers.custom_typer import CustomTyper
from cli.config import get_deployment_base_url, BASE_URL_BY_ENV
from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config, load_env, inject_env_into_schema
from cli.helpers.errors import handle_env_error
from cli.register.register import create_application_in_developer_studio

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

        # Get all available services
        all_services = list(config.get("core_services", {}).keys())

        # Select services to deploy
        if deploy_all:
            services_to_deploy = all_services
        else:
            if not all_services:
                typer.secho(
                    "No core services found in configuration.",
                    fg=typer.colors.BRIGHT_YELLOW,
                )
                return {}, []

            # Create choices with all services selected by default
            choices = [questionary.Choice(service, checked=True) for service in all_services]

            # Custom style with transparent background
            custom_style = Style([
                ('checkbox-selected', 'fg:#00aa00 bold'),  # Green checkmark
                ('checkbox', 'fg:#ffffff'),  # White for unselected
                ('selected', 'bg: fg:'),  # Transparent background
                ('pointer', 'fg:#00aa00 bold'),  # Green pointer
                ('highlighted', 'fg:#00aa00 bg:'),  # Green text, transparent background
                ('answer', 'fg:#00aa00 bold'),  # Green for final answer
            ])

            selected_services = questionary.checkbox(
                "Select services to deploy:",
                choices=choices,
                style=custom_style
            ).ask()

            if selected_services is None:  # User cancelled
                typer.secho("Deployment cancelled.", fg=typer.colors.BRIGHT_YELLOW)
                raise typer.Exit(0)

            services_to_deploy = selected_services

        if not services_to_deploy:
            typer.secho(
                "No services selected for deployment. At least one service must be selected.",
                fg=typer.colors.BRIGHT_MAGENTA,
            )
            raise typer.Exit(0)

        typer.secho(
            f"Selected services: {', '.join(services_to_deploy)}",
            fg=typer.colors.BRIGHT_BLUE,
        )

        # Collect all upload tasks
        upload_tasks = []
        api = APIClient(
            base_url=get_deployment_base_url(env),
            env=env,
            creds_path=creds_path,
        )

        for service in services_to_deploy:
            folder_path = config["core_services"][service]
            key_prefix = f"lifecycle/{app_id}/{deployment_id}/{service}"

            for root, _, files in os.walk(folder_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if os.path.isfile(full_path):
                        relative_path = os.path.relpath(full_path, folder_path)
                        s3_key = os.path.join(key_prefix, relative_path)
                        upload_tasks.append({
                            'service': service,
                            'file_path': full_path,
                            's3_key': s3_key,
                            'folder_path': folder_path
                        })

            services_payload[service] = {"configuration_file_path": key_prefix}

        # Upload files concurrently
        total_files = len(upload_tasks)
        typer.secho(
            f"Uploading {total_files} files across {len(services_to_deploy)} services...",
            fg=typer.colors.MAGENTA,
        )

        upload_tasks.append({
            'service': 'lifecycle',
            'file_path': str(Path("lifecycle") / CONFIG_FILE),
            's3_key': f"lifecycle/{app_id}/{deployment_id}/{CONFIG_FILE}",
            'folder_path': str(lifecycle_path)
        })

        def upload_file(task):
            try:
                # Generate presigned URL
                response = api.post(
                    "s3/generate_presigned_url",
                    json={"key": task['s3_key']},
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code != 200:
                    return f"Failed to generate presigned URL for {task['file_path']}: {response.text}"

                presigned_url = response.json().get("url")
                file_name = os.path.basename(task['file_path'])

                # Upload file
                if file_name.endswith(".json") or file_name.endswith(".yaml"):
                    injected_content = inject_env_into_schema(task['file_path'], env_vars)
                    upload_response = requests.put(
                        presigned_url,
                        data=injected_content.encode(),
                        headers={
                            "Content-Type": "application/octet-stream",
                            "x-amz-server-side-encryption": "aws:kms",
                        },
                    )
                else:
                    with open(task['file_path'], "rb") as file_data:
                        upload_response = requests.put(
                            presigned_url,
                            data=file_data,
                            headers={
                                "Content-Type": "application/octet-stream",
                                "x-amz-server-side-encryption": "aws:kms",
                            },
                        )

                if upload_response.status_code != 200:
                    return f"Upload failed for {task['file_path']}: HTTP {upload_response.status_code}"

                return None  # Success
            except Exception as e:
                return f"Error uploading {task['file_path']}: {str(e)}"

        # Execute uploads with progress tracking
        completed_count = 0
        errors = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_task = {executor.submit(upload_file, task): task for task in upload_tasks}

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                result = future.result()
                completed_count += 1

                if result is None:  # Success
                    typer.secho(
                        f"✓ [{completed_count}/{total_files}] {task['service']}/{os.path.basename(task['file_path'])}",
                        fg=typer.colors.MAGENTA,
                    )
                else:  # Error
                    errors.append(result)
                    typer.secho(
                        f"✗ [{completed_count}/{total_files}] {task['service']}/{os.path.basename(task['file_path'])}",
                        fg=typer.colors.BRIGHT_RED,
                    )

        if errors:
            typer.secho("\nUpload errors:", fg=typer.colors.BRIGHT_RED)
            for error in errors:
                typer.secho(f"  • {error}", fg=typer.colors.RED)
            raise typer.Exit(1)

        typer.secho(
            f"✓ Successfully uploaded all {total_files} files!",
            fg=typer.colors.BRIGHT_GREEN,
        )

    except Exception as e:
        typer.secho(f"An error occurred: {str(e)}", fg=typer.colors.BRIGHT_RED)
        raise typer.Exit(1)

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
    handle_env_error(env)
    config = load_config()
    app_id = config.get("application", {}).get("application_uid", {})
    app_version = str(config.get("application", {}).get("app_version", {}))
    if not app_id:
        typer.secho(
            "Application ID not found in config. Please run 'register' command first.",
            fg=typer.colors.BRIGHT_RED,
        )
        raise typer.Exit(1)

    api = APIClient(
        base_url=BASE_URL_BY_ENV[env], env=env, creds_path=creds_path
    )
    
    # Check if application exists in IAM
    iam_response = api.get(
        f"/cxp-iam/api/v1/applications/{app_id}",
        headers={"Content-Type": "application/json"},
    )
    
    if iam_response.status_code == 200:
        # Application exists in IAM, now check if it exists in Developer Studio
        ds_response = api.get(
            f"/lifecycle/api/v1/deployment/applications/{app_id}",
            headers={"Content-Type": "application/json"},
        )
        
        # If application doesn't exist in Developer Studio (404), create it
        if ds_response.status_code == 404:  
            # Get application details from IAM response
            iam_app_details = iam_response.json()
            
            try:
                create_application_in_developer_studio(api, iam_app_details)
            except Exception as e:
                typer.secho(
                    f"Failed to create application in Developer Studio: {str(e)}",
                    fg=typer.colors.BRIGHT_RED,
                )
                raise typer.Exit(1)

    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )
    response = api.get(
        f"/status/application/{app_id}/inProgress",
        headers={"Content-Type": "application/json"},
    )
    if response.status_code == 200:
        in_progress = response.json()
        if in_progress:
            typer.secho(
                f"An existing deployment is already in progress for application ID {app_id}.",
                fg=typer.colors.BRIGHT_RED,
            )
            typer.secho(
                "Please wait until it finishes before starting a new deployment, or use the cancel command",
                fg=typer.colors.BRIGHT_RED,
            )
            typer.secho(
                "to stop the current deployment (only possible during the validation phase).",
                fg=typer.colors.BRIGHT_RED,
            )
            raise typer.Exit(1)

    deployment_id = uuid.uuid4()
    typer.secho(
        f"Deploying application with deployment ID: {deployment_id}",
        fg=typer.colors.BRIGHT_BLUE,
    )

    services_payload, services = upload_services_config_to_s3(
        deployment_id, app_id, env, creds_path=creds_path, deploy_all=deploy_all
    )
    payload = {
        "deployment_id": str(deployment_id),
        "services": services_payload,
        "app_id": app_id,
        "app_version": app_version,
    }
    typer.secho(f"Deploying services: {', '.join(services)}", fg=typer.colors.BRIGHT_YELLOW)
    response = api.post(
        "/msk/deploy", json=payload, headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        typer.secho(
            f"Failed to initiate deployment for {', '.join(services)}: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )
        return

    typer.secho(f"Deployment {deployment_id} initiated successfully.", fg=typer.colors.BRIGHT_GREEN)


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
        typer.secho("Getting status for deployment", fg=typer.colors.BRIGHT_BLUE)
        _display_deployment_status(deployment_id, env)
        return

    # Streaming mode using SSE
    try:
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

        for event in SSEClient(stream_url, headers=headers):
            if not event.data:
                continue

            try:
                status_data = json.loads(event.data)

                if "info" in status_data and "Connection closed" in status_data["info"]:
                    typer.secho(
                        "\nStream closed: Connection timeout after 5 minutes.",
                        fg=typer.colors.BRIGHT_YELLOW,
                    )
                    break

                if (
                    "error" in status_data
                    and status_data["error"] == "Deployment not found"
                ):
                    typer.secho(
                        "\nDeployment not found.",
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
                    failure_reason = data.get("failure_reason", {}).get(
                        "combined", data.get("failure_reason", [""])[0]
                    )
                    message = f" {service}: {data['deployment_status']}{failure_reason}"
                    typer.secho(message, fg=status_color)

                if has_validation_failed:
                    typer.secho(
                        "\nDeployment failed due to validation failure.",
                        fg=typer.colors.BRIGHT_RED,
                    )
                    break

                # Add timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                typer.secho(f"\nLast update: {timestamp}", fg=typer.colors.BRIGHT_BLACK)

            except json.JSONDecodeError:
                typer.secho(
                    f"Error parsing status update: {event.data}", fg=typer.colors.BRIGHT_RED
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
        if data.get("failure_reason"):
            if data["failure_reason"].get("combined"):
                failure_reason = f" - {data["failure_reason"]["combined"]}\n"
            else:
                failure_reason = f" - {data["failure_reason"]}\n"
        else:
            failure_reason = ""
        message = f" {service}: {data['deployment_status']}\n {failure_reason}"
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