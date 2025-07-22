import typer
import os
import yaml
from cli.config import CONFIG_FILE
from cli.helpers.custom_typer import CustomTyper

function_commands = CustomTyper(name="functions", help="Manage api functions")


@function_commands.command("add")
def add_function(
    name: str = typer.Option(..., prompt=True, help="Function name (e.g., helloWorld)"),
    language: str = typer.Option(
        "Python", prompt=True, help="Programming language: One of Python, Go, NodeJS"
    ),
    method: str = typer.Option("GET", prompt=True, help="HTTP method"),
    route: str = typer.Option(
        ...,
        prompt=True,
        help="Function route (e.g., /core-services/api/functions/helloworld)",
    ),
    entry_point: str = typer.Option(
        ..., prompt=True, help="Entry point (e.g., func.main)"
    ),
    roles: str = typer.Option(
        "viewer,editor,admin",
        prompt="Roles (comma-separated)",
        help="Comma-separated list of roles",
    ),
):
    """Add a function definition to metadata.yaml"""
    roles_list = [r.strip() for r in roles.split(",")]

    new_function = {
        name: {
            "language": language,
            "method": method.upper(),
            "route": route.strip("/"),
            "entryPoint": entry_point,
            "roles": roles_list,
        }
    }

    # Load or initialize metadata
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            metadata = yaml.safe_load(f) or {}
    else:
        metadata = {}

    # Merge new data
    metadata.setdefault("api", {}).setdefault("functions", {}).update(new_function)

    # Save back to file
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(metadata, f, sort_keys=False)

    typer.echo(f"✅ Added function '{name}' to {CONFIG_FILE}")


@function_commands.command("destroy")
def destroy_function(name):
    """Delete a function definition from metadata.yaml"""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f) or {}

        functions = data.get("api", {}).get("functions", {})

        if name in functions:
            del functions[name]
            typer.echo(f"✅ Deleted function '{name}'")
        else:
            typer.echo(f"Function '{name}' not found.")

        # Save back to file
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(data, f, sort_keys=False)

    except FileNotFoundError:
        typer.echo(f"File not found: {CONFIG_FILE}")
    except yaml.YAMLError as e:
        typer.echo(f"YAML error: {e}")


@function_commands.command("list")
def list_functions():
    """List all function definitions in metadata.yaml"""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f) or {}

        functions = data.get("api", {}).get("functions", {})

        if not functions:
            typer.echo("No functions defined.")
            return

        typer.echo("Defined Functions:")
        for name, details in functions.items():
            typer.echo(f"  - {name}")

    except FileNotFoundError:
        typer.echo(f"File not found: {CONFIG_FILE}")
    except yaml.YAMLError as e:
        typer.echo(f"YAML error: {e}")
