from pydantic_settings import BaseSettings
from os.path import expanduser


class GeneralCliSettings(BaseSettings):
    """
    General settings for the CLI application
    """

    creds_filename: str = f"{expanduser('~')}/.cx-cli/credentials.json"
    required_fields_in_credentials_file: set[str] = {"serviceAccounts"}
    cx_cli_service_accounts_credentials: dict = {}


class APIValidationSettings(BaseSettings):
    """
    General settings for the CLI application
    """

    ruleset_path: str = "cli.api.ruleset"
    ruleset_filename: str = ".spectral.yaml"


general_config = GeneralCliSettings()
api_validation_config = APIValidationSettings()
