from pathlib import Path
import re
import json
import yaml

from cli.config import CONFIG_FILE
import typer

config_path = Path("lifecycle") / CONFIG_FILE


def load_config() -> dict:
    if not config_path.is_file():
        typer.secho(f"Config file not found: {CONFIG_FILE}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    with config_path.open("r") as f:
        return yaml.safe_load(f)


def save_config(config: dict):
    with config_path.open("w") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def load_env(env_path: str) -> dict:
    """Load environment variables from a .env file into a dictionary."""
    env_vars = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def inject_env_into_schema(schema_path: str, env_vars: dict) -> str:
    """Inject environment variables into all string values in a JSON schema file and return the modified content as a string."""
    with open(schema_path, "r") as f:
        if schema_path.endswith(".yaml") or schema_path.endswith(".yml"):
            data = yaml.safe_load(f)
        elif schema_path.endswith(".json"):
            data = json.load(f)

    def replace_in_obj(obj):
        if isinstance(obj, dict):
            return {k: replace_in_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_in_obj(item) for item in obj]
        elif isinstance(obj, str):
            # Replace ${LC.VAR_NAME} with env_vars[VAR_NAME]
            def replacer(match):
                var_name = match.group(1)
                if var_name in env_vars:
                    return env_vars[var_name]
                else:
                    raise ValueError(
                        f"Environment variable '{var_name}' is not defined in the environment file"
                    )

            return re.sub(r"\$\{LC\.([A-Za-z0-9_]+)\}", replacer, obj)
        else:
            return obj

    injected_data = replace_in_obj(data)
    if schema_path.endswith(".json"):
        return json.dumps(injected_data, indent=2)
    elif schema_path.endswith(".yaml"):
        return yaml.dump(injected_data, sort_keys=False)
    return ""
