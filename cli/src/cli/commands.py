import typer
from cli.helpers.custom_typer import find_and_add_typer_apps
from cli.init.init import init
from cli.register.register import register
from cli.helpers.cache_manager import (
    VersionManager,
)
from cli.validators import validate_creds

app = typer.Typer()


def version_check_callback():
    version_manager = VersionManager()
    if version_manager.is_up_to_date():
        typer.echo("✅ You are using the latest version.")
    else:
        typer.echo(
            f"⬆️  A new version is available: {version_manager.latest_version}, and you are using {version_manager.installed_version}."
        )
        typer.echo(
            "please update to the latest version: pip install git+https://github.com/CXEPI/cxp-lifecycle.git#subdirectory=cli"
        )
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    validate_creds()
    # version_check_callback()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


app.command()(init)
app.command()(register)

find_and_add_typer_apps(app)
