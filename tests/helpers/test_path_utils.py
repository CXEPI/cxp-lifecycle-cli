"""
Tests for cross-platform path handling utilities.

These tests verify that path utilities work correctly across different operating systems,
with special attention to Windows path handling issues.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cli.helpers.path_utils import (
    get_cx_cli_home,
    get_credentials_path,
    get_config_path,
    get_lifecycle_path,
    get_lifecycle_env_path,
    get_lifecycle_config_path,
    to_posix_path,
    to_platform_path,
    ensure_cx_cli_directory,
    join_s3_path,
    normalize_path_for_comparison,
)


class TestCxCliPaths:
    """Test cx-cli home directory and config path utilities."""

    def test_get_cx_cli_home_returns_path_object(self):
        """Verify get_cx_cli_home returns a Path object."""
        result = get_cx_cli_home()
        assert isinstance(result, Path)
        assert result.name == ".cx-cli"

    def test_get_cx_cli_home_is_in_user_home(self):
        """Verify cx-cli home is in user's home directory."""
        result = get_cx_cli_home()
        assert result.parent == Path.home()

    def test_get_credentials_path_has_correct_filename(self):
        """Verify credentials path has correct filename."""
        result = get_credentials_path()
        assert result.name == "credentials.json"
        assert result.parent.name == ".cx-cli"

    def test_get_config_path_has_correct_filename(self):
        """Verify config path has correct filename."""
        result = get_config_path()
        assert result.name == "config.json"
        assert result.parent.name == ".cx-cli"

    def test_paths_use_correct_separators_on_windows(self):
        """Verify paths use backslashes on Windows."""
        if os.name == "nt":
            result = str(get_credentials_path())
            # On Windows, paths should contain backslashes
            assert "\\" in result or result.count("/") == 0

    def test_paths_use_correct_separators_on_posix(self):
        """Verify paths use forward slashes on POSIX systems."""
        if os.name != "nt":
            result = str(get_credentials_path())
            # On POSIX, paths should contain forward slashes
            assert "/" in result


class TestLifecyclePaths:
    """Test lifecycle directory path utilities."""

    def test_get_lifecycle_path_returns_path_object(self):
        """Verify get_lifecycle_path returns a Path object."""
        result = get_lifecycle_path()
        assert isinstance(result, Path)
        assert result.name == "lifecycle" or str(result) == "lifecycle"

    def test_get_lifecycle_env_path_constructs_correctly(self):
        """Verify environment path is constructed correctly."""
        result = get_lifecycle_env_path("dev")
        assert isinstance(result, Path)
        assert result.name == "dev.env"
        # Check parent structure
        assert "lifecycle_envs" in str(result)
        assert "lifecycle" in str(result)

    def test_get_lifecycle_env_path_different_environments(self):
        """Verify environment paths work for different environments."""
        envs = ["dev", "prod", "sandbox", "nprd"]
        for env in envs:
            result = get_lifecycle_env_path(env)
            assert result.name == f"{env}.env"

    def test_get_lifecycle_config_path_uses_correct_config_file(self):
        """Verify lifecycle config path uses correct filename."""
        result = get_lifecycle_config_path()
        assert isinstance(result, Path)
        assert "lifecycle" in str(result)


class TestPathConversion:
    """Test path format conversion utilities."""

    def test_to_posix_path_with_path_object(self):
        """Verify to_posix_path converts Path object to POSIX format."""
        path = Path("folder") / "subfolder" / "file.txt"
        result = to_posix_path(path)
        assert isinstance(result, str)
        assert result == "folder/subfolder/file.txt"
        # Must use forward slashes regardless of OS
        assert "\\" not in result

    def test_to_posix_path_with_string(self):
        """Verify to_posix_path converts string to POSIX format."""
        # Note: On POSIX systems, backslashes in strings are literal characters,
        # not path separators. To test Windows behavior, use PureWindowsPath.
        from pathlib import PureWindowsPath

        # Test with Windows path object
        windows_path = PureWindowsPath("folder\\subfolder\\file.txt")
        result = to_posix_path(windows_path)
        assert result == "folder/subfolder/file.txt"
        assert "\\" not in result

    def test_to_posix_path_already_posix(self):
        """Verify to_posix_path handles already-POSIX paths."""
        path = "folder/subfolder/file.txt"
        result = to_posix_path(path)
        assert result == "folder/subfolder/file.txt"

    def test_to_platform_path_returns_string(self):
        """Verify to_platform_path returns a string."""
        path = Path("folder") / "subfolder" / "file.txt"
        result = to_platform_path(path)
        assert isinstance(result, str)

    def test_to_platform_path_uses_os_separator(self):
        """Verify to_platform_path uses OS-specific separator."""
        path = Path("folder") / "subfolder" / "file.txt"
        result = to_platform_path(path)
        # Result should contain the OS-specific separator
        if os.name == "nt":
            # On Windows, should have backslashes or no forward slashes in single-part paths
            assert "\\" in result or "/" not in result
        else:
            # On POSIX, should have forward slashes
            assert "/" in result


