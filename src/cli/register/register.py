import base64
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
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
    ) as progress:
        task = progress.add_task("Creating application...", start=True)

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
            typer.secho("✅ Application created successfully!")
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
                    json={'status':"ACTIVE", 'assignRoles':[{"id": service["role_id"], "name": service["role_name"]}]},
                    timeout=10,
                )
                response.raise_for_status()
                typer.secho(f"✅ Assigned role for {service['name']} successfully!")

            except requests.exceptions.RequestException as error:
                progress.update(task, description=f"❌ Failed to assign role.")
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
        f"🔒 Your Service account secret is: {credentials}", fg=typer.colors.GREEN
    )
    typer.secho("⚠️ The secret will be shown only once.", fg=typer.colors.BRIGHT_YELLOW)


def delete_application_from_iam(api, application_id):
    """
    Delete an application from IAM service (rollback operation).
    
    Args:
        api: APIClient instance
        application_id: The ID of the application to delete
    """
    try:
        delete_url = f"/cxp-iam/api/v1/applications/{application_id}"
        response = api.delete(delete_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        typer.secho(
            "⚠️  Warning: Cleanup failed. Partial data may remain in the system.",
            fg=typer.colors.YELLOW
        )
        typer.secho(
            f"   Application ID: {application_id}",
            fg=typer.colors.YELLOW
        )
        typer.secho(
            "   Please contact support for assistance with cleanup.",
            fg=typer.colors.YELLOW
        )


def create_application_in_developer_studio(api, application_details):
    """
    Create application in Developer Studio service with retry mechanism.
    Maximum total time: ~30 seconds (3 attempts * 8 seconds timeout + 6 seconds wait time)
    """
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=4),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError))
    )
    def _fetch_account_id():
        """Fetch accountId from users/me endpoint with retry"""
        me_response = api.get("/cxp-iam/api/v1/users/me", timeout=5)
        me_response.raise_for_status()
        me_data = me_response.json()
        account_id = me_data.get("associatedAccount", {}).get("id")
        
        if not account_id:
            raise ValueError("accountId not found in user profile response")
        
        return account_id
    
    try:
        account_id = _fetch_account_id()
    except (requests.exceptions.RequestException, ConnectionError) as error:
        typer.secho(
            "❌ Registration failed: Unable to retrieve your account information.",
            fg=typer.colors.RED
        )
        typer.secho(
            "   This may be due to network issues or service unavailability.",
            fg=typer.colors.YELLOW
        )
        typer.secho(
            "   Please try again later or contact support if the problem persists.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    except ValueError as error:
        typer.secho(
            "❌ Registration failed: Your account is missing required information.",
            fg=typer.colors.RED
        )
        typer.secho(
            "   Please contact support to verify your account setup.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=4),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError))
    )
    def _create():
        create_ds_url = "/lifecycle/api/v1/deployment/applications"
        payload = {
            "id": application_details.get("id"),  # Required - uuid from IAM
            "name": application_details.get("name"),  # Required
            "accountId": account_id,  # Required - fetched from /users/me
            "description": application_details.get("description"),  # Optional
            "leadDeveloper": application_details.get("contact"),  # Required - using contact from IAM
            "gitRepository": application_details.get("git"),  # Required - using git from IAM
            "applicationUrl": None  # Optional
        }
        response = api.post(create_ds_url, json=payload, timeout=8)
        response.raise_for_status()
        return response.json()

    try:
        return _create()
    except requests.exceptions.HTTPError as e:
        # Parse HTTP error for specific user-friendly messages
        status_code = e.response.status_code if e.response else None
        
        if status_code == 409:
            typer.secho(
                "❌ Registration failed: An application with this ID already exists.",
                fg=typer.colors.RED
            )
            typer.secho(
                f"   Application ID: {application_details.get('id')}",
                fg=typer.colors.YELLOW
            )
            typer.secho(
                "   Please check if this application was already registered or contact support.",
                fg=typer.colors.YELLOW
            )
        elif status_code == 400:
            typer.secho(
                "❌ Registration failed: Invalid application data provided.",
                fg=typer.colors.RED
            )
            typer.secho(
                "   Please verify your application configuration in lifecycle_config.yaml.",
                fg=typer.colors.YELLOW
            )
        elif status_code == 403:
            typer.secho(
                "❌ Registration failed: Access denied.",
                fg=typer.colors.RED
            )
            typer.secho(
                "   Your account may not have permission to register applications.",
                fg=typer.colors.YELLOW
            )
            typer.secho(
                "   Please contact your administrator or support.",
                fg=typer.colors.YELLOW
            )
        elif status_code == 503 or status_code == 504:
            typer.secho(
                "❌ Registration failed: Service temporarily unavailable.",
                fg=typer.colors.RED
            )
            typer.secho(
                "   Please try again in a few minutes.",
                fg=typer.colors.YELLOW
            )
        else:
            typer.secho(
                "❌ Registration failed: An unexpected error occurred.",
                fg=typer.colors.RED
            )
            typer.secho(
                f"   Error: {str(e)}",
                fg=typer.colors.YELLOW
            )
            typer.secho(
                "   Please try again later or contact support if the problem persists.",
                fg=typer.colors.YELLOW
            )
        raise typer.Exit(code=1)
    except (ConnectionError, requests.exceptions.ConnectionError) as e:
        typer.secho(
            "❌ Registration failed: Unable to connect to the service.",
            fg=typer.colors.RED
        )
        typer.secho(
            "   Please check your network connection and try again.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
        typer.secho(
            "❌ Registration failed: The request timed out.",
            fg=typer.colors.RED
        )
        typer.secho(
            "   The service may be experiencing high load. Please try again later.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    except RetryError as e:
        typer.secho(
            "❌ Registration failed: Service unavailable after multiple attempts.",
            fg=typer.colors.RED
        )
        typer.secho(
            "   Please try again later or contact support if the problem persists.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(
            "❌ Registration failed: An unexpected error occurred.",
            fg=typer.colors.RED
        )
        typer.secho(
            f"   Error: {str(e)}",
            fg=typer.colors.YELLOW
        )
        typer.secho(
            "   Please try again later or contact support.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)

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
    
    # Create application in Developer Studio with rollback mechanism
    try:
        create_application_in_developer_studio(api, application_details)
    except typer.Exit:
        # If Developer Studio creation fails, rollback by deleting the IAM application
        typer.secho(
            "❌ Failed to create application in Developer Studio. Initiating rollback...",
            fg=typer.colors.RED
        )
        delete_application_from_iam(api, application_details.get("id"))
        typer.secho(
            "❌ Registration failed. The application was not created.",
            fg=typer.colors.RED,
            bold=True
        )
        raise typer.Exit(code=1)

    config["application"]["application_uid"] = application_details.get("id")
    save_config(config)
    typer.secho(
        f"📄 Updated application_uid in config file: {CONFIG_FILE}",
        fg=typer.colors.GREEN,
    )

    assign_roles(api, application_details, env)
    generate_service_credentials(application_details)
