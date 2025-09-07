import requests
from cli.settings import general_config
from cli.config import BACKEND_BASE_URL, ENV
from cli.validators import validate_creds
import typer


class APIClient:
    def __init__(self, base_url: str = None, env: str = None, creds_path: str = None):
        self.base_url = base_url if base_url else BACKEND_BASE_URL
        self.env = env if env else ENV

        validate_creds(creds_path)

        self.service_credentials = (
            general_config.cx_cli_service_accounts_credentials.get(self.env, "")
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-ServiceCredentials": self.service_credentials,
                "Content-Type": "application/json",
            }
        )

    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get(self, endpoint: str, **kwargs):
        return self.session.get(
            self._build_url(endpoint), **kwargs, allow_redirects=False
        )

    def post(self, endpoint: str, json=None, **kwargs):
        return self.session.post(self._build_url(endpoint), json=json, **kwargs)

    def put(self, endpoint: str, json=None, **kwargs):
        return self.session.put(self._build_url(endpoint), json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs):
        return self.session.delete(self._build_url(endpoint), **kwargs)

    def get_headers(self):
        return dict(self.session.headers)
