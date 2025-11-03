import base64

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
from cli.config import (
    CONFIG_FILE,
    BASE_URL_BY_ENV,
    ENVIRONMENTS,
)
from cli.helpers.api_client import APIClient
from cli.helpers.errors import handle_request_error, handle_env_error
from cli.helpers.file import load_config, save_config


def create_application(api, config):
    """
    Create a new application in IAM and return application details.
    """
    typer.secho("🚀 Starting Create Application...", fg=typer.colors.BRIGHT_MAGENTA)
    create_application_url = "/cxp-iam/api/v1/applications"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ):

        try:
            application_metadata = config.get("application", {})
            application_name = (
                application_metadata.get("display_name")
                .strip()
                .lower()
                .replace(" ", "-")
            )
            application_uid = application_metadata.get("application_uid")
            payload = {
                "name": application_name,
                "displayName": application_metadata.get("display_name"),
                "description": application_metadata.get("description"),
                "contact": application_metadata.get("lead_developer_email"),
                "version": application_metadata.get("app_version"),
                "git": application_metadata.get("github_url"),
            }
            if application_uid:
                payload["id"] = application_uid
            response = api.post(
                create_application_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            typer.secho("✅ Application created successfully!", fg=typer.colors.BRIGHT_GREEN)
            return response.json()

        except requests.exceptions.RequestException as error:
            typer.secho("❌ Failed to create application.", fg=typer.colors.RED)
            handle_request_error(error)
            raise typer.Exit(code=1)


def get_platform_services(env):
    """Get platform services for the specified environment"""
    api = APIClient()
    response = api.get("/schemas/get_platform_services")
    if response.status_code != 200:
        typer.secho(
            f"✘ Failed to fetch platform services: {response.status_code} - {response.reason}",
            fg=typer.colors.RED,
            bold=True,
        )
        raise typer.Exit(1)
    platform_services = response.json()
    return platform_services.get(env, platform_services.get("dev", []))


def assign_roles(api, application_details, env):
    """
    Assign roles for platform services to the application.
    """
    client_id = application_details.get("clientId")
    assign_roles_url = f"/cxp-iam/api/v1/users/{client_id}"
    services = get_platform_services(env)
    typer.secho(
        f"🔑 Assigning Roles for Platform services in {env} environment: {', '.join(service['name'] for service in services)}...",
        fg=typer.colors.CYAN,
    )

    for service in services:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                f"Assigning Roles for Platform service {service['name']}...", start=True
            )

            try:
                response = api.put(
                    assign_roles_url,
                    json={
                        "status": "ACTIVE",
                        "assignRoles": [
                            {"id": service["role_id"], "name": service["role_name"]}
                        ],
                    },
                    timeout=10,
                )
                response.raise_for_status()
                typer.secho(f"\n✅ Assigned role for {service['name']} successfully!", fg=typer.colors.BRIGHT_GREEN)

            except requests.exceptions.RequestException as error:
                progress.update(task, description="❌ Failed to assign role.")
                handle_request_error(error)
                raise typer.Exit(code=1)


def generate_service_credentials(application_details):
    """
    Generate and display service credentials for the application.
    """
    credentials_raw = (
        f"{application_details.get('clientId')}:{application_details.get('secret')}"
    )
    credentials = base64.b64encode(credentials_raw.encode("utf-8")).decode("utf-8")
    typer.secho(
        f"\n\n🔒 Your Service account secret is: {credentials}", fg=typer.colors.MAGENTA
    )
    typer.secho("⚠️ Please copy this secret and store it securely, it will not be shown again.", fg=typer.colors.BRIGHT_YELLOW)


def register(
    env: str = typer.Argument(
        ...,
        help=f"Environment (one of: {', '.join(ENVIRONMENTS)})",
        show_default=False,
        case_sensitive=False,
    )
):
    """
    Register the app in IAM and return service credentials.
    """
    handle_env_error(env)
    typer.secho("📦 Registering a new application...", fg=typer.colors.BRIGHT_BLUE)
    config = load_config()
    api = APIClient(base_url=BASE_URL_BY_ENV[env], env=env)
    print("base url:", api.base_url)
    print("env: ", api.env)
    application_details = create_application(api, config)

    config["application"]["application_uid"] = application_details.get("id")
    save_config(config)
    typer.secho(
        f"📄 Updated application_uid in config file: {CONFIG_FILE}",
        fg=typer.colors.GREEN,
    )

    assign_roles(api, application_details, env)
    generate_service_credentials(application_details)
