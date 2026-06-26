"""Read and normalize host Chrome cookies for local bridge sync."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from bridge.config import BridgeSettings


class BrowserCookieProvider:
    """Load cookies from the host Chrome profile."""

    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings

    def cookie_header_from_chrome(self, *, domain_patterns: Iterable[str]) -> str:
        cookies = self.cookies_from_chrome(domain_patterns=domain_patterns)
        parts: list[str] = []
        for name in sorted(cookies):
            parts.append(f"{name}={cookies[name]}")
        return "; ".join(parts)

    def cookies_from_chrome(self, *, domain_patterns: Iterable[str]) -> dict[str, str]:
        patterns = tuple(domain_patterns)
        if not patterns:
            raise RuntimeError("No cookie domain patterns configured.")

        db_path = self._resolve_cookie_db_path()
        if not db_path.exists():
            raise RuntimeError(f"Chrome cookie DB not found: {db_path}")

        where_clause = " OR ".join(["host_key LIKE ?"] * len(patterns))
        params = [self._to_like_pattern(pattern) for pattern in patterns]

        with tempfile.TemporaryDirectory(prefix="dyshop-bridge-cookie-db-") as temp_dir:
            temp_db_path = Path(temp_dir) / "Cookies"
            shutil.copy2(db_path, temp_db_path)
            connection = sqlite3.connect(temp_db_path)
            try:
                cursor = connection.execute(
                    f"""
                    SELECT host_key, name, value, encrypted_value
                    FROM cookies
                    WHERE {where_clause}
                    """,
                    params,
                )
                rows = cursor.fetchall()
            finally:
                connection.close()

        password = self._get_safe_storage_password()
        cookies: dict[str, str] = {}
        for _host_key, name, value, encrypted_value in rows:
            decrypted = value or self._decrypt_chrome_cookie(encrypted_value, password)
            if not decrypted:
                continue
            normalized = self._normalize_cookie_value(decrypted)
            if not self._is_ascii_cookie_value(normalized):
                continue
            cookies[name] = normalized

        if not cookies:
            raise RuntimeError("No matching cookies found in Chrome profile.")
        return cookies

    def _resolve_cookie_db_path(self) -> Path:
        explicit_path = self.settings.chrome_cookies_path.strip()
        if explicit_path:
            return Path(explicit_path).expanduser()

        profile_name = self.settings.chrome_profile_name
        candidates: list[Path] = []

        def add_home(home_path: Path | None) -> None:
            if home_path is None:
                return
            candidate = (
                home_path
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / profile_name
                / "Cookies"
            )
            if candidate not in candidates:
                candidates.append(candidate)

        add_home(Path.home())
        env_home = os.environ.get("HOME")
        if env_home:
            add_home(Path(env_home).expanduser())

        cwd_parts = Path.cwd().resolve().parts
        if len(cwd_parts) > 2 and cwd_parts[1] == "Users":
            add_home(Path("/") / cwd_parts[1] / cwd_parts[2])

        users_root = Path("/Users")
        if users_root.exists():
            for user_home in users_root.iterdir():
                if user_home.is_dir():
                    add_home(user_home)

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _get_safe_storage_password(self) -> str:
        candidates = [
            (self.settings.chrome_safe_storage_name, None),
            ("Chrome Safe Storage", "Chrome"),
            ("Chromium Safe Storage", "Chromium"),
        ]
        for service_name, account_name in candidates:
            command = ["security", "find-generic-password", "-w", "-s", service_name]
            if account_name:
                command.extend(["-a", account_name])
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            password = (result.stdout or "").strip()
            if result.returncode == 0 and password:
                return password
        raise RuntimeError("Failed to read Chrome Safe Storage password from macOS Keychain.")

    def _decrypt_chrome_cookie(self, encrypted_value: bytes, password: str) -> str:
        if not encrypted_value:
            return ""
        payload = encrypted_value[3:] if encrypted_value.startswith(b"v10") else encrypted_value
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA1(),
            length=16,
            salt=b"saltysalt",
            iterations=1003,
            backend=default_backend(),
        )
        key = kdf.derive(password.encode("utf-8"))
        cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(payload) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        try:
            value = unpadder.update(decrypted) + unpadder.finalize()
        except ValueError:
            return ""
        return value.decode("utf-8", errors="ignore")

    def _to_like_pattern(self, pattern: str) -> str:
        normalized = pattern.strip()
        if "%" in normalized:
            return normalized
        return f"%{normalized.lstrip('.')}"

    def _normalize_cookie_value(self, value: str) -> str:
        if any(ord(ch) < 32 for ch in value) and "@" in value:
            return value.split("@", 1)[1]
        return value

    def _is_ascii_cookie_value(self, value: str) -> bool:
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            return False
        return True
