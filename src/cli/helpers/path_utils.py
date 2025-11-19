"""
Cross-platform path handling utilities for cx-cli.

This module provides utilities to ensure consistent path handling across
Windows, macOS, and Linux. Use these functions instead of direct string
concatenation or os.path operations to avoid path separator issues.
"""

from pathlib import Path
from typing import Union
import os


def get_cx_cli_home() -> Path:
    """
    Get the cx-cli configuration directory path.

    Returns:
        Path object pointing to ~/.cx-cli directory

    Examples:
        >>> path = get_cx_cli_home()
        >>> # Windows: C:\\Users\\username\\.cx-cli
        >>> # macOS/Linux: /Users/username/.cx-cli
    """
    return Path.home() / ".cx-cli"


def get_credentials_path() -> Path:
    """
    Get the default credentials file path.

    Returns:
        Path object pointing to ~/.cx-cli/credentials.json

    Examples:
        >>> path = get_credentials_path()
        >>> # Windows: C:\\Users\\username\\.cx-cli\\credentials.json
        >>> # macOS/Linux: /Users/username/.cx-cli/credentials.json
    """
    return get_cx_cli_home() / "credentials.json"


def get_config_path() -> Path:
    """
    Get the default config file path.

    Returns:
        Path object pointing to ~/.cx-cli/config.json

    Examples:
        >>> path = get_config_path()
        >>> # Windows: C:\\Users\\username\\.cx-cli\\config.json
        >>> # macOS/Linux: /Users/username/.cx-cli/config.json
    """
    return get_cx_cli_home() / "config.json"


def get_lifecycle_path() -> Path:
    """
    Get the lifecycle directory path in current working directory.

    Returns:
        Path object pointing to ./lifecycle directory

    Examples:
        >>> path = get_lifecycle_path()
        >>> # Windows: C:\\project\\lifecycle
        >>> # macOS/Linux: /project/lifecycle
    """
    return Path("lifecycle")


def get_lifecycle_env_path(env: str) -> Path:
    """
    Get the environment file path for a specific environment.

    Args:
        env: Environment name (e.g., 'dev', 'prod', 'sandbox')

    Returns:
        Path object pointing to lifecycle/lifecycle_envs/{env}.env

    Examples:
        >>> path = get_lifecycle_env_path('dev')
        >>> # Windows: lifecycle\\lifecycle_envs\\dev.env
        >>> # macOS/Linux: lifecycle/lifecycle_envs/dev.env
    """
    return get_lifecycle_path() / "lifecycle_envs" / f"{env}.env"


def get_lifecycle_config_path() -> Path:
    """
    Get the lifecycle config file path.

    Returns:
        Path object pointing to lifecycle/lifecycle_config.yaml
    """
    from cli.config import CONFIG_FILE

    return get_lifecycle_path() / CONFIG_FILE


def to_posix_path(path: Union[str, Path]) -> str:
    """
    Convert a path to POSIX format with forward slashes.

    Use this for cloud storage paths (S3, URLs) or any path that must
    use forward slashes regardless of OS.

    Args:
        path: Path as string or Path object

    Returns:
        String path with forward slashes

    Examples:
        >>> to_posix_path(Path("folder/subfolder/file.txt"))
        'folder/subfolder/file.txt'
        >>> # Even on Windows:
        >>> to_posix_path("folder\\\\subfolder\\\\file.txt")
        'folder/subfolder/file.txt'
    """
    # Handle PurePath objects (including PureWindowsPath)
    if hasattr(path, "as_posix"):
        return path.as_posix()

    # Convert string to Path
    if isinstance(path, str):
        path = Path(path)

    return path.as_posix()


def to_platform_path(path: Union[str, Path]) -> str:
    """
    Convert a path to platform-specific format.

    Use this when you need a string representation of a path for
    the current operating system.

    Args:
        path: Path as string or Path object

    Returns:
        String path with platform-specific separators

    Examples:
        >>> to_platform_path(Path("folder") / "subfolder" / "file.txt")
        >>> # Windows: 'folder\\\\subfolder\\\\file.txt'
        >>> # macOS/Linux: 'folder/subfolder/file.txt'
    """
    if isinstance(path, str):
        path = Path(path)
    return str(path)


def ensure_cx_cli_directory() -> Path:
    """
    Ensure the ~/.cx-cli directory exists.

    Creates the directory if it doesn't exist.

    Returns:
        Path object pointing to the created/existing directory

    Examples:
        >>> path = ensure_cx_cli_directory()
        >>> assert path.exists()
    """
    cx_cli_home = get_cx_cli_home()
    cx_cli_home.mkdir(parents=True, exist_ok=True)
    return cx_cli_home


def join_s3_path(*parts: str) -> str:
    """
    Join path components for S3 keys.

    S3 keys must always use forward slashes, regardless of OS.
    This function ensures proper S3 key construction.

    Args:
        *parts: Path components to join

    Returns:
        S3 key with forward slashes

    Examples:
        >>> join_s3_path("lifecycle", "app-id", "deploy-id", "service")
        'lifecycle/app-id/deploy-id/service'
        >>> # Works correctly even on Windows
    """
    # Convert any Path objects or backslash paths to forward slashes
    normalized_parts = []
    for part in parts:
        if isinstance(part, Path) or hasattr(part, "as_posix"):
            # Handle Path objects (including PureWindowsPath)
            part = part.as_posix()
        else:
            # Convert to string and replace both types of separators
            part = str(part).replace("\\", "/").replace(os.sep, "/")
        normalized_parts.append(part.strip("/"))

    return "/".join(normalized_parts)


def normalize_path_for_comparison(path: Union[str, Path]) -> Path:
    """
    Normalize a path for comparison across different representations.

    Use this when comparing paths that might be represented differently
    (e.g., with different separators or relative vs absolute).

    Args:
        path: Path as string or Path object

    Returns:
        Normalized Path object

    Examples:
        >>> p1 = normalize_path_for_comparison("C:\\\\Users\\\\name/.cx-cli/creds.json")
        >>> p2 = normalize_path_for_comparison(Path.home() / ".cx-cli" / "creds.json")
        >>> p1 == p2  # True on Windows
    """
    if isinstance(path, str):
        path = Path(path)
    # Resolve to absolute path and normalize
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        # If path doesn't exist or can't be resolved, normalize as-is
        return path
