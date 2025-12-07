import json
import typer

from cli.helpers.api_client import APIClient
from cli.config import get_deployment_base_url
from cli.helpers.errors import handle_env_error

applications_app = typer.Typer(help="List applications on your account.")


def _format_nullable(value):
    return value if value not in (None, "") else "-"


def _colorize_status(status: str) -> str:
    """Return a colorized status label based on known values."""
    if not status or status == "-":
        return "-"
    raw = str(status)
    s = raw.strip().lower()
    if s in {"validation in progress", "deployment in progress"}:
        return typer.style(raw, fg=typer.colors.CYAN)
    if s in {"deployed"}:
        return typer.style(raw, fg=typer.colors.GREEN)
    if s in {"deployment failed"}:
        return typer.style(raw, fg=typer.colors.RED)
    if s in {"partially successful"}:
        return typer.style(raw, fg=typer.colors.YELLOW)
    if s in {"deployment canceled"}:
        return typer.style(raw, fg=typer.colors.MAGENTA)

    return raw


def _pad_styled(raw_text: str, width: int, styled_text: str) -> str:
    """Pad using raw text length, append spaces after the styled text to align columns."""
    raw_len = len(str(raw_text))
    pad = max(0, width - raw_len)
    return f"{styled_text}{' ' * pad}"


def _print_applications_table(items: list[dict]) -> None:
    rows = []
    for app in items:
        name = (
            app.get("name") or app.get("displayName") or app.get("display_name") or "-"
        )
        app_id = (
            app.get("id")
            or app.get("application_uid")
            or app.get("applicationId")
            or "-"
        )
        status = app.get("activeStatus") or app.get("status")
        version = app.get("activeVersion") or app.get("version")
        lead = app.get("leadDeveloper") or app.get("leadDeveloperEmail")
        last_time = app.get("lastDeploymentTime") or app.get("lastDeploymentTime")
        rows.append(
            [
                str(name),
                str(app_id),
                _format_nullable(status),
                _format_nullable(version),
                _format_nullable(lead),
                _format_nullable(last_time),
            ]
        )

    headers = [
        "Name",
        "ID",
        "Status",
        "Version",
        "Lead Developer",
        "Last Deployment",
    ]

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    typer.echo("")
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "  ".join("-" * col_widths[i] for i in range(len(headers)))
    typer.secho(header_line, fg=typer.colors.BRIGHT_BLUE)
    typer.secho(separator, fg=typer.colors.BLUE)

    for row in rows:
        name_cell = str(row[0]).ljust(col_widths[0])
        id_cell = str(row[1]).ljust(col_widths[1])
        raw_status = str(row[2])
        colored_status = _colorize_status(raw_status)
        status_cell = _pad_styled(raw_status, col_widths[2], colored_status)
        version_cell = str(row[3]).ljust(col_widths[3])
        lead_cell = str(row[4]).ljust(col_widths[4])
        last_cell = str(row[5]).ljust(col_widths[5])

        line = "  ".join(
            [name_cell, id_cell, status_cell, version_cell, lead_cell, last_cell]
        )
        typer.echo(line)

    typer.echo("")


@applications_app.command("list")
def list_applications(
    env: str = typer.Argument("dev"),
    creds_path: str = typer.Option(
        None,
        help="Path to credentials file. If not provided, the default path will be used.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON only"),
):
    """List all applications registered in your account."""
    handle_env_error(env)
    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )

    resp = api.get("/cli/applications")
    if resp.status_code != 200:
        typer.secho(
            f"Failed to fetch applications: {resp.status_code} {resp.text}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    data = resp.json()

    items = data.get("items", [])
    total = data.get("total", len(items))
    typer.secho(f"Applications (total {total}):", fg=typer.colors.BRIGHT_BLUE)

    if json_output:
        typer.echo(json.dumps(data, indent=2))
        return

    _print_applications_table(items)
