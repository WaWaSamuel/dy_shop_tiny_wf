"""Configuration for the local host-side session bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeSettings:
    host: str = "127.0.0.1"
    port: int = 8765
    backend_api_base_url: str = "http://127.0.0.1:8000/api/v1"
    chrome_profile_name: str = "Default"
    chrome_cookies_path: str = ""
    chrome_safe_storage_name: str = "Chrome Safe Storage"
    request_timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> "BridgeSettings":
        return cls(
            host=os.getenv("BRIDGE_HOST", "127.0.0.1"),
            port=int(os.getenv("BRIDGE_PORT", "8765")),
            backend_api_base_url=os.getenv("BRIDGE_BACKEND_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
            chrome_profile_name=os.getenv("BRIDGE_CHROME_PROFILE_NAME", "Default"),
            chrome_cookies_path=os.getenv("BRIDGE_CHROME_COOKIES_PATH", ""),
            chrome_safe_storage_name=os.getenv("BRIDGE_CHROME_SAFE_STORAGE_NAME", "Chrome Safe Storage"),
            request_timeout_seconds=int(os.getenv("BRIDGE_REQUEST_TIMEOUT_SECONDS", "20")),
        )
