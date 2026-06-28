"""Runtime tool registry for agent/skill callable business capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.services.browser_news_digest import BrowserNewsDigestService
from app.services.feishu_bot import get_feishu_bot_service
from app.services.news_aggregator import NewsAggregationService
from app.services.news_push_history import NewsPushHistoryService
from app.services.runtime_center import (
    get_runtime_catalog,
    get_runtime_logs,
    get_runtime_overview,
)
from app.services.session_sources import SessionSourceService


ToolHandler = Callable[["ToolContext", dict[str, Any]], Awaitable[Any]]


@dataclass
class ToolContext:
    """Execution context passed to runtime tools."""

    user_id: str | None = None
    redis: Any | None = None
    db: Any | None = None


@dataclass
class RuntimeToolDefinition:
    """Tool metadata for discovery and invocation."""

    name: str
    summary: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_summary: str = ""
    tags: list[str] = field(default_factory=list)
    handler: ToolHandler | None = None


class RuntimeToolRegistry:
    """In-process registry for backend business tools."""

    def __init__(self) -> None:
        self._tools: dict[str, RuntimeToolDefinition] = {}

    def register(self, tool: RuntimeToolDefinition) -> None:
        if tool.handler is None:
            raise ValueError(f"Tool {tool.name} missing handler")
        self._tools[tool.name] = tool

    def list_tools(self) -> list[RuntimeToolDefinition]:
        return sorted(self._tools.values(), key=lambda item: item.name)

    def get(self, name: str) -> RuntimeToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown runtime tool: {name}")
        return tool

    async def invoke(self, name: str, *, context: ToolContext, args: dict[str, Any]) -> Any:
        tool = self.get(name)
        return await tool.handler(context, args)


def _now_digest_service():
    return BrowserNewsDigestService()


async def runtime_overview_tool(context: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if context.db is None or context.user_id is None:
        raise RuntimeError("runtime.get_overview 需要 db 和 user_id")
    limit = int(args.get("log_limit", 60))
    return await get_runtime_overview(context.db, context.user_id, log_limit=limit)


async def runtime_logs_tool(context: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    if context.db is None or context.user_id is None:
        raise RuntimeError("runtime.list_logs 需要 db 和 user_id")
    return await get_runtime_logs(
        context.db,
        context.user_id,
        capability_kind=args.get("capability_kind"),
        capability_key=args.get("capability_key"),
        workflow_id=args.get("workflow_id"),
        project_key=args.get("project_key"),
        status=args.get("status"),
        search=args.get("search"),
        limit=int(args.get("limit", 80)),
    )


async def runtime_catalog_tool(context: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    del args
    if context.db is None or context.user_id is None:
        raise RuntimeError("runtime.list_capabilities 需要 db 和 user_id")
    return await get_runtime_catalog(context.db, context.user_id)


async def session_sources_list_tool(context: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    if context.redis is None:
        raise RuntimeError("session_sources.list 需要 redis")
    service = SessionSourceService()
    return await service.list_sources(
        redis=context.redis,
        refresh=bool(args.get("refresh", False)),
    )


async def session_source_probe_tool(context: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if context.redis is None:
        raise RuntimeError("session_sources.probe 需要 redis")
    source_id = str(args.get("source_id") or "").strip()
    if not source_id:
        raise RuntimeError("session_sources.probe 缺少 source_id")
    service = SessionSourceService()
    return await service.probe_source(
        redis=context.redis,
        source_id=source_id,
        refresh_cookie_from_browser=bool(args.get("refresh_cookie_from_browser", False)),
    )


async def news_get_digest_tool(context: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if context.redis is None:
        raise RuntimeError("news.get_digest 需要 redis")
    refresh = bool(args.get("refresh", False))
    browser_service = BrowserNewsDigestService()
    browser_digest = await browser_service.get_latest_digest(redis=context.redis)
    if browser_digest:
        push_history = NewsPushHistoryService()
        browser_digest["push_records"] = await push_history.list_records(
            redis=context.redis,
            window_end=browser_service.parse_window_end(browser_digest),
        )
        return browser_digest

    service = NewsAggregationService()
    digest = await service.get_digest(redis=context.redis, force_refresh=refresh)
    push_history = NewsPushHistoryService()
    _, window_end = service.get_latest_completed_window()
    digest["push_records"] = await push_history.list_records(redis=context.redis, window_end=window_end)
    return digest


async def news_list_sources_tool(context: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    del context, args
    service = NewsAggregationService()
    return service.get_sources()


async def im_send_card_tool(context: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    del context
    title = str(args.get("title") or "").strip()
    if not title:
        raise RuntimeError("im.send_card 缺少 title")

    raw_lines = args.get("lines") or []
    if isinstance(raw_lines, str):
        lines = [raw_lines]
    else:
        lines = [str(item).strip() for item in raw_lines if str(item).strip()]
    if not lines:
        raise RuntimeError("im.send_card 缺少 lines")

    template = str(args.get("template") or "blue").strip() or "blue"
    open_id = str(args.get("open_id") or "").strip() or None
    chat_id = str(args.get("chat_id") or "").strip() or None

    bot = get_feishu_bot_service()
    if not bot.ready:
        raise RuntimeError("Feishu bot is not ready")

    return await bot.push_info_card(
        title=title,
        lines=lines,
        template=template,
        open_id=open_id,
        chat_id=chat_id,
    )


registry = RuntimeToolRegistry()

registry.register(
    RuntimeToolDefinition(
        name="runtime.get_overview",
        summary="获取执行记录中心总览、能力目录与最近记录。",
        input_schema={"type": "object", "properties": {"log_limit": {"type": "integer", "default": 60}}},
        output_summary="返回 summary、catalog、recent_records 和 filter_options。",
        tags=["runtime", "overview"],
        handler=runtime_overview_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="runtime.list_logs",
        summary="按条件查询执行记录。",
        input_schema={
            "type": "object",
            "properties": {
                "capability_kind": {"type": "string"},
                "capability_key": {"type": "string"},
                "workflow_id": {"type": "string"},
                "project_key": {"type": "string"},
                "status": {"type": "string"},
                "search": {"type": "string"},
                "limit": {"type": "integer", "default": 80},
            },
        },
        output_summary="返回执行记录数组。",
        tags=["runtime", "logs"],
        handler=runtime_logs_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="runtime.list_capabilities",
        summary="返回当前项目已登记和已发现的 workflow/agent/skill 能力目录。",
        input_schema={"type": "object", "properties": {}},
        output_summary="返回能力目录及最近运行统计。",
        tags=["runtime", "catalog"],
        handler=runtime_catalog_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="session_sources.list",
        summary="列出外部站点会话源及健康状态。",
        input_schema={"type": "object", "properties": {"refresh": {"type": "boolean", "default": False}}},
        output_summary="返回会话源数组。",
        tags=["session", "guard"],
        handler=session_sources_list_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="session_sources.probe",
        summary="探测单个外部站点会话源状态，可选从浏览器刷新 cookie。",
        input_schema={
            "type": "object",
            "required": ["source_id"],
            "properties": {
                "source_id": {"type": "string"},
                "refresh_cookie_from_browser": {"type": "boolean", "default": False},
            },
        },
        output_summary="返回单个会话源状态。",
        tags=["session", "guard"],
        handler=session_source_probe_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="news.get_digest",
        summary="获取资讯摘要结果，优先读取浏览器提交的 digest，其次回退聚合服务。",
        input_schema={"type": "object", "properties": {"refresh": {"type": "boolean", "default": False}}},
        output_summary="返回资讯摘要完整结构。",
        tags=["news", "digest"],
        handler=news_get_digest_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="news.list_sources",
        summary="列出资讯源配置。",
        input_schema={"type": "object", "properties": {}},
        output_summary="返回资讯源数组。",
        tags=["news", "digest"],
        handler=news_list_sources_tool,
    )
)
registry.register(
    RuntimeToolDefinition(
        name="im.send_card",
        summary="将结构化文本拼装为飞书交互式消息卡片，并发送到指定 open_id 或 chat_id。",
        input_schema={
            "type": "object",
            "required": ["title", "lines"],
            "properties": {
                "title": {"type": "string"},
                "lines": {"type": "array", "items": {"type": "string"}},
                "template": {"type": "string", "default": "blue"},
                "open_id": {"type": "string"},
                "chat_id": {"type": "string"},
            },
        },
        output_summary="返回 receive_id_type、receive_id、target_hint 和 message_id。",
        tags=["im", "feishu", "card"],
        handler=im_send_card_tool,
    )
)
