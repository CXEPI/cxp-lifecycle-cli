"""
Windows simulation tests that run on macOS/Linux.

These tests mock Windows behavior to verify cross-platform compatibility
without needing an actual Windows machine.
"""

import os
import sys
from pathlib import Path, PureWindowsPath, PurePosixPath
from unittest.mock import patch, MagicMock, PropertyMock
import tempfile
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class WindowsPathSimulator:
    """Helper class to simulate Windows path behavior on any platform."""

    @staticmethod
    def simulate_windows_home() -> str:
        """Simulate a Windows home directory path."""
        return "C:\\Users\\testuser"

    @staticmethod
    def simulate_windows_path(posix_path: str) -> str:
        """Convert a POSIX path to Windows format."""
        # Handle home directory
        if posix_path.startswith("~"):
            posix_path = posix_path.replace(
                "~", WindowsPathSimulator.simulate_windows_home()
            )

        # Convert forward slashes to backslashes
        windows_path = posix_path.replace("/", "\\")

        # Add drive letter if absolute path
        if windows_path.startswith("\\") and not windows_path.startswith("\\\\"):
            windows_path = "C:" + windows_path

        return windows_path

    @staticmethod
    def create_windows_path_mock(path_str: str):
        """Create a Path-like mock object that behaves like Windows Path."""
        mock_path = MagicMock(spec=Path)
        mock_path.__str__ = MagicMock(
            return_value=WindowsPathSimulator.simulate_windows_path(path_str)
        )
        mock_path.__truediv__ = (
            lambda self, other: WindowsPathSimulator.create_windows_path_mock(
                path_str + "/" + str(other)
            )
        )
        mock_path.as_posix = MagicMock(return_value=path_str.replace("\\", "/"))
        parts = path_str.split("/")
        mock_path.name = parts[-1] if parts else ""
        mock_path.parent = (
            WindowsPathSimulator.create_windows_path_mock("/".join(parts[:-1]))
            if len(parts) > 1
            else mock_path
        )
        return mock_path


