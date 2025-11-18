"""
Integration tests for Windows compatibility.

These tests verify that the actual CLI modules work correctly with
the path utilities, especially focusing on cross-platform compatibility.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSettingsWindowsCompatibility:
    """Test settings.py Windows compatibility."""

    def test_general_cli_settings_creds_filename_no_mixed_separators(self):
        """Verify GeneralCliSettings.creds_filename has no mixed separators."""
        from cli.settings import GeneralCliSettings

        settings = GeneralCliSettings()
        creds_filename = settings.creds_filename

        # Should not have mixed separators
        path_str = str(creds_filename)
        if os.name == "nt":
            # On Windows, count both types of separators
            forward_count = path_str.count("/")
            # Exclude drive letter colon from backslash count
            backward_count = path_str[2:].count("\\") if len(path_str) > 2 else 0

            # Should not have mixed separators (except drive letter)
            assert not (
                forward_count > 0 and backward_count > 0
            ), f"Mixed separators in creds_filename: {path_str}"

    def test_general_cli_settings_creds_filename_is_valid_path(self):
        """Verify creds_filename can be used to create files."""
        from cli.settings import GeneralCliSettings

        settings = GeneralCliSettings()
        creds_filename = settings.creds_filename

        # Should be able to use this path
        creds_path = Path(creds_filename)
        assert isinstance(creds_path, Path)
        # Parent should be .cx-cli
        assert creds_path.parent.name == ".cx-cli"

    def test_version_check_settings_config_file_no_mixed_separators(self):
        """Verify VersionCheckSettings.config_file has no mixed separators."""
        from cli.settings import VersionCheckSettings

        settings = VersionCheckSettings()
        config_file = settings.config_file

        # Should be a Path object
        assert isinstance(config_file, Path)

        # Check string representation
        path_str = str(config_file)
        if os.name == "nt":
            forward_count = path_str.count("/")
            backward_count = path_str[2:].count("\\") if len(path_str) > 2 else 0
            assert not (
                forward_count > 0 and backward_count > 0
            ), f"Mixed separators in config_file: {path_str}"


class TestValidatorsWindowsCompatibility:
    """Test validators.py Windows compatibility."""

    def test_validate_creds_with_directory_path(self):
        """Verify validate_creds properly handles directory paths on all platforms."""
        from cli.validators import validate_creds
        from cli.settings import general_config
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create credentials file
            creds_file = Path(tmpdir) / "credentials.json"
            creds_data = {
                "serviceAccounts": {
                    "dev": {"clientId": "test-id", "secret": "test-secret"}
                }
            }
            with open(creds_file, "w") as f:
                json.dump(creds_data, f)

            # Pass directory path (should append credentials.json)
            try:
                validate_creds(tmpdir)
                # Should succeed
                assert True
            except SystemExit:
                pytest.fail("validate_creds failed with directory path")

    def test_validate_creds_constructs_path_correctly(self):
        """Verify validate_creds constructs file paths correctly."""
        from cli.validators import validate_creds
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            creds_dir = Path(tmpdir) / "test_cx_cli"
            creds_dir.mkdir()
            creds_file = creds_dir / "credentials.json"

            creds_data = {
                "serviceAccounts": {
                    "dev": {"clientId": "test-id", "secret": "test-secret"}
                }
            }
            with open(creds_file, "w") as f:
                json.dump(creds_data, f)

            # Should work with both string and Path
            try:
                validate_creds(str(creds_dir))
                assert True
            except SystemExit:
                pytest.fail("validate_creds failed with string directory path")


class TestDeployWindowsCompatibility:
    """Test deploy.py Windows compatibility."""

    def test_s3_keys_use_forward_slashes(self):
        """Verify S3 keys always use forward slashes, even on Windows."""
        from cli.helpers.path_utils import join_s3_path
        import uuid

        # Simulate deploy.py S3 key construction
        app_id = "test-app-id"
        deployment_id = uuid.uuid4()
        service = "data_fabric"

        key_prefix = join_s3_path("lifecycle", app_id, str(deployment_id), service)

        # Should use forward slashes only
        assert "\\" not in key_prefix
        assert key_prefix == f"lifecycle/{app_id}/{deployment_id}/{service}"

    def test_s3_keys_with_relative_paths(self):
        """Verify S3 keys work correctly with relative paths from os.walk."""
        from cli.helpers.path_utils import join_s3_path

        # Simulate Windows-style relative path
        if os.name == "nt":
            relative_path = "subfolder\\file.json"
        else:
            relative_path = "subfolder/file.json"

        key_prefix = "lifecycle/app/deploy/service"
        s3_key = join_s3_path(key_prefix, relative_path)

        # Should always use forward slashes
        assert "\\" not in s3_key
        assert s3_key == "lifecycle/app/deploy/service/subfolder/file.json"

    def test_lifecycle_env_path_construction(self):
        """Verify lifecycle environment paths are constructed correctly."""
        from cli.helpers.path_utils import get_lifecycle_env_path

        env = "dev"
        env_path = get_lifecycle_env_path(env)

        # Should be a Path object
        assert isinstance(env_path, Path)

        # Should have correct structure
        assert env_path.name == "dev.env"
        assert "lifecycle_envs" in str(env_path)

        # String representation should use OS-specific separators
        path_str = str(env_path)
        if os.name == "nt":
            # On Windows, should use backslashes or be a simple path
            assert "\\" in path_str or "/" not in path_str
        else:
            # On POSIX, should use forward slashes
            assert "/" in path_str


class TestFileHelpersWindowsCompatibility:
    """Test file.py helpers Windows compatibility."""

    def test_config_path_is_path_object(self):
        """Verify config_path is a Path object."""
        from cli.helpers.file import config_path

        assert isinstance(config_path, Path)

    def test_config_path_construction(self):
        """Verify config_path is constructed correctly."""
        from cli.helpers.file import config_path

        # Should contain lifecycle and config file
        path_str = str(config_path)
        assert "lifecycle" in path_str

        # Should not have mixed separators
        if os.name == "nt":
            # Allow either all forward or all backward (minus drive letter)
            has_forward = "/" in path_str
            has_backward = path_str.count("\\") > 1  # More than just drive letter

            # Don't fail on simple paths
            if has_forward and has_backward:
                pytest.fail(f"Mixed separators in config_path: {path_str}")


class TestInitWindowsCompatibility:
    """Test init.py Windows compatibility."""

    def test_create_lifecycle_folder_uses_path_utils(self):
        """Verify create_lifecycle_folder uses path utilities."""
        from cli.init.init import create_lifecycle_folder

        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                lifecycle_path = create_lifecycle_folder()

                # Should return a Path object
                assert isinstance(lifecycle_path, Path)

                # Directory should exist
                assert lifecycle_path.exists()
                assert lifecycle_path.is_dir()

                # Should be named "lifecycle"
                assert lifecycle_path.name == "lifecycle"
            finally:
                os.chdir(original_cwd)


class TestEndToEndScenarios:
    """End-to-end tests for complete workflows."""

    def test_init_and_deploy_path_consistency(self):
        """Verify paths are consistent between init and deploy."""
        from cli.helpers.path_utils import (
            get_lifecycle_path,
            get_lifecycle_env_path,
            get_lifecycle_config_path,
        )

        lifecycle_path = get_lifecycle_path()
        env_path = get_lifecycle_env_path("dev")
        config_path = get_lifecycle_config_path()

        # All should be Path objects
        assert all(isinstance(p, Path) for p in [lifecycle_path, env_path, config_path])

        # env_path and config_path should be under lifecycle_path
        env_path_str = str(env_path)
        config_path_str = str(config_path)
        lifecycle_str = str(lifecycle_path)

        assert lifecycle_str in env_path_str
        assert lifecycle_str in config_path_str

    def test_credentials_file_creation_and_reading(self):
        """Verify credentials file can be created and read using path utils."""
        from cli.helpers.path_utils import ensure_cx_cli_directory, get_credentials_path
        import json

        # Ensure directory exists
        cx_cli_dir = ensure_cx_cli_directory()
        assert cx_cli_dir.exists()

        # Get credentials path
        creds_path = get_credentials_path()

        # Create test credentials file
        test_data = {
            "serviceAccounts": {"dev": {"clientId": "test", "secret": "secret"}}
        }

        try:
            # Write
            with open(str(creds_path), "w") as f:
                json.dump(test_data, f)

            # Read
            with open(str(creds_path), "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == test_data
        finally:
            # Cleanup
            if creds_path.exists():
                creds_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
