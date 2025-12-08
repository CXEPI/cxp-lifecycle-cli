import json
import os
from pathlib import Path

import typer
import jsonschema
from jsonschema import validate as validate_json, ValidationError

from cli.helpers.api_client import APIClient
from cli.helpers.file import load_config
from cli.helpers.path_utils import get_lifecycle_path
from cli.helpers.prompts import prompt_service_selection
from cli.init.init import fetch_schema


def get_files_to_validate(service_path: Path) -> list[Path]:
    """
    Get all JSON/YAML files in the service folder that don't have '.example' in their name.
    """
    files_to_validate = []

    for root, dirs, files in os.walk(service_path):
        for file in files:
            # Skip files with .example in the name
            if ".example" in file:
                continue
            # Only validate JSON and YAML files
            if file.endswith((".json", ".yaml", ".yml")):
                files_to_validate.append(Path(root) / file)

    return files_to_validate


def load_file_content(file_path: Path) -> dict | None:
    """
    Load and parse a JSON or YAML file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.suffix in [".yaml", ".yml"]:
                import yaml
                return yaml.safe_load(f)
            else:
                return json.load(f)
    except json.JSONDecodeError as e:
        typer.secho(
            f"  ⚠️  {file_path.name}: Invalid JSON - {e}",
            fg=typer.colors.YELLOW,
        )
        return None
    except Exception as e:
        typer.secho(
            f"  ⚠️  {file_path.name}: Error reading file - {e}",
            fg=typer.colors.YELLOW,
        )
        return None


def validate_file_against_schema(file_path: Path, json_schema: dict) -> list[str]:
    """
    Validate a file against a JSON schema.
    Returns a list of validation error messages.
    """
    errors = []

    content = load_file_content(file_path)
    if content is None:
        return ["Failed to parse file"]

    try:
        validate_json(instance=content, schema=json_schema)
    except ValidationError as e:
        # Get the path to the error in the document
        error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        errors.append(f"{error_path}: {e.message}")
    except jsonschema.exceptions.SchemaError as e:
        errors.append(f"Schema error: {e.message}")

    return errors


def validate_simple_service(service_name: str, service_path: Path, api: APIClient) -> tuple[int, int]:
    """
    Validate files for a simple service (iam, baqs, agent).
    """
    typer.secho(f"\n📁 Validating {service_name.upper()}...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Fetch the schema
    schema_response = fetch_schema(api, service_name)
    if not schema_response:
        typer.secho(f"  ⚠️  Could not fetch schema for {service_name}", fg=typer.colors.YELLOW)
        return 0, 1

    json_schema = schema_response.get("jsonSchema", {})
    if not json_schema:
        typer.secho(f"  ⚠️  No JSON schema found for {service_name}", fg=typer.colors.YELLOW)
        return 0, 1

    files_to_validate = get_files_to_validate(service_path)

    if not files_to_validate:
        typer.secho(f"  ℹ️  No files to validate", fg=typer.colors.CYAN)
        return 0, 0

    files_validated = 0
    errors_found = 0

    for file_path in files_to_validate:
        relative_path = file_path.relative_to(service_path)
        validation_errors = validate_file_against_schema(file_path, json_schema)
        files_validated += 1

        if validation_errors:
            errors_found += len(validation_errors)
            typer.secho(f"  ⚠️  {relative_path}:", fg=typer.colors.YELLOW)
            for error in validation_errors:
                typer.secho(f"      - {error}", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"  ✅ {relative_path}", fg=typer.colors.GREEN)

    return files_validated, errors_found


def validate_data_fabric_service(service_path: Path, api: APIClient) -> tuple[int, int]:
    """
    Validate files for the data_fabric service with its nested folder structure.
    """
    typer.secho(f"\n📁 Validating DATA_FABRIC...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    total_files = 0
    total_errors = 0

    # Define the folder structure and their corresponding schema names
    folders = {
        "connectors": "data_fabric/connector",
        "etl_instances": "data_fabric/etl_instance",
        "etl_templates": "data_fabric/etl_template",
        "tables": "data_fabric/table",
    }

    for folder_name, schema_name in folders.items():
        folder_path = service_path / folder_name
        if not folder_path.exists():
            continue

        typer.secho(f"\n  📂 {folder_name}/", fg=typer.colors.CYAN)

        # Fetch schema for this folder type
        schema_response = fetch_schema(api, schema_name)
        if not schema_response:
            typer.secho(f"    ⚠️  Could not fetch schema for {schema_name}", fg=typer.colors.YELLOW)
            total_errors += 1
            continue

        json_schema = schema_response.get("jsonSchema", {})
        if not json_schema:
            typer.secho(f"    ⚠️  No JSON schema found for {schema_name}", fg=typer.colors.YELLOW)
            total_errors += 1
            continue

        # Get files directly in this folder (not recursive for data_fabric subfolders)
        files_to_validate = [
            f for f in folder_path.iterdir()
            if f.is_file()
            and ".example" not in f.name
            and f.suffix in [".json", ".yaml", ".yml"]
        ]

        if not files_to_validate:
            typer.secho(f"    ℹ️  No files to validate", fg=typer.colors.CYAN)
            continue

        for file_path in files_to_validate:
            validation_errors = validate_file_against_schema(file_path, json_schema)
            total_files += 1

            if validation_errors:
                total_errors += len(validation_errors)
                typer.secho(f"    ⚠️  {file_path.name}:", fg=typer.colors.YELLOW)
                for error in validation_errors:
                    typer.secho(f"        - {error}", fg=typer.colors.YELLOW)
            else:
                typer.secho(f"    ✅ {file_path.name}", fg=typer.colors.GREEN)

    # Handle data_models separately with its nested structure
    data_models_path = service_path / "data_models"
    if data_models_path.exists():
        typer.secho(f"\n  📂 data_models/", fg=typer.colors.CYAN)

        # Iterate through each data model folder (e.g., "sample")
        for model_folder in data_models_path.iterdir():
            if not model_folder.is_dir():
                continue

            typer.secho(f"\n    📂 {model_folder.name}/", fg=typer.colors.CYAN)

            sub_folders = {
                "entity": "data_fabric/data_model_entity",
                "relationship": "data_fabric/data_model_relationship",
                "type": "data_fabric/data_model_type",
            }

            for sub_folder_name, schema_name in sub_folders.items():
                sub_folder_path = model_folder / sub_folder_name
                if not sub_folder_path.exists():
                    continue

                typer.secho(f"\n      📂 {sub_folder_name}/", fg=typer.colors.CYAN)

                schema_response = fetch_schema(api, schema_name)
                if not schema_response:
                    typer.secho(f"        ⚠️  Could not fetch schema for {schema_name}", fg=typer.colors.YELLOW)
                    total_errors += 1
                    continue

                json_schema = schema_response.get("jsonSchema", {})
                if not json_schema:
                    typer.secho(f"        ⚠️  No JSON schema found for {schema_name}", fg=typer.colors.YELLOW)
                    total_errors += 1
                    continue

                files_to_validate = [
                    f for f in sub_folder_path.iterdir()
                    if f.is_file()
                    and ".example" not in f.name
                    and f.suffix in [".json", ".yaml", ".yml"]
                ]

                if not files_to_validate:
                    typer.secho(f"        ℹ️  No files to validate", fg=typer.colors.CYAN)
                    continue

                for file_path in files_to_validate:
                    validation_errors = validate_file_against_schema(file_path, json_schema)
                    total_files += 1

                    if validation_errors:
                        total_errors += len(validation_errors)
                        typer.secho(f"        ⚠️  {file_path.name}:", fg=typer.colors.YELLOW)
                        for error in validation_errors:
                            typer.secho(f"            - {error}", fg=typer.colors.YELLOW)
                    else:
                        typer.secho(f"        ✅ {file_path.name}", fg=typer.colors.GREEN)

    return total_files, total_errors


def validate(
    creds_path: str = typer.Option(
        None,
        help="Path to credentials file. If not provided, the default path will be used.",
    ),
    validate_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Validate all services without confirmation prompts",
    ),
) -> None:
    """
    Validate local configuration files against JSON schemas.
    """
    config = load_config()
    lifecycle_path = get_lifecycle_path()

    # Get all available services
    all_services = list(config.get("core_services", {}).keys())

    if not all_services:
        typer.secho(
            "No core services found in configuration. Run 'init' first.",
            fg=typer.colors.BRIGHT_RED,
        )
        raise typer.Exit(1)

    # Select services to validate
    if validate_all:
        services_to_validate = all_services
    else:
        selected_services = prompt_service_selection(
            all_services, "Select services to validate:"
        )

        if selected_services is None:
            typer.secho("Validation cancelled.", fg=typer.colors.BRIGHT_YELLOW)
            raise typer.Exit(0)

        services_to_validate = selected_services

    if not services_to_validate:
        typer.secho(
            "No services selected for validation.",
            fg=typer.colors.BRIGHT_MAGENTA,
        )
        raise typer.Exit(0)

    typer.secho(
        f"\n🔍 Validating services: {', '.join(services_to_validate)}",
        fg=typer.colors.BRIGHT_BLUE,
        bold=True,
    )

    typer.secho(
        f"❕Please note that files with \".example\" in their name are skipped during validation,\n"
        f"as they are treated as example files.\n",
        fg=typer.colors.YELLOW,
    )

    # Initialize API client
    api = APIClient(creds_path=creds_path)

    total_files_validated = 0
    total_errors_found = 0

    for service in services_to_validate:
        service_path = lifecycle_path / service

        if not service_path.exists():
            typer.secho(
                f"\n⚠️  Service folder not found: {service_path}",
                fg=typer.colors.YELLOW,
            )
            continue

        if service == "data_fabric":
            files, errors = validate_data_fabric_service(service_path, api)
        else:
            files, errors = validate_simple_service(service, service_path, api)

        total_files_validated += files
        total_errors_found += errors

    # Print summary
    typer.secho("\n" + "=" * 60, fg=typer.colors.BRIGHT_BLUE)
    typer.secho("Validation Summary", fg=typer.colors.BRIGHT_BLUE, bold=True)
    typer.secho("=" * 60, fg=typer.colors.BRIGHT_BLUE)
    typer.secho(f"  Files validated: {total_files_validated}", fg=typer.colors.BRIGHT_WHITE)

    if total_errors_found > 0:
        typer.secho(f"  Validation errors: {total_errors_found}", fg=typer.colors.BRIGHT_YELLOW)
        typer.secho("\n⚠️  Validation completed with warnings", fg=typer.colors.BRIGHT_RED, bold=True)
    else:
        typer.secho(f"  Validation errors: 0", fg=typer.colors.BRIGHT_GREEN)
        typer.secho("\n✅ All files validated successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)

    typer.secho("=" * 60, fg=typer.colors.BRIGHT_BLUE)