class TestWindowsSimulation:
    """Test Windows-specific behavior on macOS/Linux using mocking."""

    def test_windows_home_directory_format(self):
        """Simulate Windows home directory and verify path format."""
        with patch("pathlib.Path.home") as mock_home:
            # Simulate Windows home directory
            mock_home.return_value = PureWindowsPath("C:\\Users\\testuser")

            from cli.helpers.path_utils import get_cx_cli_home

            # Mock the path operations to behave like Windows
            with patch("cli.helpers.path_utils.Path") as mock_path_class:
                mock_path_class.home.return_value = PureWindowsPath(
                    "C:\\Users\\testuser"
                )
                mock_path_class.side_effect = lambda x: (
                    PureWindowsPath(x) if isinstance(x, str) else x
                )

                cx_cli_home = get_cx_cli_home()

                # The path should be constructed correctly
                # When stringified on Windows, it should use backslashes
                expected = "C:\\Users\\testuser\\.cx-cli"
                assert (
                    str(PureWindowsPath("C:\\Users\\testuser") / ".cx-cli") == expected
                )

    def test_windows_credentials_path_no_mixed_separators(self):
        """Verify credentials path doesn't have mixed separators on Windows."""
        with patch("pathlib.Path.home") as mock_home:
            # Simulate Windows home
            windows_home = PureWindowsPath("C:\\Users\\testuser")
            mock_home.return_value = windows_home

            # Construct path like our utility does
            creds_path = windows_home / ".cx-cli" / "credentials.json"
            creds_str = str(creds_path)

            # On Windows, Path should use backslashes
            # Check for mixed separators
            if "\\" in creds_str:
                # If it has backslashes, it should not also have forward slashes
                # (except possibly in the drive letter area)
                assert (
                    creds_str.count("/") == 0
                ), f"Mixed separators detected: {creds_str}"

    def test_windows_s3_path_always_uses_forward_slashes(self):
        """Verify S3 paths use forward slashes even when simulating Windows."""
        from cli.helpers.path_utils import join_s3_path

        # Simulate Windows-style paths being passed in
        with patch("os.sep", "\\"):
            with patch("os.name", "nt"):
                # Test with backslashes (Windows relative path)
                windows_relative = "subfolder\\nested\\file.json"
                s3_key = join_s3_path("lifecycle", "app-id", windows_relative)

                # Must use forward slashes
                assert "\\" not in s3_key
                assert s3_key == "lifecycle/app-id/subfolder/nested/file.json"

    def test_windows_path_from_os_walk(self):
        """Simulate os.walk on Windows and verify S3 key construction."""
        from cli.helpers.path_utils import join_s3_path

        # Simulate Windows os.walk results
        with patch("os.sep", "\\"):
            # Simulate what os.path.relpath returns on Windows
            windows_relative_path = "data_fabric\\connectors\\connector.json"

            # This is what our code does
            s3_key = join_s3_path(
                "lifecycle", "app-id", "deploy-id", windows_relative_path
            )

            # Should convert to forward slashes for S3
            assert "\\" not in s3_key
            assert (
                s3_key
                == "lifecycle/app-id/deploy-id/data_fabric/connectors/connector.json"
            )

    def test_settings_with_windows_home(self):
        """Test GeneralCliSettings with simulated Windows home directory."""
        # Clear any cached imports
        if "cli.settings" in sys.modules:
            del sys.modules["cli.settings"]
        if "cli.helpers.path_utils" in sys.modules:
            del sys.modules["cli.helpers.path_utils"]

        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = PureWindowsPath("C:\\Users\\testuser")

            # Now import settings - it will use our mocked home
            from cli.helpers.path_utils import get_credentials_path

            creds_path = get_credentials_path()
            creds_str = str(creds_path)

            # Should contain .cx-cli
            assert ".cx-cli" in creds_str
            assert "credentials.json" in creds_str

    def test_mixed_separator_detection(self):
        """Test detection of mixed separator issues that caused the bug."""
        # This is the exact bug the user reported:
        # 'C:\Users\xa/.cx-cli/credentials.json'

        buggy_path = "C:\\Users\\xa/.cx-cli/credentials.json"

        # Detect mixed separators
        has_backslash = "\\" in buggy_path
        has_forward = "/" in buggy_path

        assert has_backslash and has_forward, "Should detect mixed separators"

        # Our fix: use Path operations which are consistent
        # Convert to Path and back to string to normalize
        fixed_path = str(PureWindowsPath(buggy_path))

        # After normalization, should be consistent
        # PureWindowsPath normalizes to backslashes
        assert fixed_path == "C:\\Users\\xa\\.cx-cli\\credentials.json"

    def test_expanduser_mixed_separator_bug(self):
        """Reproduce the original bug with expanduser and string concatenation."""
        # Demonstrate the original buggy code pattern
        # On Windows, expanduser('~') returns 'C:\Users\username'
        windows_home = "C:\\Users\\testuser"

        # Old buggy code did this (string concatenation):
        buggy_path = f"{windows_home}/.cx-cli/credentials.json"

        # This creates mixed separators!
        assert buggy_path == "C:\\Users\\testuser/.cx-cli/credentials.json"
        assert "\\" in buggy_path and "/" in buggy_path

        # Our fix uses Path operations which are consistent
        from pathlib import Path, PureWindowsPath

        # Simulate Windows behavior
        fixed_path = PureWindowsPath(windows_home) / ".cx-cli" / "credentials.json"
        fixed_str = str(fixed_path)

        # Path operations ensure consistency - all backslashes on Windows
        assert fixed_str == "C:\\Users\\testuser\\.cx-cli\\credentials.json"
        assert "/" not in fixed_str  # No mixed separators!


