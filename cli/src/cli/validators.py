import os
import typer
from cli.settings import general_config

import json


class FileStructureError(Exception):
    """Raised when the file exists but its internal structure is invalid."""

    ...


def creds_existance(file_path: str) -> bool:
    """
    Validate that the credentials file exists and is a valid JSON.
    This is a placeholder for the actual validation logic.
    """
    print(f"Validating credentials file at {general_config.creds_filename}")
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

            general_config.service_credentials = service_accounts
            print("Credentials file validated successfully.")
            return True
        else:
            raise KeyError(creds_file_keys)
    except KeyError as MissingData:
        raise FileStructureError(f"Missing required {general_config.required_fields_in_credentials_file} in: {MissingData}")
    except json.decoder.JSONDecodeError as json_error:
        raise FileStructureError(
            f"Invalid JSON format in credentials file: {json_error}"
        )
    except Exception as error:
        raise FileStructureError(f"Invalid credentials file structure: {error}")


def validate_creds() -> None:
    """
    Decorator that *always* verifies that creds file path exists
    and passes validation on the creds file before executing `func`.
    """
    try:
        creds_existance(general_config.creds_filename)
    except Exception as error:
        typer.secho(
            f"{error.__class__.__name__}: {error}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1)
