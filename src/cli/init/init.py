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
    return response.json()


def _create_data_fabric_service_folder(service_path, service, api):
    """
    Creates the folder structure for the data_fabric service.
    """
    with open(service_path / "commands.txt", "w", encoding="utf-8") as schema_file:
        schema_file.write("#Create Connector connectors/connectors.example.json")
    folders = [
        "connectors",
        "etl_instances",
        "etl_templates",
        "tables",
        "data_models"
    ]
    for folder in folders:
        folder_no_plural = folder.rstrip("s")
        (service_path / folder).mkdir(parents=True, exist_ok=True)
        if folder == "data_models":
            (service_path / "data_models" / "sample").mkdir(parents=True, exist_ok=True)
            folder = "data_models/sample"

        schema_response = fetch_schema(api, f"{service}/{folder_no_plural}")
        if not schema_response:
            continue

        json_schema = schema_response.get("jsonSchema", {})
        example_instance = schema_response.get("exampleInstance", {})

        json_schema_path = service_path / folder / f"{folder_no_plural}_json_schema.example.json"
        example_instance_path = service_path / folder / f"{folder_no_plural}_example"
        if folder in ["etl_templates", "etl_instances"]:
            example_instance_path = example_instance_path.with_suffix(".example.yaml")
        else:
            example_instance_path = example_instance_path.with_suffix(".example.json")

        with open(json_schema_path, "w", encoding="utf-8") as schema_file:
            schema_file.write(json.dumps(json_schema, indent=2))
        with open(example_instance_path, "w", encoding="utf-8") as example_file:
            if folder in ["etl_templates", "etl_instances"]:
                if isinstance(example_instance, str):
                    example_file.write(example_instance)
                else:
                    yaml.dump(example_instance, example_file, sort_keys=False)
            else:
                example_file.write(json.dumps(example_instance, indent=2))

        if folder == "data_models/sample":
            sub_folders = ["entity", "relationship", "type"]
            for sub_folder in sub_folders:
                folder_path = service_path / folder / sub_folder
                folder_path.mkdir(parents=True, exist_ok=True)

                schema_response = fetch_schema(api, f"{service}/{folder_no_plural}_{sub_folder}")
                if not schema_response:
                    continue

                json_schema = schema_response.get("jsonSchema", {})
                example_instance = schema_response.get("exampleInstance", {})

                json_schema_path = service_path / folder / sub_folder / f"{sub_folder}_json_schema.example.json"
                example_instance_path = service_path / folder / sub_folder / f"{sub_folder}_example.example.json"

                with open(json_schema_path, "w", encoding="utf-8") as schema_file:
                    schema_file.write(json.dumps(json_schema, indent=2))
                with open(example_instance_path, "w", encoding="utf-8") as example_file:
                    example_file.write(json.dumps(example_instance, indent=2))


def _create_simple_service_folder(service_path, service, api):
    """
    Creates a folder for a simple service with a single schema file.
    """
    schema_response = fetch_schema(api, service)
    if not schema_response:
        return

    json_schema_path = service_path  / f"{service}_json_schema.example.json"
    example_instance_path = service_path  / f"{service}_example.example.json"

    json_schema = schema_response.get("jsonSchema", {})
    example_instance = schema_response.get("exampleInstance", {})

    with open(json_schema_path, "w", encoding="utf-8") as schema_file:
        schema_file.write(json.dumps(json_schema, indent=2))
    with open(example_instance_path, "w", encoding="utf-8") as example_file:
        example_file.write(json.dumps(example_instance, indent=2))


def create_service_folders(lifecycle_path, core_services, api):
    """
    Create folders for core services and fetch additional schemas if required.
    """
    for service in core_services:
        service_path = lifecycle_path / service
        service_path.mkdir(parents=True, exist_ok=True)

        if service == "data_fabric":
            _create_data_fabric_service_folder(service_path, service, api)
        elif service in ["iam", "baqs", "agent"]:
            _create_simple_service_folder(service_path, service, api)

    return {
        service: to_posix_path(
            (lifecycle_path / service).relative_to(lifecycle_path.parent)
        )
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
