"""AI provider registry - lookup by capability type."""

from __future__ import annotations

import logging
from typing import Optional

from app.integrations.ai.base import AICapabilityType, BaseAIProvider

logger = logging.getLogger(__name__)


class AIProviderRegistry:
    """Registry for AI providers, organized by capability type.

    Supports registering multiple providers per capability and
    selecting the appropriate one based on requirements.
    """

    def __init__(self) -> None:
        # capability -> {provider_name -> provider_instance}
        self._providers: dict[AICapabilityType, dict[str, BaseAIProvider]] = {}
        # capability -> default_provider_name
        self._defaults: dict[AICapabilityType, str] = {}
        # provider_name -> enabled
        self._enabled: dict[str, bool] = {}

    def register(
        self,
        provider: BaseAIProvider,
        *,
        is_default: bool = False,
        enabled: bool = True,
    ) -> None:
        """Register an AI provider for its declared capabilities.

        Args:
            provider: The AI provider instance.
            is_default: Whether this should be the default for its capabilities.
            enabled: Whether the provider is initially enabled.
        """
        name = provider.provider_name

        for capability in provider.capabilities:
            if capability not in self._providers:
                self._providers[capability] = {}
            self._providers[capability][name] = provider

            if is_default or capability not in self._defaults:
                self._defaults[capability] = name

        self._enabled[name] = enabled
        logger.info(
            f"Registered AI provider '{name}' with capabilities: "
            f"{[c.value for c in provider.capabilities]} "
            f"(default={is_default}, enabled={enabled})"
        )

    def unregister(self, provider_name: str) -> bool:
        """Remove a provider from the registry.

        Returns:
            True if provider was found and removed.
        """
        removed = False
        for capability in list(self._providers.keys()):
            if provider_name in self._providers[capability]:
                del self._providers[capability][provider_name]
                removed = True
                # Update default if this was the default
                if self._defaults.get(capability) == provider_name:
                    remaining = list(self._providers[capability].keys())
                    self._defaults[capability] = remaining[0] if remaining else ""

        self._enabled.pop(provider_name, None)
        if removed:
            logger.info(f"Unregistered AI provider '{provider_name}'")
        return removed

    def get_provider(
        self,
        *,
        capability: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Optional[BaseAIProvider]:
        """Get a specific provider by name and/or capability.

        Args:
            capability: Desired capability type (string or AICapabilityType).
            provider_name: Specific provider name. If None, returns default.

        Returns:
            Provider instance or None.
        """
        # If provider_name given, find it across capabilities
        if provider_name and not capability:
            for cap_providers in self._providers.values():
                if provider_name in cap_providers:
                    provider = cap_providers[provider_name]
                    if self._enabled.get(provider_name, True):
                        return provider
            return None

        # Resolve capability
        cap: Optional[AICapabilityType] = None
        if isinstance(capability, AICapabilityType):
            cap = capability
        elif isinstance(capability, str):
            try:
                cap = AICapabilityType(capability)
            except ValueError:
                return None

        if cap is None:
            return None

        cap_providers = self._providers.get(cap, {})

        if provider_name:
            provider = cap_providers.get(provider_name)
            if provider and self._enabled.get(provider_name, True):
                return provider
            return None

        # Return default provider for this capability
        default_name = self._defaults.get(cap, "")
        if default_name and default_name in cap_providers:
            if self._enabled.get(default_name, True):
                return cap_providers[default_name]

        # Fallback: return first enabled provider
        for name, provider in cap_providers.items():
            if self._enabled.get(name, True):
                return provider

        return None

    def get_providers_by_capability(
        self, capability: AICapabilityType
    ) -> list[BaseAIProvider]:
        """Get all enabled providers for a capability.

        Args:
            capability: The capability type.

        Returns:
            List of enabled providers.
        """
        cap_providers = self._providers.get(capability, {})
        return [
            provider
            for name, provider in cap_providers.items()
            if self._enabled.get(name, True)
        ]

    def set_default(self, capability: AICapabilityType, provider_name: str) -> bool:
        """Set the default provider for a capability.

        Returns:
            True if provider exists for that capability.
        """
        cap_providers = self._providers.get(capability, {})
        if provider_name in cap_providers:
            self._defaults[capability] = provider_name
            logger.info(
                f"Set default for {capability.value}: '{provider_name}'"
            )
            return True
        return False

    def enable(self, provider_name: str) -> bool:
        """Enable a provider."""
        if provider_name in self._enabled:
            self._enabled[provider_name] = True
            return True
        return False

    def disable(self, provider_name: str) -> bool:
        """Disable a provider."""
        if provider_name in self._enabled:
            self._enabled[provider_name] = False
            return True
        return False

    def list_providers(self) -> list[dict[str, object]]:
        """List all registered providers with their info."""
        seen: set[str] = set()
        result: list[dict[str, object]] = []

        for cap_providers in self._providers.values():
            for name, provider in cap_providers.items():
                if name in seen:
                    continue
                seen.add(name)
                result.append({
                    "name": name,
                    "display_name": provider.meta.display_name,
                    "capabilities": [c.value for c in provider.capabilities],
                    "enabled": self._enabled.get(name, True),
                    "version": provider.meta.version,
                })

        return result

    def list_capabilities(self) -> list[dict[str, object]]:
        """List all capabilities with their available providers."""
        result: list[dict[str, object]] = []
        for cap, providers in self._providers.items():
            enabled_providers = [
                name for name in providers if self._enabled.get(name, True)
            ]
            result.append({
                "capability": cap.value,
                "providers": list(providers.keys()),
                "enabled_providers": enabled_providers,
                "default": self._defaults.get(cap, ""),
            })
        return result


# Global AI registry singleton
_ai_registry: Optional[AIProviderRegistry] = None


def get_ai_registry() -> AIProviderRegistry:
    """Get or create the global AI provider registry."""
    global _ai_registry
    if _ai_registry is None:
        _ai_registry = AIProviderRegistry()
    return _ai_registry
