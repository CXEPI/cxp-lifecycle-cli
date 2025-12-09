import json
from typing import Optional

import typer

from cli.helpers.api_client import APIClient
from cli.config import get_deployment_base_url, ENVIRONMENTS
from cli.helpers.file import load_config
from cli.helpers.errors import handle_env_error


deployments_app = typer.Typer(help="View deployment details and history.")


def _colorize_status(status: Optional[str]) -> str:
    if not status:
        return "-"
    raw = str(status)
    s = raw.strip().lower()
    if s in {"validation in progress", "deployment in progress"}:
        return typer.style(raw, fg=typer.colors.CYAN)
    if s == "deployed":
        return typer.style(raw, fg=typer.colors.GREEN)
    if s == "deployment failed":
        return typer.style(raw, fg=typer.colors.RED)
    if s == "partially successful":
        return typer.style(raw, fg=typer.colors.YELLOW)
    if s == "deployment canceled":
        return typer.style(raw, fg=typer.colors.MAGENTA)
    return raw


def _format_nullable(value):
    return value if value not in (None, "") else "-"


def _pad_styled(raw_text: str, width: int, styled_text: str) -> str:
    raw_len = len(str(raw_text))
    pad = max(0, width - raw_len)
    return f"{styled_text}{' ' * pad}"


def _print_deployment_details(data: dict) -> None:
    """Pretty print a single deployment object with colorized status and nested details."""
    typer.echo("")
    typer.secho("Deployment Details:", fg=typer.colors.BRIGHT_BLUE)

    dep_id = data.get("deploymentId") or data.get("id") or "-"
    app_id = data.get("applicationId") or data.get("application_id") or "-"
    status_raw = data.get("status", "-")
    status_colored = _colorize_status(status_raw)
    version = data.get("version", "-")
    deployed_by = data.get("deployedBy", "-")
    dep_time = data.get("deploymentTime") or data.get("createdAt") or "-"
    dep_complete_time = (
        data.get("deploymentCompleteTime") or data.get("updatedAt") or "-"
    )

    typer.echo(f"Deployment ID: {dep_id}")
    typer.echo(f"Application ID: {app_id}")
    typer.echo(f"Status: {status_colored}")
    typer.echo(f"Version: {version}")
    typer.echo(f"Deployed By: {deployed_by}")
    typer.echo(f"Deployment Time: {dep_time}")
    typer.echo(f"Deployment Complete Time: {dep_complete_time}")

    rcs = data.get("requestedCoreServices") or {}
    if isinstance(rcs, dict) and rcs:
        typer.echo("")
        typer.secho("Requested Core Services:", fg=typer.colors.BRIGHT_BLUE)
        for service_name, svc in rcs.items():
            typer.secho(f"- {service_name}", fg=typer.colors.BRIGHT_WHITE)
            if isinstance(svc, dict):
                ds = svc.get("deployment_status")
                cfp = svc.get("configuration_file_path")
                fr = svc.get("failure_reason")
                topics = svc.get("num_of_topics")
                topic_statuses = svc.get("topic_statuses")

                if ds is not None:
                    typer.echo(f"    Status: {ds}")
                if cfp is not None:
                    typer.echo(f"    Config Path: {cfp}")
                if fr is not None:
                    typer.echo(f"    Failure Reason: {fr}")
                if topics is not None:
                    typer.echo(f"    Num of Topics: {topics}")
                if topic_statuses is not None:
                    if isinstance(topic_statuses, dict) and topic_statuses:
                        typer.echo("    Topic Statuses:")
                        for tname, tstat in topic_statuses.items():
                            typer.echo(f"      - {tname}: {tstat}")
                    else:
                        typer.echo("    Topic Statuses: {}")
            else:
                typer.echo(f"    Details: {svc}")

    typer.echo("")


