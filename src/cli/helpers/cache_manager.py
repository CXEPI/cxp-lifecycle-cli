import json
import logging
import re
from datetime import datetime, timedelta
from importlib.metadata import version as dist_version
from pathlib import Path
from typing import Optional

import requests
from packaging.version import Version

CACHE_FILE = Path("lifecycle", ".version_cache.json")
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
        self.installed_version = self.get_project_version()

    def get_latest_version(self) -> str:
        cached_version = self.get_cache_version()
        if cached_version:
            logging.info(f"Using cached version: {cached_version}")
            return cached_version

        self.latest_version = self.get_latest_github_tag()
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

    def get_latest_github_tag(self) -> str:
        url = "https://api.github.com/repos/CXEPI/cxp-lifecycle-cli/tags"
        headers = {}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"GitHub API request failed: status {resp.status_code}")
        tags = resp.json()
        if not tags:
            raise RuntimeError("No tags found")
        latest = tags[0]["name"]
        return latest

    def get_cache_version(self) -> Optional[str]:
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time < self.cache_ttl:
                return data["version"]
        except Exception as e:
            logging.error(f"Error reading cache file {self.cache_file}: {e}")
        return None

    def get_project_version(self) -> str:
        return dist_version(self.package_name)

    def is_up_to_date(self) -> bool:
        latest = re.sub(r"^[vV]", "", self.latest_version)
        installed = re.sub(r"^[vV]", "", self.installed_version)

        return Version(installed) >= Version(latest)
