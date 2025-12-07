import typer


def get_status_color(status: str) -> str:
    """Get the appropriate color for a deployment/validation status"""
    if not status:
        return typer.colors.BRIGHT_CYAN

    if "Done" in status or "Succeeded" in status or "Completed" in status:
        return typer.colors.BRIGHT_GREEN
    elif "Failed" in status or "REJECTED" in status or "ERROR" in status:
        return typer.colors.BRIGHT_RED
    elif (
        "Progress" in status
        or "Pending" in status
        or "RECEIVED" in status
        or "Validating" in status
    ):
        return typer.colors.BRIGHT_YELLOW
    elif "Cancel" in status:
        return typer.colors.BRIGHT_MAGENTA
    else:
        return typer.colors.BRIGHT_CYAN

