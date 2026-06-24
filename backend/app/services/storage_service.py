"""Cloud storage service for OSS (Object Storage Service) operations.

Provides upload, download, presigned URL generation, and deletion
for managing product images, design assets, and other files.
"""

import hashlib
import hmac
import logging
import os
import time
from base64 import b64encode
from datetime import datetime, timezone
from email.utils import formatdate
from typing import Any
from urllib.parse import quote, urljoin

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default content types by extension
CONTENT_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".json": "application/json",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
}


class StorageService:
    """Cloud storage service for managing files on Alibaba Cloud OSS.

    Provides upload, download, presigned URL generation, and deletion
    operations with proper signing and error handling.

    Usage:
        storage = StorageService()
        url = await storage.upload_file("/tmp/image.jpg", "products/123/main.jpg")
        presigned = await storage.generate_presigned_url("products/123/main.jpg")
        await storage.close()
    """

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self._access_key = access_key or settings.OSS_ACCESS_KEY
        self._secret_key = secret_key or settings.OSS_SECRET_KEY
        self._bucket = bucket or settings.OSS_BUCKET
        self._endpoint = (endpoint or settings.OSS_ENDPOINT).rstrip("/")

        # Derive bucket URL
        # e.g., https://bucket-name.oss-cn-hangzhou.aliyuncs.com
        endpoint_host = self._endpoint.replace("https://", "").replace("http://", "")
        self._bucket_url = f"https://{self._bucket}.{endpoint_host}"

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def upload_file(self, local_path: str, remote_key: str) -> str:
        """Upload a local file to OSS.

        Args:
            local_path: Absolute path to the local file.
            remote_key: Object key (path) in the bucket (e.g., "products/123/main.jpg").

        Returns:
            Public URL of the uploaded file.

        Raises:
            FileNotFoundError: If local_path doesn't exist.
            Exception: On upload failure.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")

        # Determine content type
        ext = os.path.splitext(local_path)[1].lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

        # Read file
        with open(local_path, "rb") as f:
            file_content = f.read()

        # Calculate content MD5
        content_md5 = b64encode(hashlib.md5(file_content).digest()).decode()

        # Build request
        date_str = formatdate(usegmt=True)
        remote_key = remote_key.lstrip("/")
        url = f"{self._bucket_url}/{quote(remote_key)}"

        # Sign the request
        string_to_sign = (
            f"PUT\n{content_md5}\n{content_type}\n{date_str}\n"
            f"/{self._bucket}/{remote_key}"
        )
        signature = self._sign(string_to_sign)

        headers = {
            "Date": date_str,
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Authorization": f"OSS {self._access_key}:{signature}",
        }

        try:
            response = await self._client.put(url, content=file_content, headers=headers)

            if response.status_code not in (200, 201):
                raise Exception(
                    f"OSS upload failed: {response.status_code} - {response.text}"
                )

            public_url = f"{self._bucket_url}/{remote_key}"
            logger.info("[Storage] Uploaded: %s -> %s", local_path, public_url)
            return public_url

        except httpx.TimeoutException as exc:
            logger.error("[Storage] Upload timeout for %s: %s", remote_key, exc)
            raise Exception(f"Upload timeout: {exc}") from exc

    async def download_file(self, remote_key: str, local_path: str) -> str:
        """Download a file from OSS to local storage.

        Args:
            remote_key: Object key in the bucket.
            local_path: Local path to save the downloaded file.

        Returns:
            The local_path where the file was saved.

        Raises:
            Exception: On download failure.
        """
        remote_key = remote_key.lstrip("/")
        url = f"{self._bucket_url}/{quote(remote_key)}"

        # Sign the request
        date_str = formatdate(usegmt=True)
        string_to_sign = f"GET\n\n\n{date_str}\n/{self._bucket}/{remote_key}"
        signature = self._sign(string_to_sign)

        headers = {
            "Date": date_str,
            "Authorization": f"OSS {self._access_key}:{signature}",
        }

        try:
            response = await self._client.get(url, headers=headers)

            if response.status_code != 200:
                raise Exception(
                    f"OSS download failed: {response.status_code} - {response.text}"
                )

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(response.content)

            logger.info("[Storage] Downloaded: %s -> %s", remote_key, local_path)
            return local_path

        except httpx.TimeoutException as exc:
            logger.error("[Storage] Download timeout for %s: %s", remote_key, exc)
            raise Exception(f"Download timeout: {exc}") from exc

    async def generate_presigned_url(self, remote_key: str, expires: int = 3600) -> str:
        """Generate a presigned URL for temporary access to a file.

        Args:
            remote_key: Object key in the bucket.
            expires: URL validity duration in seconds (default 1 hour).

        Returns:
            Presigned URL string with temporary access authorization.
        """
        remote_key = remote_key.lstrip("/")
        expiration = int(time.time()) + expires

        # Build the string to sign for presigned URL
        string_to_sign = f"GET\n\n\n{expiration}\n/{self._bucket}/{remote_key}"
        signature = self._sign(string_to_sign)

        # Build presigned URL with query parameters
        presigned_url = (
            f"{self._bucket_url}/{quote(remote_key)}"
            f"?OSSAccessKeyId={quote(self._access_key)}"
            f"&Expires={expiration}"
            f"&Signature={quote(signature)}"
        )

        logger.debug("[Storage] Generated presigned URL for: %s (expires in %ds)", remote_key, expires)
        return presigned_url

    async def delete_file(self, remote_key: str) -> bool:
        """Delete a file from OSS.

        Args:
            remote_key: Object key in the bucket to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        remote_key = remote_key.lstrip("/")
        url = f"{self._bucket_url}/{quote(remote_key)}"

        # Sign the request
        date_str = formatdate(usegmt=True)
        string_to_sign = f"DELETE\n\n\n{date_str}\n/{self._bucket}/{remote_key}"
        signature = self._sign(string_to_sign)

        headers = {
            "Date": date_str,
            "Authorization": f"OSS {self._access_key}:{signature}",
        }

        try:
            response = await self._client.delete(url, headers=headers)

            if response.status_code in (200, 204):
                logger.info("[Storage] Deleted: %s", remote_key)
                return True
            else:
                logger.warning(
                    "[Storage] Delete failed for %s: %d - %s",
                    remote_key, response.status_code, response.text,
                )
                return False

        except httpx.TimeoutException as exc:
            logger.error("[Storage] Delete timeout for %s: %s", remote_key, exc)
            return False

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _sign(self, string_to_sign: str) -> str:
        """Generate HMAC-SHA1 signature for OSS request.

        Args:
            string_to_sign: The canonical string to sign.

        Returns:
            Base64-encoded HMAC-SHA1 signature.
        """
        h = hmac.new(
            self._secret_key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        )
        return b64encode(h.digest()).decode()