@deployments_app.command("get")
def get_deployment(
    deployment_id: Optional[str] = typer.Argument(None, help="The deployment ID to retrieve."),
    env: str = typer.Argument("dev"),
    creds_path: str = typer.Option(
        None,
        help="Custom path to credentials file. Uses default location if not specified.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Display output in raw JSON format."),
):
    """
    Retrieve details for a specific deployment.
    With an ID: returns that deployment's full details.
    Without an ID: returns the current (last successful) deployment for the local application.
    """

    if deployment_id in ENVIRONMENTS and (env == "dev" or not env):
        env = deployment_id
        deployment_id = None

    handle_env_error(env)
    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )

    if deployment_id:
        resp = api.get(f"/cli/deployments/{deployment_id}")
        if resp.status_code != 200:
            typer.secho(
                f"Failed to fetch deployment: {resp.status_code} {resp.text}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        data = resp.json()
        if json_output:
            typer.secho("Deployment Details:", fg=typer.colors.BRIGHT_BLUE)
            typer.echo(json.dumps(data, indent=2))
        else:
            _print_deployment_details(data)
        return

    cfg = load_config()
    app_id = cfg.get("application", {}).get("application_uid") or cfg.get(
        "application", {}
    ).get("id")
    if not app_id:
        typer.secho(
            "Application ID not found in lifecycle_config.yaml", fg=typer.colors.RED
        )
        raise typer.Exit(1)

    current_resp = api.get(f"/cli/deployments/current/{app_id}")
    if current_resp.status_code == 404:
        typer.secho(
            "No successful deployments found for this application.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(0)
    if current_resp.status_code != 200:
        typer.secho(
            f"Failed to fetch current deployment: {current_resp.status_code} {current_resp.text}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    data = current_resp.json()
    if json_output:
        typer.secho("Current Deployment:", fg=typer.colors.BRIGHT_BLUE)
        typer.echo(json.dumps(data, indent=2))
    else:
        _print_deployment_details(data)


@deployments_app.command("history")
def list_deployments_history(
    app_id: Optional[str] = typer.Argument(None, help="The application ID to view history for."),
    env: str = typer.Argument("dev"),
    creds_path: str = typer.Option(
        None,
        help="Custom path to credentials file. Uses default location if not specified.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Display output in raw JSON format."),
):
    """
    View the deployment history for an application.
    Defaults to the local application's ID from lifecycle_config.yaml if <app-id> not provided.
    """
    if app_id in ENVIRONMENTS and (not env or env == "dev"):
        env = app_id
        app_id = None

    handle_env_error(env)
    app_id = (
        app_id
        or load_config().get("application", {}).get("application_uid")
        or load_config().get("application", {}).get("id")
    )
    if not app_id:
        typer.secho(
            "Application ID not provided and not found in local lifecycle_config.yaml",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    api = APIClient(
        base_url=get_deployment_base_url(env), env=env, creds_path=creds_path
    )
    resp = api.get(f"/cli/deployments/history/{app_id}")
    if resp.status_code != 200:
        typer.secho(
            f"Failed to fetch deployments: {resp.status_code} {resp.text}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    data = resp.json()

    items = data.get("items", [])
    total = data.get("total", len(items))
    typer.secho(f"Deployment history for application {app_id} (total {total}):", fg=typer.colors.BRIGHT_BLUE)

    if json_output:
        typer.echo(json.dumps(data, indent=2))
        return

    rows = []
    for d in items:
        dep_id = d.get("deploymentId") or d.get("deployment_id") or d.get("id") or "-"
        status = d.get("status") or d.get("state")
        version = d.get("version") or d.get("appVersion") or d.get("applicationVersion")
        deployed_by = d.get("deployedBy") or d.get("deployed_by") or d.get("actor")
        deployed_time = (
            d.get("deploymentTime")
            or d.get("deployment_time")
            or d.get("createdAt")
            or d.get("created_at")
        )
        rows.append(
            [
                str(dep_id),
                _format_nullable(status),
                _format_nullable(version),
                _format_nullable(deployed_by),
                _format_nullable(deployed_time),
            ]
        )

    headers = [
        "Deployment ID",
        "Status",
        "Version",
        "Deployed By",
        "Deployment Time",
    ]

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    typer.echo("")

    header_line = "   ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "   ".join("-" * col_widths[i] for i in range(len(headers)))
    typer.secho(header_line, fg=typer.colors.BRIGHT_BLUE)
    typer.secho(separator, fg=typer.colors.BLUE)

    for row in rows:
        dep_cell = str(row[0]).ljust(col_widths[0])
        raw_status = str(row[1])
        colored_status = _colorize_status(raw_status)
        status_cell = _pad_styled(raw_status, col_widths[1], colored_status)
        version_cell = str(row[2]).ljust(col_widths[2])
        by_cell = str(row[3]).ljust(col_widths[3])
        time_cell = str(row[4]).ljust(col_widths[4])
        typer.echo(
            "   ".join([dep_cell, status_cell, version_cell, by_cell, time_cell])
        )

    typer.echo("")
