import uuid
from cli.helpers.custom_typer import CustomTyper
import os
import requests
import typer
from cli.config import DEPLOYMENT_BASE_URL
from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config

deploy_commands_app = CustomTyper(name="deploy", help="Manage deployment functions")


@deploy_commands_app.command("get-status")
def get_status(deployment_id: str) -> None:
    typer.secho("Getting Status for deployment", fg=typer.colors.BRIGHT_BLUE)
    api = APIClient(base_url=DEPLOYMENT_BASE_URL)
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
                f" {service}: {data['deployment_status']} {data['failure_reason'] if data['failure_reason'] else ''}", fg=typer.colors.BRIGHT_CYAN
            )
    else:
        typer.secho(
            f"Failed to get deployment status: {response.text}",
            fg=typer.colors.BRIGHT_RED,
        )


def upload_services_config_to_s3(deployment_id, app_id) -> tuple[dict, list]:
    try:
        config = load_config()
        services_payload = {}
        for service, folder_path in config.get("core_services", {}).items():
            if typer.confirm(f"Do you want to deploy '{service}'?", default=True):
                key_prefix = f"lifecycle/{app_id}/{deployment_id}/{service}"
                for file in os.listdir(folder_path):
                    full_path = os.path.join(folder_path, file)
                    if os.path.isfile(full_path):
                        api = APIClient(base_url=DEPLOYMENT_BASE_URL)
                        response = api.post(
                            "s3/generate_presigned_url",
                            json={"key": os.path.join(key_prefix, file)},
                            headers={"Content-Type": "application/json"},
                        )
                        if response.status_code != 200:
                            typer.secho(
                                f"Failed to generate presigned URL for {file}: {response.text}",
                                fg=typer.colors.BRIGHT_RED,
                            )
                            raise typer.Exit(1)
                        presigned_url = response.json().get('url')
                        with open(full_path, "rb") as file_data:
                            upload_response = requests.put(
                                presigned_url,
                                data=file_data,
                                headers={"Content-Type": "application/octet-stream",
                                         "x-amz-server-side-encryption": "aws:kms"},
                            )
                            if upload_response.status_code != 200:
                                typer.secho(
                                    f"Internal error",
                                    fg=typer.colors.BRIGHT_RED,
                                )
                                raise typer.Exit(1)
                services_payload[service] = {"configuration_file_path": key_prefix}
        return services_payload, list(config.get("core_services", {}).keys())
    except Exception as e:
        typer.secho(f"An unexpected error occurred: {str(e)}", fg=typer.colors.BRIGHT_RED)
        raise typer.Exit(1)


@deploy_commands_app.command("deploy")
def deploy() -> None:
    """
    Deploy the application with the given deployment ID.
    """
    deployment_id = uuid.uuid4()
    typer.secho(
        f"Deploying application with deployment ID: {deployment_id}",
        fg=typer.colors.BRIGHT_BLUE,
    )
    config = load_config()
    app_id = config.get("application", {}).get("application_uid_dev", {})
    api = APIClient(base_url=DEPLOYMENT_BASE_URL)
    services_payload, services = upload_services_config_to_s3(deployment_id, app_id)
    payload = {"deployment_id": str(deployment_id), "services": services_payload, "app_id": app_id}
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
