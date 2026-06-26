"""Sync browser cookies from host Chrome into the local backend API."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.browser_cookie_provider import BrowserCookieProvider
from app.services.session_sources import SessionSourceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync host browser cookie to local backend session source.")
    parser.add_argument("--source", default="weread", help="Session source id, default: weread")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/api/v1",
        help="Backend API base URL, default: http://127.0.0.1:8000/api/v1",
    )
    return parser.parse_args()


async def build_cookie_header(source_id: str) -> str:
    service = SessionSourceService()
    definition = service.get_definition(source_id)
    provider = BrowserCookieProvider()
    return provider.cookie_header_from_chrome(domain_patterns=definition.domain_patterns)


def post_cookie_sync(api_url: str, source_id: str, cookie_header: str) -> dict:
    endpoint = f"{api_url.rstrip('/')}/session-sources/{source_id}/cookie-sync"
    payload = json.dumps({"cookie_header": cookie_header}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    args = parse_args()
    cookie_header = asyncio.run(build_cookie_header(args.source))
    try:
        result = post_cookie_sync(args.api_url, args.source, cookie_header)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(body)
        return exc.code or 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
