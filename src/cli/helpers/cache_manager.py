import json
import os
import re
from datetime import datetime, timedelta
from importlib.metadata import version as dist_version
from pathlib import Path
from typing import Optional

import requests
from packaging.version import Version

CACHE_FILE = Path("lifecycle", ".version_cache.json")
CACHE_TTL = timedelta(hours=24)


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
        cached = self.get_cache_version()
        if cached:
            return cached

        tag = self.get_latest_github_tag()
        latest = tag if tag else self.get_project_version()

        self.save_cache_version(latest)
        return latest

    def save_cache_version(self, version: str) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(
                    {"version": version, "timestamp": datetime.now().isoformat()},
                    f,
                )
        except Exception:
            pass

    def get_latest_github_tag(self) -> Optional[str]:
            try:
                url = "https://api.github.com/repos/CXEPI/cxp-lifecycle-cli/tags"
                headers = {
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "cxp-lifecycle-cli/version-check",
                }
                token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
                if token:
                    headers["Authorization"] = f"Bearer {token}"

                resp = requests.get(url, headers=headers, timeout=3)
                if resp.status_code != 200:
                    return None

                tags = resp.json()
                if not isinstance(tags, list) or not tags:
                    return None

                candidates = []
                for t in tags:
                    name = t.get("name")
                    if not name:
                        continue
                    candidates.append(self._strip_v(name))

                if not candidates:
                    return None

                best = max(candidates, key=lambda s: Version(self._safe_version(s)))
                return best
            except Exception:
                return None

    def get_cache_version(self) -> Optional[str]:
        try:
            if not self.cache_file.exists():
                return None
            with open(self.cache_file, "r") as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data.get("timestamp", "1970-01-01T00:00:00"))
            if datetime.now() - ts < self.cache_ttl:
                ver = data.get("version")
                return ver if ver else None
        except Exception:
            # ignore cache issues silently
            return None
        return None

    def get_project_version(self) -> str:
        return dist_version(self.package_name)

    def is_up_to_date(self) -> bool:
        latest = re.sub(r"^[vV]", "", self.latest_version)
        installed = re.sub(r"^[vV]", "", self.installed_version)

        return Version(installed) >= Version(latest)
