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


@deploy_commands_app.command("get-status")
def get_status(
    deployment_id: str = typer.Argument(...), env: str = typer.Argument("dev")
) -> None:
    handle_env_error(env)
    typer.secho("Getting Status for deployment", fg=typer.colors.BRIGHT_BLUE)
    api = APIClient(base_url=get_deployment_base_url(env), env=env)
    response = api.get(f"/status/deployment/get/{deployment_id}")
    if response.status_code == 200:
        status = response.json()["services"]
        if not status:
            typer.secho(
                "No services found for this deployment.", fg=typer.colors.BRIGHT_YELLOW
            )
            return
        for service, data in status.items():
            typer.secho(
                f" {service}: {data['deployment_status']} {data['failure_reason'] if data['failure_reason'] else ''}",
                fg=typer.colors.BRIGHT_CYAN,
            )
    else:
        typer.secho(
            f"Failed to get deployment status: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )


def upload_services_config_to_s3(deployment_id, app_id, env: str) -> tuple[dict, list]:
    try:
        config = load_config()
        lifecycle_path = Path("lifecycle")
        env_path = os.path.join(lifecycle_path / "lifecycle_envs", f"{env}.env")
        env_vars = load_env(env_path)
        services_payload = {}
        services_to_deploy = []

        for service, folder_path in config.get("core_services", {}).items():
            if typer.confirm(f"Do you want to deploy '{service}'?", default=True):
                services_to_deploy.append(service)
                key_prefix = f"lifecycle/{app_id}/{deployment_id}/{service}"
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        if os.path.isfile(full_path):
                            api = APIClient(base_url=get_deployment_base_url(env), env=env)
                            response = api.post(
                                "s3/generate_presigned_url",
                                json={"key": os.path.join(key_prefix, os.path.relpath(full_path, folder_path))},
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

        if not services_to_deploy:
            typer.secho(
                "No services were selected for deployment. At least one service must be selected.",
                fg=typer.colors.BRIGHT_MAGENTA,
            )
            raise typer.Exit(0)

        return services_payload, services_to_deploy

    except Exception as e:
        typer.secho(f"An error occurred: {str(e)}", fg=typer.colors.BRIGHT_RED)
        raise typer.Exit(1)


@deploy_commands_app.command("deploy")
def deploy(env: str = typer.Argument("dev")) -> None:
    """
    Deploy the application with the given deployment ID and environment.
    """
    if not ENABLE_ALL_ENVIRNMENTS and env != "dev":
        typer.secho(
            f"You can only deploy to 'dev' environment using the cli tool.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    handle_env_error(env)
    deployment_id = uuid.uuid4()
    typer.secho(
        f"Deploying application with deployment ID: {deployment_id}",
        fg=typer.colors.BRIGHT_BLUE,
    )
    config = load_config()
    app_id = config.get("application", {}).get("application_uid", {})
    api = APIClient(base_url=get_deployment_base_url(env), env=env)
    services_payload, services = upload_services_config_to_s3(
        deployment_id, app_id, env
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
