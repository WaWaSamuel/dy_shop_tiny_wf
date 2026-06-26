"""Session source definitions shared by the local bridge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSourceDefinition:
    id: str
    name: str
    login_url: str
    domain_patterns: tuple[str, ...]


SESSION_SOURCES: dict[str, SessionSourceDefinition] = {
    "weread": SessionSourceDefinition(
        id="weread",
        name="微信读书",
        login_url="https://weread.qq.com/web/shelf",
        domain_patterns=("weread.qq.com",),
    ),
}


def get_definition(source_id: str) -> SessionSourceDefinition:
    try:
        return SESSION_SOURCES[source_id]
    except KeyError as exc:
        raise RuntimeError(f"Unknown session source: {source_id}") from exc


def list_sources() -> list[dict[str, str]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "login_url": item.login_url,
        }
        for item in SESSION_SOURCES.values()
    ]