class TestS3PathHandling:
    """Test S3 path construction utilities."""

    def test_join_s3_path_with_strings(self):
        """Verify S3 path joining works with string arguments."""
        result = join_s3_path("lifecycle", "app-id", "deploy-id", "service")
        assert result == "lifecycle/app-id/deploy-id/service"
        # Must always use forward slashes
        assert "\\" not in result

    def test_join_s3_path_with_uuid(self):
        """Verify S3 path joining works with UUID objects."""
        import uuid

        deployment_id = uuid.uuid4()
        result = join_s3_path("lifecycle", "app-id", str(deployment_id), "service")
        assert result.startswith("lifecycle/app-id/")
        assert result.endswith("/service")
        assert "\\" not in result

    def test_join_s3_path_removes_leading_trailing_slashes(self):
        """Verify S3 path joining strips leading/trailing slashes."""
        result = join_s3_path("/lifecycle/", "/app-id/", "/deploy-id/")
        assert result == "lifecycle/app-id/deploy-id"
        # Should not have leading or trailing slashes
        assert not result.startswith("/")
        assert not result.endswith("/")

    def test_join_s3_path_with_path_objects(self):
        """Verify S3 path joining works with Path objects."""
        path = Path("folder") / "subfolder"
        result = join_s3_path("lifecycle", path, "file.txt")
        assert result == "lifecycle/folder/subfolder/file.txt"
        assert "\\" not in result

    def test_join_s3_path_with_backslashes(self):
        """Verify S3 path joining converts backslashes to forward slashes."""
        # Test with string containing backslashes (common on Windows)
        # join_s3_path should convert these to forward slashes
        result = join_s3_path("lifecycle", "folder\\subfolder", "file.txt")
        assert result == "lifecycle/folder/subfolder/file.txt"
        assert "\\" not in result

        # Also test with PureWindowsPath
        from pathlib import PureWindowsPath

        windows_path = PureWindowsPath("folder\\subfolder")
        result2 = join_s3_path("lifecycle", windows_path, "file.txt")
        assert result2 == "lifecycle/folder/subfolder/file.txt"
        assert "\\" not in result2

    def test_join_s3_path_preserves_nested_structure(self):
        """Verify S3 path joining preserves nested directory structure."""
        result = join_s3_path("lifecycle", "app", "deploy", "service/subdir/file.json")
        assert result == "lifecycle/app/deploy/service/subdir/file.json"


class TestPathNormalization:
    """Test path normalization for comparison."""

    def test_normalize_path_with_string(self):
        """Verify normalize_path_for_comparison works with strings."""
        result = normalize_path_for_comparison("~/.cx-cli/credentials.json")
        assert isinstance(result, Path)

    def test_normalize_path_with_path_object(self):
        """Verify normalize_path_for_comparison works with Path objects."""
        path = Path.home() / ".cx-cli" / "credentials.json"
        result = normalize_path_for_comparison(path)
        assert isinstance(result, Path)

    def test_normalize_path_handles_mixed_separators(self):
        """Verify normalize_path_for_comparison handles mixed separators."""
        # This simulates the Windows issue: C:\Users\name/.cx-cli/credentials.json
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.touch()

            # Create two representations of the same path
            path1 = normalize_path_for_comparison(test_file)
            path2 = normalize_path_for_comparison(str(test_file))

            # They should be equal after normalization
            assert path1 == path2


class TestDirectoryCreation:
    """Test directory creation utilities."""

    def test_ensure_cx_cli_directory_creates_directory(self):
        """Verify ensure_cx_cli_directory creates the directory."""
        with patch("cli.helpers.path_utils.get_cx_cli_home") as mock_home:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_dir = Path(tmpdir) / "test_cx_cli"
                mock_home.return_value = test_dir

                result = ensure_cx_cli_directory()

                assert result.exists()
                assert result.is_dir()

    def test_ensure_cx_cli_directory_idempotent(self):
        """Verify ensure_cx_cli_directory is idempotent."""
        with patch("cli.helpers.path_utils.get_cx_cli_home") as mock_home:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_dir = Path(tmpdir) / "test_cx_cli"
                mock_home.return_value = test_dir

                # Call twice
                result1 = ensure_cx_cli_directory()
                result2 = ensure_cx_cli_directory()

                # Should succeed both times
                assert result1.exists()
                assert result2.exists()
                assert result1 == result2


