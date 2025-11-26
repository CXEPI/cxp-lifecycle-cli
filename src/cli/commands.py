import typer
from cli.helpers.custom_typer import find_and_add_typer_apps
from cli.init.init import init
from cli.register.register import register
from cli.cancel.cancel import cancel
from cli.validate.validate import validate
from cli.helpers.cache_manager import (
    VersionManager,
)
from cli.settings import version_check_config

app = typer.Typer()
version_manager = VersionManager()


def version_check_callback():
    try:
        # Skip version check if disabled in config
        if not version_check_config.check_enabled:
            return

        if version_manager.is_up_to_date():
            typer.echo("✅ You are using the latest CLI version.")
        else:
            typer.echo(
                f"⬆️  A new CLI version is available: {version_manager.latest_version}, and you are using {version_manager.installed_version}."
            )
            typer.echo("\nPlease update to the latest CLI version:")
            typer.echo("  cx-cli upgrade")
            typer.echo("\nOr manually:")
            typer.echo(
                "  uv tool install --force --no-cache git+https://github.com/CXEPI/cxp-lifecycle-cli"
            )
            typer.echo(
                "  pip install --upgrade git+https://github.com/CXEPI/cxp-lifecycle-cli"
            )
            typer.echo("\nTo disable this check, run:")
            typer.echo("  cx-cli config set version-check-enabled false")
            raise typer.Exit()
    except Exception:
        pass


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    # Skip version check for version management commands
    skip_commands = ["upgrade", "version", "config"]
    if ctx.invoked_subcommand not in skip_commands:
        version_check_callback()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


@app.command()
def version():
    """Show the CLI version."""
    typer.echo(f"cx-cli version {version_manager.installed_version}")


@app.command()
def upgrade(
    method: str = typer.Option(
        None,
        "--method",
        "-m",
        help="Installation method to use: 'uv' or 'pip'. Auto-detects if not specified.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force upgrade even if already up-to-date")
):
    """Upgrade cx-cli to the latest version."""
    if not version_manager.is_up_to_date():
        typer.echo(
            f"Current version: {version_manager.installed_version}\n"
            f"Latest version: {version_manager.latest_version}"
        )
    elif not force:
        typer.echo(
            f"✅ Already running the latest version: {version_manager.installed_version}"
        )
        return

    if not yes:
        confirm = typer.confirm("Do you want to upgrade?")
        if not confirm:
            typer.echo("Upgrade cancelled.")
            raise typer.Exit()

    typer.echo("Upgrading cx-cli...")
    success, message = version_manager.upgrade_cli(method)

    if success:
        typer.echo(f"✅ {message}")
        typer.echo(
            "Please restart your terminal or run the command again to use the new version."
        )
    else:
        typer.echo(f"❌ {message}", err=True)
        raise typer.Exit(1)


config_app = typer.Typer(help="Manage CLI configuration")
app.add_typer(config_app, name="config")


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="Configuration key to retrieve")):
    """Get a configuration value."""
    value = version_check_config.get(key)
    if value is None:
        typer.echo(f"Configuration key '{key}' not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"{key}: {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a configuration value."""
    # Handle boolean values
    if value.lower() in ["true", "false"]:
        bool_value = value.lower() == "true"
        if key == "version-check-enabled":
            version_check_config.check_enabled = bool_value
            typer.echo(f"✅ Set {key} to {bool_value}")
            return

    # Handle other values
    version_check_config.set(key, value)
    typer.echo(f"✅ Set {key} to {value}")


@config_app.command("list")
def config_list():
    """List all configuration settings."""
    config_file = version_check_config.config_file
    if not config_file.exists():
        typer.echo("No configuration file found. Using defaults.")
        typer.echo("  version-check-enabled: true")
        return

    typer.echo(f"Configuration file: {config_file}")
    typer.echo("\nSettings:")
    for key, value in version_check_config._config.items():
        typer.echo(f"  {key}: {value}")


app.command()(init)
app.command()(register)
app.command()(cancel)
app.command()(validate)

find_and_add_typer_apps(app)