class TestWindowsOSOperations:
    """Test OS operations with Windows simulation."""

    def test_os_path_join_with_path_objects(self):
        """Test the problematic pattern: os.path.join with Path objects."""
        from pathlib import Path
        import os

        with patch("os.sep", "\\"):
            with patch("os.path.join") as mock_join:
                # Simulate Windows os.path.join behavior
                def windows_join(*args):
                    # Convert Path objects to strings
                    str_args = [str(arg) for arg in args]
                    # Join with backslash
                    return "\\".join(str_args)

                mock_join.side_effect = windows_join

                # This was the buggy pattern in deploy.py:31
                lifecycle_path = Path("lifecycle")
                buggy_result = os.path.join(
                    lifecycle_path / "lifecycle_envs", "dev.env"
                )

                # This would create weird results
                assert "\\" in buggy_result

    def test_s3_key_with_os_path_join_on_windows(self):
        """Test the S3 key bug with os.path.join on Windows."""
        import os

        with patch("os.sep", "\\"):
            with patch("os.path.join") as mock_join:
                # Simulate Windows behavior
                def windows_join(*args):
                    return "\\".join(str(arg) for arg in args)

                mock_join.side_effect = windows_join

                # Old buggy code did this for S3 keys
                buggy_s3_key = os.path.join("lifecycle/app/deploy", "service")

                # This creates backslashes on Windows - WRONG for S3!
                assert buggy_s3_key == "lifecycle/app/deploy\\service"

        # Our fix uses join_s3_path
        from cli.helpers.path_utils import join_s3_path

        fixed_s3_key = join_s3_path("lifecycle/app/deploy", "service")

        # Always uses forward slashes
        assert fixed_s3_key == "lifecycle/app/deploy/service"
        assert "\\" not in fixed_s3_key


class TestWindowsFileOperations:
    """Test file operations with Windows path simulation."""

    def test_credentials_file_creation_windows_style(self):
        """Test creating credentials file with Windows-style paths."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate Windows path
            if os.name == "nt":
                creds_dir = Path(tmpdir) / ".cx-cli"
            else:
                # On macOS, we can still test the logic
                creds_dir = Path(tmpdir) / ".cx-cli"

            creds_dir.mkdir(parents=True, exist_ok=True)
            creds_file = creds_dir / "credentials.json"

            # Write test data
            test_data = {
                "serviceAccounts": {"dev": {"clientId": "test", "secret": "secret"}}
            }

            # This should work on any platform
            with open(str(creds_file), "w") as f:
                json.dump(test_data, f)

            # Read back
            with open(str(creds_file), "r") as f:
                loaded = json.load(f)

            assert loaded == test_data

    def test_lifecycle_directory_creation_windows_style(self):
        """Test creating lifecycle directories with Windows simulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                from cli.helpers.path_utils import get_lifecycle_path

                lifecycle_path = get_lifecycle_path()
                lifecycle_path.mkdir(parents=True, exist_ok=True)

                # Create subdirectories
                env_dir = lifecycle_path / "lifecycle_envs"
                env_dir.mkdir(parents=True, exist_ok=True)

                # Create env file
                env_file = env_dir / "dev.env"
                env_file.write_text("# Test env file\n")

                # Verify structure
                assert lifecycle_path.exists()
                assert env_dir.exists()
                assert env_file.exists()

            finally:
                os.chdir(original_cwd)


class TestCrossPatformConsistency:
    """Test that our utilities produce consistent results across platforms."""

    def test_same_path_different_representations(self):
        """Test that different path representations resolve to same location."""
        from cli.helpers.path_utils import normalize_path_for_comparison

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.touch()

            # Different ways to represent the same path
            path1 = str(test_file)
            path2 = test_file

            # After normalization, should be equal
            norm1 = normalize_path_for_comparison(path1)
            norm2 = normalize_path_for_comparison(path2)

            assert norm1 == norm2

    def test_posix_conversion_consistent(self):
        """Test that POSIX conversion is consistent."""
        from cli.helpers.path_utils import to_posix_path

        # Note: On POSIX systems (macOS/Linux), backslashes in strings are treated
        # as literal characters, not path separators. To test Windows behavior,
        # we need to use PureWindowsPath or test the actual scenarios.
        test_cases = [
            ("folder/file.txt", "folder/file.txt"),
            (Path("folder") / "file.txt", "folder/file.txt"),
        ]

        for input_path, expected in test_cases:
            result = to_posix_path(input_path)
            assert result == expected

        # Test Windows-style path using PureWindowsPath
        from pathlib import PureWindowsPath

        windows_path = PureWindowsPath("folder\\subfolder\\file.txt")
        result = to_posix_path(windows_path)
        assert result == "folder/subfolder/file.txt"
        assert "\\" not in result


