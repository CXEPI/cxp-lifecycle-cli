"""Version management utilities."""

from importlib import metadata


def get_version():
    """Get version from various sources in order of preference."""
    try:
        return metadata.version("lifecycle-cli")
    except metadata.PackageNotFoundError:
        return "unknown"
        pass

if __name__ == "__main__":
    print(get_version())
