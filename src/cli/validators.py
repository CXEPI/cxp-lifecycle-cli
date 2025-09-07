import os
import typer
from cli.settings import general_config
import json
from pathlib import Path


class FileStructureError(Exception):
    """Raised when the file exists but its internal structure is invalid."""

    ...


def creds_existance(file_path: str) -> bool:
    """
    Validate that the credentials file exists and is a valid JSON.
    This is a placeholder for the actual validation logic.
    """
    # Clear existing credentials to ensure we always load from file when explicitly provided
    if file_path != general_config.creds_filename:
        general_config.cx_cli_service_accounts_credentials = {}

    print(f"Validating credentials file at {file_path}")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Required config file '{file_path}' not found")
    try:
        with open(file_path, "r") as f:
            file_content = json.loads(f.read())
            creds_file_keys = set(file_content.keys())
        if general_config.required_fields_in_credentials_file.issubset(creds_file_keys):
            service_accounts = file_content["serviceAccounts"]
            if not isinstance(service_accounts, dict):
                raise FileStructureError(
                    "serviceAccounts must be a dictionary with environment keys"
                )

            # Store the credentials in general_config
            general_config.cx_cli_service_accounts_credentials = service_accounts
            # Store the current creds file path in general_config
            general_config.creds_filename = file_path
            print("Credentials file validated successfully.")
            return True
        else:
            raise KeyError(creds_file_keys)
    except KeyError as MissingData:
        raise FileStructureError(
            f"Missing required {general_config.required_fields_in_credentials_file} in: {MissingData}"
        )
    except json.decoder.JSONDecodeError as json_error:
        raise FileStructureError(
            f"Invalid JSON format in credentials file: {json_error}"
        )
    except Exception as error:
        raise FileStructureError(f"Invalid credentials file structure: {error}")


def validate_creds(creds_path: str = None) -> None:
    """
    Validates that the credentials file exists and passes validation.

    Args:
        creds_path: Optional custom path to credentials file. If not provided,
                    the default path from general_config will be used.
    """
    # Simple caching to avoid redundant validation of the same path
    # If we've already validated with this exact path and have credentials loaded, skip
    last_path = getattr(general_config, "_last_validated_path", None)
    if creds_path == last_path and general_config.cx_cli_service_accounts_credentials:
        return

    if creds_path:
        # If creds_path is a directory, append "credentials.json" to it
        path = Path(creds_path)
        if path.is_dir():
            file_path = os.path.join(creds_path, "credentials.json")
        else:
            file_path = creds_path
    else:
        file_path = general_config.creds_filename

    try:
        creds_existance(file_path)
        # Remember this path to avoid duplicate validation
        general_config._last_validated_path = creds_path
    except Exception as error:
        typer.secho(
            f"{error.__class__.__name__}: {error}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1)