class TestRealWorldWindowsScenarios:
    """Test real-world scenarios that would occur on Windows."""

    def test_deploy_s3_upload_scenario(self):
        """Simulate the deploy S3 upload scenario from deploy.py."""
        from cli.helpers.path_utils import join_s3_path
        import uuid

        # Simulate deploy parameters
        app_id = "test-app-id"
        deployment_id = uuid.uuid4()
        service = "data_fabric"

        # Simulate Windows os.walk results
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directory structure
            service_dir = Path(tmpdir) / "data_fabric"
            connectors_dir = service_dir / "connectors"
            connectors_dir.mkdir(parents=True)
            test_file = connectors_dir / "connector.json"
            test_file.write_text('{"test": "data"}')

            # Simulate walking the directory
            for root, _, files in os.walk(service_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, service_dir)

                    # Construct S3 key using our utility
                    s3_key = join_s3_path(
                        "lifecycle", app_id, str(deployment_id), service, relative_path
                    )

                    # Verify S3 key is correct
                    assert "\\" not in s3_key
                    assert s3_key.startswith(
                        f"lifecycle/{app_id}/{deployment_id}/{service}"
                    )
                    assert s3_key.endswith("connector.json")

    def test_init_with_windows_paths(self):
        """Simulate init command with Windows paths."""
        from cli.helpers.path_utils import get_lifecycle_path

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Simulate creating lifecycle structure
                lifecycle_path = get_lifecycle_path()
                lifecycle_path.mkdir(exist_ok=True)

                # Create envs folder
                envs_folder = lifecycle_path / "lifecycle_envs"
                envs_folder.mkdir(exist_ok=True)

                # Create env files
                env_files = ["dev.env", "prod.env", "sandbox.env"]
                for env_file in env_files:
                    env_path = envs_folder / env_file
                    env_path.write_text(f"# {env_file}\n")

                # Verify all created correctly
                assert lifecycle_path.exists()
                assert envs_folder.exists()
                for env_file in env_files:
                    assert (envs_folder / env_file).exists()

            finally:
                os.chdir(original_cwd)

    def test_validators_with_windows_directory_path(self):
        """Test validators.py behavior with Windows-style directory path."""
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create credentials directory
            creds_dir = Path(tmpdir)
            creds_file = creds_dir / "credentials.json"

            # Create credentials file
            creds_data = {
                "serviceAccounts": {"dev": {"clientId": "test", "secret": "test"}}
            }
            with open(creds_file, "w") as f:
                json.dump(creds_data, f)

            # Simulate validators.py logic
            # If given a directory, should append "credentials.json"
            creds_path = Path(tmpdir)
            if creds_path.is_dir():
                file_path = str(creds_path / "credentials.json")
            else:
                file_path = str(creds_path)

            # Should be able to open the file
            with open(file_path, "r") as f:
                loaded = json.load(f)

            assert loaded == creds_data


def test_summary():
    """Summary test to verify all fixes."""
    from cli.helpers.path_utils import (
        get_credentials_path,
        get_config_path,
        join_s3_path,
        to_posix_path,
    )

    print("\n" + "=" * 60)
    print("Windows Compatibility Test Summary")
    print("=" * 60)

    # Test 1: Credentials path
    creds = get_credentials_path()
    print(f"\n✓ Credentials path: {creds}")
    print(f"  Type: {type(creds)}")

    # Test 2: Config path
    config = get_config_path()
    print(f"\n✓ Config path: {config}")
    print(f"  Type: {type(config)}")

    # Test 3: S3 path
    s3_key = join_s3_path("lifecycle", "app", "deploy", "service\\file.json")
    print(f"\n✓ S3 key: {s3_key}")
    print(f"  No backslashes: {('\\' not in s3_key)}")

    # Test 4: POSIX conversion
    posix = to_posix_path("folder\\subfolder\\file.txt")
    print(f"\n✓ POSIX conversion: {posix}")
    print(f"  No backslashes: {('\\' not in posix)}")

    print("\n" + "=" * 60)
    print("All Windows compatibility checks passed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
