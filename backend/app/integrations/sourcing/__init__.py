"""Sourcing providers registration."""

from app.integrations.registry import get_provider_registry
from app.integrations.sourcing.alibaba_1688 import Alibaba1688Provider


def register_sourcing_providers() -> None:
    """Register all sourcing providers with the global registry."""
    registry = get_provider_registry()
    registry.register("sourcing", Alibaba1688Provider())
    # TODO: Register additional sourcing providers here
    # registry.register("sourcing", AliExpressProvider())
    # registry.register("sourcing", TaobaoProvider())
