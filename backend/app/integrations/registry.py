"""Provider registry for managing integration providers by category."""

from __future__ import annotations

import logging
from typing import Any, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ProviderRegistry:
    """Registry for integration providers.

    Organizes providers by category (sourcing, platform, logistics, selection)
    and supports registration, lookup, and enable/disable management.
    """

    def __init__(self) -> None:
        # category -> {provider_name -> provider_instance}
        self._providers: dict[str, dict[str, Any]] = {}
        # category -> {provider_name -> enabled}
        self._enabled_status: dict[str, dict[str, bool]] = {}

    def register(
        self,
        category: str,
        provider: Any,
        *,
        enabled: bool = True,
    ) -> None:
        """Register a provider under a category.

        Args:
            category: Provider category (e.g., 'sourcing', 'platforms', 'logistics').
            provider: Provider instance (must have `provider_name` attribute).
            enabled: Whether the provider is initially enabled.

        Raises:
            ValueError: If provider doesn't have required attributes.
        """
        if not hasattr(provider, "provider_name"):
            raise ValueError(
                f"Provider must have a 'provider_name' attribute. "
                f"Got: {type(provider).__name__}"
            )

        name = provider.provider_name

        if category not in self._providers:
            self._providers[category] = {}
            self._enabled_status[category] = {}

        self._providers[category][name] = provider
        self._enabled_status[category][name] = enabled

        logger.info(
            f"Registered provider '{name}' in category '{category}' "
            f"(enabled={enabled})"
        )

    def unregister(self, category: str, provider_name: str) -> bool:
        """Remove a provider from the registry.

        Returns:
            True if provider was found and removed.
        """
        if category in self._providers and provider_name in self._providers[category]:
            del self._providers[category][provider_name]
            del self._enabled_status[category][provider_name]
            logger.info(f"Unregistered provider '{provider_name}' from '{category}'")
            return True
        return False

    def get(self, category: str, provider_name: str) -> Optional[Any]:
        """Get a specific provider by category and name.

        Args:
            category: Provider category.
            provider_name: Provider's unique name.

        Returns:
            Provider instance or None if not found.
        """
        return self._providers.get(category, {}).get(provider_name)

    def get_all(self, category: str) -> list[Any]:
        """Get all providers in a category (enabled and disabled).

        Args:
            category: Provider category.

        Returns:
            List of all provider instances in the category.
        """
        return list(self._providers.get(category, {}).values())

    def get_enabled(self, category: str) -> list[Any]:
        """Get only enabled providers in a category.

        Args:
            category: Provider category.

        Returns:
            List of enabled provider instances.
        """
        providers = self._providers.get(category, {})
        enabled_status = self._enabled_status.get(category, {})
        return [
            provider
            for name, provider in providers.items()
            if enabled_status.get(name, True)
        ]

    def enable(self, category: str, provider_name: str) -> bool:
        """Enable a provider.

        Returns:
            True if provider was found.
        """
        if category in self._enabled_status and provider_name in self._enabled_status[category]:
            self._enabled_status[category][provider_name] = True
            logger.info(f"Enabled provider '{provider_name}' in '{category}'")
            return True
        return False

    def disable(self, category: str, provider_name: str) -> bool:
        """Disable a provider without removing it.

        Returns:
            True if provider was found.
        """
        if category in self._enabled_status and provider_name in self._enabled_status[category]:
            self._enabled_status[category][provider_name] = False
            logger.info(f"Disabled provider '{provider_name}' in '{category}'")
            return True
        return False

    def is_enabled(self, category: str, provider_name: str) -> bool:
        """Check if a provider is enabled."""
        return self._enabled_status.get(category, {}).get(provider_name, False)

    def list_categories(self) -> list[str]:
        """Get all registered categories."""
        return list(self._providers.keys())

    def list_providers(self, category: str) -> list[dict[str, Any]]:
        """List providers in a category with their status.

        Returns:
            List of provider info dicts.
        """
        providers = self._providers.get(category, {})
        enabled_status = self._enabled_status.get(category, {})
        result = []
        for name, provider in providers.items():
            result.append({
                "name": name,
                "display_name": getattr(provider, "display_name", name),
                "category": category,
                "enabled": enabled_status.get(name, True),
                "class": type(provider).__name__,
            })
        return result


# Global registry singleton
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
