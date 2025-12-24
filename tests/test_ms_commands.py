"""Tests for Message Service CLI commands."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli.ms.ms import (
    GrantRole,
    get_messaging_api_url,
    grants_create,
    grants_delete,
    grants_list,
)
import typer


class TestGrantRole:
    """Tests for GrantRole enum."""

    def test_grant_role_values(self):
        """Test GrantRole enum values."""
        assert GrantRole.PRODUCER.value == "producer"
        assert GrantRole.CONSUMER.value == "consumer"

    def test_grant_role_is_string_enum(self):
        """Test GrantRole inherits from str."""
        assert isinstance(GrantRole.PRODUCER, str)
        assert isinstance(GrantRole.CONSUMER, str)


class TestGetMessagingApiUrl:
    """Tests for get_messaging_api_url function."""

    def test_get_messaging_api_url_sbx(self):
        """Test URL generation for sandbox."""
        with patch("cli.ms.ms.BASE_URL_BY_ENV", {"sbx": "https://sbx.example.com"}):
            url = get_messaging_api_url("sbx")
            assert url == "https://sbx.example.com/messaging/api/v1"

    def test_get_messaging_api_url_dev(self):
        """Test URL generation for dev."""
        with patch("cli.ms.ms.BASE_URL_BY_ENV", {"dev": "https://dev.example.com"}):
            url = get_messaging_api_url("dev")
            assert url == "https://dev.example.com/messaging/api/v1"

    def test_get_messaging_api_url_unknown_env(self):
        """Test unknown environment raises Exit."""
        with patch("cli.ms.ms.BASE_URL_BY_ENV", {}):
            with pytest.raises(typer.Exit) as exc_info:
                get_messaging_api_url("unknown")
            assert exc_info.value.exit_code == 1


class TestGrantsCreate:
    """Tests for grants_create command."""

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_create_producer_grant_success(self, mock_get_url, mock_api_client):
        """Test successful producer grant creation."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_api.post.return_value = mock_response
        mock_api_client.return_value = mock_api

        # Should not raise
        grants_create(
            topic="cx.test.events.v1",
            app_id="test-app",
            role=GrantRole.PRODUCER,
            group=None,
            env="sbx",
            creds_path=None,
        )

        mock_api.post.assert_called_once_with(
            "/topics/cx.test.events.v1/grants",
            json={"app_id": "test-app", "role": "producer"},
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_create_consumer_grant_with_group_success(self, mock_get_url, mock_api_client):
        """Test successful consumer grant creation with group."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_api.post.return_value = mock_response
        mock_api_client.return_value = mock_api

        grants_create(
            topic="cx.test.events.v1",
            app_id="test-app",
            role=GrantRole.CONSUMER,
            group="my-group",
            env="sbx",
            creds_path=None,
        )

        mock_api.post.assert_called_once_with(
            "/topics/cx.test.events.v1/grants",
            json={"app_id": "test-app", "role": "consumer", "consumer_group": "my-group"},
        )

    def test_create_consumer_grant_without_group_fails(self):
        """Test consumer grant without group raises Exit."""
        with pytest.raises(typer.Exit) as exc_info:
            grants_create(
                topic="cx.test.events.v1",
                app_id="test-app",
                role=GrantRole.CONSUMER,
                group=None,
                env="sbx",
                creds_path=None,
            )
        assert exc_info.value.exit_code == 1

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_create_grant_conflict(self, mock_get_url, mock_api_client):
        """Test grant already exists (409)."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_api.post.return_value = mock_response
        mock_api_client.return_value = mock_api

        # Should not raise, just print warning
        grants_create(
            topic="cx.test.events.v1",
            app_id="test-app",
            role=GrantRole.PRODUCER,
            group=None,
            env="sbx",
            creds_path=None,
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_create_grant_failure(self, mock_get_url, mock_api_client):
        """Test grant creation failure raises Exit."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_api.post.return_value = mock_response
        mock_api_client.return_value = mock_api

        with pytest.raises(typer.Exit) as exc_info:
            grants_create(
                topic="cx.test.events.v1",
                app_id="test-app",
                role=GrantRole.PRODUCER,
                group=None,
                env="sbx",
                creds_path=None,
            )
        assert exc_info.value.exit_code == 1


class TestGrantsDelete:
    """Tests for grants_delete command."""

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_delete_grant_success(self, mock_get_url, mock_api_client):
        """Test successful grant deletion."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_api.delete.return_value = mock_response
        mock_api_client.return_value = mock_api

        grants_delete(
            topic="cx.test.events.v1",
            app_id="test-app",
            role=GrantRole.PRODUCER,
            env="sbx",
            creds_path=None,
        )

        mock_api.delete.assert_called_once_with(
            "/topics/cx.test.events.v1/grants/test-app?role=producer"
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_delete_grant_not_found(self, mock_get_url, mock_api_client):
        """Test grant not found (404)."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_api.delete.return_value = mock_response
        mock_api_client.return_value = mock_api

        # Should not raise, just print warning
        grants_delete(
            topic="cx.test.events.v1",
            app_id="test-app",
            role=GrantRole.PRODUCER,
            env="sbx",
            creds_path=None,
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_delete_grant_failure(self, mock_get_url, mock_api_client):
        """Test grant deletion failure raises Exit."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_api.delete.return_value = mock_response
        mock_api_client.return_value = mock_api

        with pytest.raises(typer.Exit) as exc_info:
            grants_delete(
                topic="cx.test.events.v1",
                app_id="test-app",
                role=GrantRole.PRODUCER,
                env="sbx",
                creds_path=None,
            )
        assert exc_info.value.exit_code == 1


class TestGrantsList:
    """Tests for grants_list command."""

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_list_grants_success(self, mock_get_url, mock_api_client):
        """Test successful grants listing."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grants": [
                {"app_id": "app1", "role": "producer"},
                {"app_id": "app2", "role": "consumer", "consumer_group": "group1"},
            ]
        }
        mock_api.get.return_value = mock_response
        mock_api_client.return_value = mock_api

        grants_list(
            topic="cx.test.events.v1",
            env="sbx",
            creds_path=None,
        )

        mock_api.get.assert_called_once_with("/topics/cx.test.events.v1/grants")

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_list_grants_empty(self, mock_get_url, mock_api_client):
        """Test empty grants list."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"grants": []}
        mock_api.get.return_value = mock_response
        mock_api_client.return_value = mock_api

        # Should not raise
        grants_list(
            topic="cx.test.events.v1",
            env="sbx",
            creds_path=None,
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_list_grants_topic_not_found(self, mock_get_url, mock_api_client):
        """Test topic not found (404)."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_api.get.return_value = mock_response
        mock_api_client.return_value = mock_api

        # Should not raise, just print warning
        grants_list(
            topic="cx.test.events.v1",
            env="sbx",
            creds_path=None,
        )

    @patch("cli.ms.ms.APIClient")
    @patch("cli.ms.ms.get_messaging_api_url")
    def test_list_grants_failure(self, mock_get_url, mock_api_client):
        """Test grants listing failure raises Exit."""
        mock_get_url.return_value = "https://example.com/messaging/api/v1"
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_api.get.return_value = mock_response
        mock_api_client.return_value = mock_api

        with pytest.raises(typer.Exit) as exc_info:
            grants_list(
                topic="cx.test.events.v1",
                env="sbx",
                creds_path=None,
            )
        assert exc_info.value.exit_code == 1
