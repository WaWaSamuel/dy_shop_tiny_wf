"""Browser cookie helpers for local automation."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import Settings, get_settings


class BrowserCookieProvider:
    """Load cookie headers from browser storage or explicit strings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_cookie_jar(
        self,
        *,
        domain_patterns: Iterable[str],
        cookie_header: str = "",
    ) -> httpx.Cookies:
        domain_patterns = tuple(domain_patterns)
        if cookie_header.strip():
            return self.cookies_from_header(
                cookie_header,
                default_domain=self._default_domain(domain_patterns),
            )
        return self.cookies_from_chrome(domain_patterns=domain_patterns)

    def cookies_from_header(self, cookie_header: str, default_domain: str = "") -> httpx.Cookies:
        jar = httpx.Cookies()
        for segment in re.split(r";\s*", cookie_header.strip()):
            if not segment or "=" not in segment:
                continue
            name, value = segment.split("=", 1)
            name = name.strip()
            if not name:
                continue
            jar.set(name, value.strip(), domain=default_domain, path="/")
        return jar

    def cookie_header_from_chrome(self, *, domain_patterns: Iterable[str]) -> str:
        jar = self.cookies_from_chrome(domain_patterns=domain_patterns)
        return self.cookie_header_from_jar(jar)

    def cookies_from_chrome(self, *, domain_patterns: Iterable[str]) -> httpx.Cookies:
        domain_patterns = tuple(domain_patterns)
        db_path = self._resolve_cookie_db_path()
        if not db_path.exists():
            raise RuntimeError(f"Chrome cookie DB not found: {db_path}")

        where_clause = " OR ".join(["host_key LIKE ?"] * len(domain_patterns))
        params = [self._to_like_pattern(pattern) for pattern in domain_patterns]
        if not params:
            raise RuntimeError("No cookie domain patterns configured.")

        with tempfile.TemporaryDirectory(prefix="browser-cookie-db-") as temp_dir:
            temp_db_path = Path(temp_dir) / "Cookies"
            shutil.copy2(db_path, temp_db_path)
            connection = sqlite3.connect(temp_db_path)
            try:
                cursor = connection.execute(
                    f"""
                    SELECT host_key, name, value, encrypted_value, path
                    FROM cookies
                    WHERE {where_clause}
                    """,
                    params,
                )
                rows = cursor.fetchall()
            finally:
                connection.close()

        password = self._get_safe_storage_password()
        jar = httpx.Cookies()
        for host_key, name, value, encrypted_value, path in rows:
            decrypted = value or self._decrypt_chrome_cookie(encrypted_value, password)
            if not decrypted:
                continue
            decrypted = self._normalize_cookie_value(decrypted)
            if not self._is_ascii_cookie_value(decrypted):
                continue
            domain = host_key if host_key.startswith(".") else f".{host_key.lstrip('.')}"
            jar.set(name, decrypted, domain=domain, path=path or "/")

        if not jar:
            joined = ", ".join(domain_patterns)
            raise RuntimeError(f"No browser cookies found for configured domains: {joined}")
        return jar

    def cookie_header_from_jar(self, cookies: httpx.Cookies) -> str:
        pairs: list[str] = []
        seen: set[str] = set()
        for cookie in cookies.jar:
            if cookie.name in seen:
                continue
            if not self._is_ascii_cookie_value(cookie.value):
                continue
            seen.add(cookie.name)
            pairs.append(f"{cookie.name}={cookie.value}")
        return "; ".join(pairs)

    def get_cookie_value(self, cookies: httpx.Cookies, name: str) -> str:
        for cookie in cookies.jar:
            if cookie.name == name:
                return cookie.value
        return ""

    def _resolve_cookie_db_path(self) -> Path:
        explicit_path = self.settings.BROWSER_CHROME_COOKIES_PATH or self.settings.WEREAD_CHROME_COOKIES_PATH
        if explicit_path:
            return Path(explicit_path).expanduser()
        profile_name = self.settings.BROWSER_CHROME_PROFILE_NAME or self.settings.WEREAD_CHROME_PROFILE_NAME
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

        for env_key in ("SUDO_USER", "LOGNAME", "USER"):
            env_user = os.environ.get(env_key)
            if env_user and env_user != "root":
                add_home(Path("/Users") / env_user)

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
            (self.settings.BROWSER_CHROME_SAFE_STORAGE_NAME or self.settings.WEREAD_CHROME_SAFE_STORAGE_NAME, None),
            ("Chrome Safe Storage", "Chrome"),
            ("Chromium Safe Storage", "Chromium"),
        ]
        attempted: list[str] = []

        for service_name, account_name in candidates:
            command = ["security", "find-generic-password", "-w", "-s", service_name]
            if account_name:
                command.extend(["-a", account_name])
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            password = (result.stdout or "").strip()
            if result.returncode == 0 and password:
                return password
            attempted.append(f"{service_name}/{account_name or '*'}:{(result.stderr or '').strip() or result.returncode}")

        raise RuntimeError(
            "Failed to read Chrome Safe Storage password. "
            "Grant terminal access to Keychain or supply cookies explicitly. "
            f"Details: {' | '.join(attempted)}"
        )

    def _decrypt_chrome_cookie(self, encrypted_value: bytes, password: str) -> str:
        if not encrypted_value:
            return ""
        payload = encrypted_value
        if payload.startswith(b"v10"):
            payload = payload[3:]

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
        if not normalized:
            return "%"
        if "%" in normalized:
            return normalized
        return f"%{normalized.lstrip('.')}"

    def _default_domain(self, domain_patterns: Iterable[str]) -> str:
        for pattern in domain_patterns:
            normalized = pattern.strip()
            if not normalized:
                continue
            return normalized if normalized.startswith(".") else f".{normalized}"
        return ""

    def _is_ascii_cookie_value(self, value: str) -> bool:
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            return False
        return True

    def _normalize_cookie_value(self, value: str) -> str:
        if any(ord(ch) < 32 for ch in value) and "@" in value:
            return value.split("@", 1)[1]
        return value
