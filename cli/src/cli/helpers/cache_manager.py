import json
import logging
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError
from datetime import timedelta
from pathlib import Path
from typing import Optional

from cli.helpers.api_client import APIClient
from packaging import version as pkg_version

CACHE_FILE = Path("lifecycle", "version_cache.json")
CACHE_TTL = timedelta(hours=8)


class VersionManager:
    def __init__(
        self,
        cache_file: Path = CACHE_FILE,
        cache_ttl: timedelta = CACHE_TTL,
        package_name: str = "lifecycle-cli",
    ):
        self.cache_file = cache_file
        self.cache_ttl = cache_ttl
        self.package_name = package_name
        self.latest_version = self.get_latest_version()
        self.installed_version = self.get_installed_version()

    def get_latest_version(self) -> str:
        cached_version = self.get_cache_version()
        if cached_version:
            logging.info(f"Using cached version: {cached_version}")
            return cached_version
        api = APIClient()
        response = api.get(f"/version/get_latest_version")
        if response.status_code != 200:
            raise Exception(
                f"Failed to fetch latest version from backend: {response.status_code}"
            )
        self.latest_version = response.json().get("latest_version")
        self.save_cache_version()
        return self.latest_version

    def save_cache_version(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(
                {
                    "version": self.latest_version,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
            )

    def get_cache_version(self) -> Optional[str]:
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time < CACHE_TTL:
                return data["version"]
        except Exception as e:
            logging.error(f"Error reading cache file {self.cache_file}: {e}")
        return None

    def get_installed_version(self) -> str:
        try:
            return version(self.package_name)
        except PackageNotFoundError:
            return "0.0.0"

    def is_up_to_date(self) -> bool:
        return pkg_version.parse(self.installed_version) >= pkg_version.parse(
            self.latest_version
        )
