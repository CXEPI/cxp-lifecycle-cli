import importlib
from pathlib import Path

import typer


class CustomTyper(typer.Typer):
    """
    A Typer subclass that automatically shows help when no subcommand is provided
    """

    def __init__(self, help_text: str = "CLI commands", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_auto_help(help_text)

    def _setup_auto_help(self, help_text: str):
        @self.callback(invoke_without_command=True)
        def auto_help_callback(ctx: typer.Context):
            if ctx.invoked_subcommand is None:
                print(ctx.get_help())
                raise typer.Exit()

        auto_help_callback.__doc__ = help_text


def find_and_add_typer_apps(app: typer.Typer):
    """Find and add all Typer apps from the cli package"""
    # Get the directory where this commands.py file is located (the cli package)
    cli_package_dir = Path(__file__).parent.parent

    # Look for all Python files in subdirectories
    for py_file in cli_package_dir.rglob("*.py"):
        # Skip files we don't want to process
        if py_file.name in {"__init__.py", "commands.py", "config.py"}:
            continue

        # Skip if it's in the current directory (not a subdirectory)
        if py_file.parent == cli_package_dir:
            continue

        try:
            # Calculate the module path relative to the cli package
            rel_path = py_file.relative_to(cli_package_dir)
            module_parts = list(rel_path.with_suffix("").parts)
            module_name = f"cli.{'.'.join(module_parts)}"

            # Import the module
            module = importlib.import_module(module_name)

            # Look for Typer apps
            for attr_name in dir(module):
                if attr_name.endswith("_app"):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, typer.Typer):
                        command_name = py_file.stem
                        app.add_typer(attr, name=command_name)
                        break  # Only add one app per module

        except ImportError as e:
            print(f"Could not import module for {py_file}: {e}")
        except Exception as e:
            print(f"Error processing {py_file}: {e}")
