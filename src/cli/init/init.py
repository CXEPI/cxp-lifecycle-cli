import json

import typer
from pathlib import Path

import yaml
from cli.helpers.api_client import APIClient
from cli.helpers.file import save_config
from cli.helpers.prompts import prompt_application, prompt_core_services
from cli.helpers.path_utils import get_lifecycle_path, to_posix_path


def create_lifecycle_folder():
    """
    Create the lifecycle folder if it doesn't exist.
    """
    lifecycle_path = get_lifecycle_path()
    lifecycle_path.mkdir(exist_ok=True)
    return lifecycle_path


def create_lifecycle_envs_folder(lifecycle_path):
    """
    Create the lifecycle_envs folder inside the lifecycle folder and populate it with empty environment files (with example comment).
    """
    env_folder = lifecycle_path / "lifecycle_envs"
    env_folder.mkdir(exist_ok=True)
    env_files = {
        "sandbox.env": "# Example: CONNECTOR_NAME=sandbox-connector\n",
        "dev.env": "# Example: CONNECTOR_NAME=dev-connector\n",
        "nprd.env": "# Example: CONNECTOR_NAME=nprd-connector\n",
        "prod.env": "# Example: CONNECTOR_NAME=prod-connector\n",
    }
    for filename, content in env_files.items():
        env_path = env_folder / filename
        if not env_path.exists():
            with open(env_path, "w") as f:
                f.write(content)


def fetch_schema(api, schema_name):
    """
    Fetch the schema from the API.
    """
    if "/" in schema_name:
        path, schema_name = schema_name.rsplit("/", 1)
        response = api.get(f"/schemas/schema/{schema_name}?path={path}")
    else:
        response = api.get(f"/schemas/schema/{schema_name}")
    if response.status_code != 200:
        typer.secho(
            f"✘ Failed to fetch schema {schema_name}: {response.status_code} - {response.reason}",
            fg=typer.colors.RED,
            bold=True,
        )
        return {}
    new_json = response.json()
    if schema_name in ['etl_instance', 'etl_template']:
        new_json["example_instance"] = ""
    else:
        new_json["example_instance"] = {}
    new_json["json_schema"] = response.json()
    return new_json


def write_schema_files(schema_data: dict, schema_path: Path, example_path: Path):
    """
    Write schema and example files.
    - json_schema is always JSON
    - example_instance may be JSON (dict) or YAML (string)
    """
    schema_json = json.dumps(schema_data["json_schema"], indent=2)
    schema_path.write_text(schema_json, encoding="utf-8")

    example_instance = schema_data["example_instance"]
    if isinstance(example_instance, str):
        example_path = example_path.with_suffix(".yaml.example")
        example_path.write_text(example_instance, encoding="utf-8")
    else:
        example_path = example_path.with_suffix(".json.example")
        example_json = json.dumps(example_instance, indent=2)
        example_path.write_text(example_json, encoding="utf-8")

def create_service_folders(lifecycle_path, core_services, api):
    """
    Create folders for core services and fetch additional schemas if required.
    """
    def process_schema(schema_name: str, base_path: Path, base_filename: str):
        schema_data = fetch_schema(api, schema_name)
        if not schema_data:
            return
        schema_path = base_path / f"{base_filename}_schema.json.example"
        example_path = base_path / f"{base_filename}_example"  # suffix decided in write
        write_schema_files(schema_data, schema_path, example_path)

    for service in core_services:
        service_path = lifecycle_path / service
        service_path.mkdir(parents=True, exist_ok=True)

        if service == "data_fabric":
            folders = ["connectors", "data_models", "etl_instances", "etl_templates", "tables"]
            for folder in folders:
                folder_path = service_path / folder
                (folder_path / "_local").mkdir(parents=True, exist_ok=True)
                process_schema(f"{folder}/{folder}_example.json", folder_path, folder)

            # Data model folders
            data_model_path = service_path / "data_models" / "model_name_example"
            data_model_folders = ["entity", "relationship", "type"]
            for folder in data_model_folders:
                folder_path = data_model_path / folder
                (folder_path / "_local").mkdir(parents=True, exist_ok=True)
                process_schema(f"data_models/model_name_example/{folder}/{folder}_example.json", folder_path, folder)

            # Model metadata
            process_schema(
                "data_models/model_name_example/model_name_metadata.json",
                data_model_path,
                "model_name_metadata"
            )

        else:
            (service_path / "_local").mkdir(parents=True, exist_ok=True)
            process_schema(f"{service}.json", service_path, service)

    return {
        service: str((lifecycle_path / service).relative_to(lifecycle_path.parent))
        for service in core_services
    }


def init():
    """
    Initializes and writes app metadata to a YAML config file.
    """
    lifecycle_path = create_lifecycle_folder()
    create_lifecycle_envs_folder(lifecycle_path)
    api = APIClient()
    print("Base URI:", api.base_url)
    print("Environment: ", api.env)
    schema = fetch_schema(api, "config.json")
    if schema == {}:
        raise typer.Exit(1)

    application = prompt_application(schema)
    core_services = prompt_core_services(schema)

    core_services_dict = create_service_folders(lifecycle_path, core_services, api)

    config = {
        "application": application,
        "core_services": core_services_dict,
    }

    save_config(config)
    typer.secho("✅ Created lifecycle folders and config file", fg=typer.colors.GREEN)

    if core_services:
        typer.secho(
            f"✅ Created folders for services: {', '.join(core_services)}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            "No core services selected, so no folders created.", fg=typer.colors.RED
        )
