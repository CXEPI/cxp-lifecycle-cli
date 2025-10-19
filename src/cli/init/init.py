import json

import typer
from pathlib import Path

import yaml
from cli.helpers.api_client import APIClient
from cli.helpers.file import save_config
from cli.helpers.prompts import prompt_application, prompt_core_services


def create_lifecycle_folder():
    """
    Create the lifecycle folder if it doesn't exist.
    """
    lifecycle_path = Path("lifecycle")
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

def parse_schema(schema, folder_path, schema_name):
    schema_json = json.loads(schema)
    json_schema = schema_json.get("jsonSchema")
    with open(folder_path / f"{schema_name}_json_schema.example.json", "w", encoding="utf-8") as schema_file:
        json.dump(json_schema, schema_file, sort_keys=False)

    example_instance = schema_json.get("exampleInstance")
    example_instance_path = folder_path / f"{schema_name}_instance.example"
    if example_instance and type(example_instance) != dict:
        with open(example_instance_path + ".yaml", "w", encoding="utf-8") as schema_file:
            yaml.dump(example_instance, schema_file, sort_keys=False)
    else:
        with open(example_instance_path + ".json", "w", encoding="utf-8") as schema_file:
            json.dump(example_instance, schema_file, sort_keys=False)


def create_service_folders(lifecycle_path, core_services, api):
    """
    Create folders for core services and fetch additional schemas if required.
    """
    for service in core_services:
        service_path = lifecycle_path / service
        service_path.mkdir(parents=True, exist_ok=True)

        if service == "data_fabric":
            with open(service_path / "commands.txt", "w", encoding="utf-8") as schema_file:
                schema_file.write("#Create Connector connectors/connectors.example.json")
            folders = [
                "connectors",
                "etl_instances",
                "etl_templates",
                "tables",
            ]

            for folder in folders:
                folder_path = (service_path / folder)
                schema_name = f"{folder[:-1]}"
                folder_path.mkdir(parents=True, exist_ok=True)
                schema = fetch_schema(api, f"data_fabric/{schema_name}")
                parse_schema(schema, folder_path, schema_name)



            (service_path / "data_models").mkdir(parents=True, exist_ok=True)
            (service_path / "data_models" / "sample").mkdir(parents=True, exist_ok=True)
            schema = fetch_schema(api, "data_fabric/data_model")
            json_schema = schema.get("jsonSchema")
            parse_schema(json_schema, (service_path / "data_models" / "sample"), "data_model")


            snacks_folders = ["entity", "relationship", "type"]
            for folder in snacks_folders:
                folder_path = service_path / "data_models/sample" / folder
                folder_path.mkdir(parents=True, exist_ok=True)
                schema = fetch_schema(api, f"data_fabric/data_models_{folder}")
                with open(folder_path / f"{folder}.example.json", "w", encoding="utf-8") as schema_file:
                    schema_file.write(json.dumps(schema, indent=2))

        if service == "iam" or service == "baqs":
            schema = fetch_schema(api, f"{service}.json")
            schema_path = service_path / f"{service}.json"
            schema_json = json.dumps(schema, indent=2)
            with open(schema_path, "w", encoding="utf-8") as schema_file:
                schema_file.write(schema_json)

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
    print("base url:", api.base_url)
    print("env: ", api.env)
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
    typer.secho(f"Created lifecycle folders and config file", fg=typer.colors.GREEN)

    if core_services:
        typer.secho(
            f"Created folders for services: {', '.join(core_services)}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            "No core services selected, so no folders created.", fg=typer.colors.RED
        )
