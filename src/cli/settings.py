from pydantic_settings import BaseSettings
from os.path import expanduser
import json
from pathlib import Path
from typing import Optional


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


class VersionCheckSettings:
    """
    Settings for version checking behavior.
    Stored in ~/.cx-cli/config.json
    """

    def __init__(self):
        self.config_file = Path(expanduser("~/.cx-cli/config.json"))
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception:
            pass

    @property
    def check_enabled(self) -> bool:
        """Whether version checking is enabled."""
        return self._config.get("version-check-enabled", True)

    @check_enabled.setter
    def check_enabled(self, value: bool) -> None:
        """Set whether version checking is enabled."""
        self._config["version-check-enabled"] = value
        self._save_config()

    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a configuration value."""
        self._config[key] = value
        self._save_config()


general_config = GeneralCliSettings()
api_validation_config = APIValidationSettings()
version_check_config = VersionCheckSettings()
