from pathlib import Path

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
