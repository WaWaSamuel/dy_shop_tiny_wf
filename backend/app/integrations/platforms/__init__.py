"""Platform providers registration."""

from app.integrations.registry import get_provider_registry
from app.integrations.platforms.douyin_shop import DouyinShopProvider


def register_platform_providers() -> None:
    """Register all platform providers with the global registry."""
    registry = get_provider_registry()
    registry.register("platforms", DouyinShopProvider())
    # TODO: Register additional platform providers here
    # registry.register("platforms", TaobaoProvider())
    # registry.register("platforms", PinduoduoProvider())