class TestWindowsSpecificIssues:
    """Test cases specifically for Windows path handling issues."""

    def test_no_mixed_separators_in_cx_cli_paths(self):
        """Verify cx-cli paths don't have mixed separators."""
        paths = [
            get_cx_cli_home(),
            get_credentials_path(),
            get_config_path(),
        ]

        for path in paths:
            path_str = str(path)
            # Check for mixed separators (both / and \ in same path)
            has_forward = "/" in path_str
            has_backward = "\\" in path_str

            # Should not have both types of separators
            # (Unless it's a Windows absolute path like C:/ which is acceptable)
            if os.name == "nt":
                # On Windows, if there are forward slashes, there should be no backslashes
                # except possibly the drive letter separator
                if has_forward and has_backward:
                    # Allow C:\ at the start, but nothing else
                    remaining = path_str[3:] if path_str[1:3] == ":\\" else path_str
                    assert (
                        "/" not in remaining or "\\" not in remaining
                    ), f"Mixed separators in path: {path_str}"

    def test_s3_paths_never_have_backslashes(self):
        """Verify S3 paths never contain backslashes, even on Windows."""
        from pathlib import PureWindowsPath

        test_cases = [
            (("lifecycle", "app", "deploy", "service"), "lifecycle/app/deploy/service"),
            (
                ("lifecycle", "folder\\subfolder", "file.txt"),
                "lifecycle/folder/subfolder/file.txt",
            ),
            (
                ("lifecycle", Path("folder") / "subfolder", "file.txt"),
                "lifecycle/folder/subfolder/file.txt",
            ),
            (
                ("lifecycle", PureWindowsPath("folder\\subfolder"), "file.txt"),
                "lifecycle/folder/subfolder/file.txt",
            ),
        ]

        for parts, expected in test_cases:
            result = join_s3_path(*parts)
            assert result == expected, f"Expected {expected}, got {result}"
            assert "\\" not in result, f"S3 path contains backslash: {result}"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific test")
    def test_windows_home_directory_format(self):
        """Verify home directory is properly formatted on Windows."""
        cx_cli_home = get_cx_cli_home()
        home_str = str(cx_cli_home)

        # On Windows, should look like: C:\Users\username\.cx-cli
        # Should have drive letter
        assert (
            home_str[1:3] == ":\\" or home_str[1:3] == ":/"
        ), f"Windows path missing drive letter: {home_str}"

    @pytest.mark.skipif(os.name == "nt", reason="POSIX-specific test")
    def test_posix_home_directory_format(self):
        """Verify home directory is properly formatted on POSIX systems."""
        cx_cli_home = get_cx_cli_home()
        home_str = str(cx_cli_home)

        # On POSIX, should look like: /home/username/.cx-cli or /Users/username/.cx-cli
        assert home_str.startswith("/"), f"POSIX path should start with /: {home_str}"
        assert "\\" not in home_str, f"POSIX path contains backslash: {home_str}"


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_credentials_path_can_be_opened(self):
        """Verify credentials path string can be used to open files."""
        creds_path = str(get_credentials_path())

        # Ensure parent directory exists
        ensure_cx_cli_directory()

        # Should be able to create and open the file
        try:
            with open(creds_path, "w") as f:
                f.write('{"test": "data"}')

            with open(creds_path, "r") as f:
                content = f.read()
                assert "test" in content
        finally:
            # Cleanup
            if os.path.exists(creds_path):
                os.remove(creds_path)

    def test_s3_key_with_relative_path_from_walk(self):
        """Verify S3 key construction works with os.walk relative paths."""
        # Simulate what happens in deploy.py
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            service_dir = Path(tmpdir) / "service"
            sub_dir = service_dir / "subfolder"
            sub_dir.mkdir(parents=True)
            test_file = sub_dir / "test.json"
            test_file.touch()

            # Simulate os.walk behavior
            for root, _, files in os.walk(service_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, service_dir)

                    # Construct S3 key
                    s3_key = join_s3_path(
                        "lifecycle", "app-id", "deploy-id", relative_path
                    )

                    # Verify it's a valid S3 key
                    assert "\\" not in s3_key
                    assert s3_key.startswith("lifecycle/app-id/deploy-id/")
                    assert s3_key.endswith("test.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
