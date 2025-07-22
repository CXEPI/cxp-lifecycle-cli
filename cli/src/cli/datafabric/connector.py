import os

import typer
import yaml

from cli.config import CONFIG_FILE
from cli.helpers.custom_typer import CustomTyper

connectors_commands = CustomTyper(
    name="connectors", help="Manage Data Fabric connectors"
)


@connectors_commands.command("add")
def add_connector(
    connector_name: str = typer.Option(
        ..., prompt=True, help="Connector name (e.g., cx_cvi_snowflake_connector)"
    ),
    route: str = typer.Option(
        ...,
        prompt=True,
        help="Route path to connector YAML (e.g., core-services/datafabric/connectors/cx_cvi_snowflake_connector.yaml)",
    ),
):
    """Add a connector to metadata.yaml under datafabric.connectors"""

    # Load or create metadata.yaml
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            metadata = yaml.safe_load(f) or {}
    else:
        metadata = {}

    # Update or insert the connector
    metadata.setdefault("datafabric", {}).setdefault("connectors", {})[
        connector_name
    ] = route

    # Save back to file
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(metadata, f, sort_keys=False)

    typer.echo(
        f"✅ Added connector '{connector_name}' with route '{route}' to {CONFIG_FILE}"
    )


@connectors_commands.command("destroy")
def destroy_connector(connector_name):
    """Delete a connector from the YAML file if the name matches."""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f)

        connectors = data.get("datafabric", {}).get("connectors", {})

        if connector_name in connectors:
            del data["datafabric"]["connectors"][connector_name]
            print(f"Deleted connector: {connector_name}")
        else:
            print(f"Connector '{connector_name}' not found.")

        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    except FileNotFoundError:
        print(f"File not found: {CONFIG_FILE}")
    except yaml.YAMLError as e:
        print(f"YAML error: {e}")


@connectors_commands.command("list")
def list_connectors():
    """List all connectors defined in the metadata.yaml file."""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f)

        connectors = data.get("datafabric", {}).get("connectors", {})
        if not connectors:
            print("No connectors found.")
            return

        print("Connectors:")
        for name, route in connectors.items():
            print(f"- {name}: {route}")

    except FileNotFoundError:
        print(f"File not found: {CONFIG_FILE}")
    except yaml.YAMLError as e:
        print(f"YAML error: {e}")
