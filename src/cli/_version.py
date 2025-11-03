"""Version management utilities."""

import subprocess
from importlib import metadata
from packaging import version
from pathlib import Path


def get_version():
    """Get version from various sources in order of preference."""
    try:
        # Try to get version from installed package metadata first
        return metadata.version("lifecycle-cli")
    except metadata.PackageNotFoundError:
        pass

    try:
        # Try to get version from git tags
        return get_git_version()
    except Exception:
        pass

    # Fallback: read from pyproject.toml
    try:
        return get_fallback_version()
    except Exception:
        return "unknown"


def get_git_version():
    """Get version from git tags."""
    try:
        # Get the latest git tag
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        tag = result.stdout.strip()

        # Remove 'v' prefix if present
        if tag.startswith("v"):
            tag = tag[1:]

        # Validate it's a proper version
        version.parse(tag)
        return tag
    except (subprocess.CalledProcessError, version.InvalidVersion):
        raise ValueError("No valid git tag found")


def get_fallback_version():
    """Get version from pyproject.toml as fallback."""
    try:
        import tomllib
    except ImportError:
        # Python < 3.11, use tomli
        try:
            import tomli as tomllib
        except ImportError:
            return "unknown"

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("version", "unknown")
    return "unknown"


def is_development_version():
    """Check if this is a development version."""
    try:
        git_version = get_git_version()
        current_version = get_version()
        return git_version != current_version
    except Exception:
        return False


if __name__ == "__main__":
    print(get_version())
