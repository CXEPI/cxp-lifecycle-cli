from typing import Callable
import questionary
import typer
import re
from urllib.parse import urlparse
import semver


def prompt_email(prompt_text: str = "Enter lead developer email") -> str:
    email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
    while True:
        email = typer.prompt(prompt_text)
        if email_pattern.match(email):
            return email
        else:
            typer.secho(
                "✘ Invalid email format, please try again.",
                fg=typer.colors.RED,
                bold=True,
            )


def prompt_url(prompt_text: str = "Enter GitHub URL") -> str:
    allowed_hosts = {"github.com", "wwwin-github.cisco.com"}
    while True:
        url = typer.prompt(prompt_text)
        parsed = urlparse(url)
        if (
            parsed.scheme == "https"
            and parsed.netloc in allowed_hosts
            and parsed.path != ""
        ):
            return url
        else:
            typer.secho(
                "✘ Invalid GitHub URL. Must start with https://github.com/ or https://wwwin-github.cisco.com/. Please try again.",
                fg=typer.colors.RED,
                bold=True,
            )


def prompt_semver_version(prompt_text: str = "Enter version (semver)") -> str:
    while True:
        version = typer.prompt(prompt_text)
        try:
            semver.VersionInfo.parse(version)
            return version
        except ValueError:
            typer.secho(
                "✘ Invalid semantic version. Please try again (e.g., 1.2.3).",
                fg=typer.colors.RED,
                bold=True,
            )


FORMAT_PROMPT_MAP: dict[str, Callable[[str], str]] = {
    "email": prompt_email,
    "semver": prompt_semver_version,
    "uri": prompt_url,
}


def prompt_string(key: str, description: str = "", format: str = None) -> str:
    prompt_func = FORMAT_PROMPT_MAP.get(format)
    if prompt_func:
        return prompt_func(description or f"Enter {key}")
    return typer.prompt(description or f"Enter {key}")


def prompt_core_services(schema: dict) -> list[str]:
    core_services_schema = schema["properties"]["core_services"]
    pattern_properties = core_services_schema.get("patternProperties", {})
    services_raw = list(pattern_properties.keys())

    if services_raw and services_raw[0].startswith("^("):
        match = re.match(r"\^\((.*?)\)\$", services_raw[0])
        services_clean = match.group(1).split("|") if match else []
    else:
        services_clean = [s.strip("^$") for s in services_raw]

    selected_services = questionary.checkbox(
        "Select core services:", choices=services_clean
    ).ask()

    if not selected_services:
        selected_services = []

    return selected_services


def prompt_application(schema: dict) -> dict:
    application_schema = schema["properties"]["application"]
    result = {}
    props = application_schema.get("properties", {})
    for key, value in props.items():
        description = value.get("description", "")
        field_format = value.get("format", None)
        result[key] = prompt_string(key, description, field_format)
    return result
