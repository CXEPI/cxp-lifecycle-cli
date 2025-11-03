import typer
from cli.helpers.custom_typer import find_and_add_typer_apps
from cli.init.init import init
from cli.register.register import register
from cli.cancel.cancel import cancel
from cli.helpers.cache_manager import (
    VersionManager,
)

app = typer.Typer()
version_manager = VersionManager()


def version_check_callback():
    try:
        if version_manager.is_up_to_date():
            typer.echo("✅ You are using the latest version.")
        else:
            typer.echo(
                f"⬆️  A new version is available: {version_manager.latest_version}, and you are using {version_manager.installed_version}."
            )
            typer.echo("Please update to the latest version:")
            typer.echo("  uv tool upgrade lifecycle-cli")
            typer.echo(
                "  uvx --from git+https://github.com/CXEPI/cxp-lifecycle-cli cx-cli [command]"
            )
            typer.echo(
                "  pip install --upgrade git+https://github.com/CXEPI/cxp-lifecycle-cli"
            )
            raise typer.Exit()
    except Exception:
        pass


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    version_check_callback()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


@app.command()
def version():
    """Show the CLI version."""
    typer.echo(f"cx-cli version {version_manager.get_cache_version()}")


app.command()(init)
app.command()(register)
app.command()(cancel)

find_and_add_typer_apps(app)
