from typing_extensions import Annotated
import typer

# from cli.api.function import function_commands
from cli.helpers.custom_typer import CustomTyper
from cli.settings import api_validation_config
from cli.api.helpers import get_app_schemas
import questionary
import subprocess
from importlib import resources
from contextlib import contextmanager
from pathlib import Path
import shutil
import json


api_commands_app = CustomTyper(name="openapi_validator", help="Validate api commands")
# api_commands.add_typer(function_commands, name="functions", help="Manage API functions")


@contextmanager
def ruleset_path() -> Path:
    """
    Yields a real filesystem Path to the ruleset declared in
    `api_validation_config`.  Works whether the package is unpacked
    or zipped inside a .whl / PyInstaller EXE.

        with ruleset_path() as path:
            run_spectral(path)
    """
    pkg = api_validation_config.ruleset_path
    filename = api_validation_config.ruleset_filename

    try:
        traversable = resources.files(pkg).joinpath(filename)
    except Exception as e:
        print(f"Error accessing ruleset: {str(e)}")
        raise

    if not traversable.is_file():
        raise FileNotFoundError(
            f"Ruleset {filename!r} not found inside package {pkg!r}"
        )

    # `as_file` will copy to a tmp dir if `traversable` is *not* on disk
    with resources.as_file(traversable) as real_path:
        yield Path(real_path)


#
@api_commands_app.command("validate")
def lint_spec(spec: Annotated[Path, typer.Argument()] = None):
    """
    Validates spec file
    """
    if not spec:
        all_schemas = get_app_schemas()
        selected_schema = questionary.select(
            "Select OpenAPI schema to validate:", choices=all_schemas
        ).ask()
        if selected_schema is None:
            print("No OpenAPI schema selected")
            raise typer.Exit(code=1)
        spec = selected_schema
    elif not spec.is_file() or spec.suffix not in [".json", ".yml", ".yaml"]:
        print("Given schema path is invalid")
        raise typer.Exit(code=1)

    with ruleset_path() as rules_path:
        ruleset_dir = rules_path.parent
        node_modules = ruleset_dir / "node_modules"
        package_json = ruleset_dir / "package.json"

        needs_install = True
        if node_modules.exists() and package_json.exists():
            try:
                with open(package_json, "r") as f:
                    pkg_data = json.load(f)
                    required_deps = pkg_data.get("dependencies", {}).keys()

                    # Check if all required packages exist in node_modules
                    if all((node_modules / dep).exists() for dep in required_deps):
                        needs_install = False
            except (IOError, OSError, json.JSONDecodeError):
                pass  # If there's any error reading/parsing files, we'll do the install

        if needs_install:
            print("Installing node modules...")
            npm_install = subprocess.run(
                ["npm", "ci", "--omit=dev"],
                cwd=str(ruleset_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if npm_install.returncode != 0:
                print("Failed to install node modules:", npm_install.stderr.decode())
                raise typer.Exit(code=1)

        spectral = shutil.which("spectral")
        if spectral:
            cmd = [spectral, "lint", "--ruleset", str(rules_path), str(spec)]
        else:
            npx = shutil.which("npx")
            if not npx:
                typer.secho(
                    "Neither 'spectral' nor 'npx' found in PATH.\n"
                    "Install Node.js and run:\n"
                    "  npm i -g @stoplight/spectral-cli",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            cmd = [
                npx,
                "-y",  # skip “install?” prompt on older npx
                "-p",
                "@stoplight/spectral-cli",
                "spectral",
                "lint",
                "--ruleset",
                str(rules_path),
                str(spec),
            ]

        proc = subprocess.run(cmd)
        raise typer.Exit(code=proc.returncode)
