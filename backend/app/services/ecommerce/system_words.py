"""System word rule engine - match category+tags and inject words."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemWordRule:
    """A single system word injection rule."""

    id: str
    name: str
    # Matching criteria
    categories: list[str] = field(default_factory=list)  # Match any of these categories
    tags: list[str] = field(default_factory=list)  # Match any of these tags
    platforms: list[str] = field(default_factory=list)  # Match specific platforms
    # Injection configuration
    prefix_words: list[str] = field(default_factory=list)  # Words to prepend
    suffix_words: list[str] = field(default_factory=list)  # Words to append
    required_words: list[str] = field(default_factory=list)  # Must be present
    forbidden_words: list[str] = field(default_factory=list)  # Must not be present
    replacement_map: dict[str, str] = field(default_factory=dict)  # Word replacements
    # Rule metadata
    priority: int = 0  # Higher = applied first
    enabled: bool = True
    description: str = ""


@dataclass
class InjectionResult:
    """Result of applying system word rules to content."""

    original_text: str
    modified_text: str
    rules_applied: list[str]
    words_added: list[str]
    words_replaced: list[tuple[str, str]]
    violations: list[dict[str, Any]]
    is_compliant: bool


class SystemWordEngine:
    """Rule engine for system word matching and injection.

    Matches products by category and tags, then injects required words,
    removes forbidden words, and applies replacements.
    """

    def __init__(self) -> None:
        self._rules: list[SystemWordRule] = []

    def load_rules(self, rules: list[SystemWordRule]) -> None:
        """Load a set of rules into the engine, replacing existing ones."""
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        logger.info(f"Loaded {len(self._rules)} system word rules")

    def add_rule(self, rule: SystemWordRule) -> None:
        """Add a single rule and re-sort."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if found and removed."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return len(self._rules) < before

    def get_matching_rules(
        self,
        *,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        platform: Optional[str] = None,
    ) -> list[SystemWordRule]:
        """Find all rules matching the given criteria.

        A rule matches if:
        - Its category list is empty (matches all) OR contains the given category
        - Its tag list is empty (matches all) OR overlaps with given tags
        - Its platform list is empty (matches all) OR contains the given platform
        - The rule is enabled

        Args:
            category: Product category.
            tags: Product tags.
            platform: Target platform.

        Returns:
            List of matching rules, sorted by priority.
        """
        matching: list[SystemWordRule] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Category match
            if rule.categories and category:
                if category not in rule.categories:
                    continue
            elif rule.categories and not category:
                continue

            # Tag match (any overlap)
            if rule.tags and tags:
                if not set(rule.tags) & set(tags):
                    continue
            elif rule.tags and not tags:
                continue

            # Platform match
            if rule.platforms and platform:
                if platform not in rule.platforms:
                    continue
            elif rule.platforms and not platform:
                continue

            matching.append(rule)

        return matching

    def apply_rules(
        self,
        text: str,
        *,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        platform: Optional[str] = None,
    ) -> InjectionResult:
        """Apply all matching rules to the given text.

        Rules are applied in priority order (highest first).

        Args:
            text: The content text to process.
            category: Product category for rule matching.
            tags: Product tags for rule matching.
            platform: Target platform for rule matching.

        Returns:
            InjectionResult with modified text and application details.
        """
        rules = self.get_matching_rules(
            category=category, tags=tags, platform=platform
        )

        modified = text
        rules_applied: list[str] = []
        words_added: list[str] = []
        words_replaced: list[tuple[str, str]] = []
        violations: list[dict[str, Any]] = []

        for rule in rules:
            applied = False

            # Apply replacements
            for old_word, new_word in rule.replacement_map.items():
                if old_word in modified:
                    modified = modified.replace(old_word, new_word)
                    words_replaced.append((old_word, new_word))
                    applied = True

            # Check forbidden words
            for word in rule.forbidden_words:
                if word in modified:
                    violations.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "type": "forbidden_word",
                        "word": word,
                        "message": f"Forbidden word '{word}' found in text",
                    })
                    # Remove forbidden words
                    modified = modified.replace(word, "")
                    applied = True

            # Add required words if missing
            for word in rule.required_words:
                if word not in modified:
                    violations.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "type": "missing_required_word",
                        "word": word,
                        "message": f"Required word '{word}' missing from text",
                    })

            # Apply prefix words
            for prefix in rule.prefix_words:
                if not modified.startswith(prefix):
                    modified = f"{prefix} {modified}"
                    words_added.append(prefix)
                    applied = True

            # Apply suffix words
            for suffix in rule.suffix_words:
                if not modified.endswith(suffix):
                    modified = f"{modified} {suffix}"
                    words_added.append(suffix)
                    applied = True

            if applied:
                rules_applied.append(rule.id)

        # Clean up double spaces
        modified = re.sub(r"\s{2,}", " ", modified).strip()

        # Determine compliance: no forbidden word violations
        is_compliant = all(
            v["type"] != "forbidden_word" for v in violations
        )

        return InjectionResult(
            original_text=text,
            modified_text=modified,
            rules_applied=rules_applied,
            words_added=words_added,
            words_replaced=words_replaced,
            violations=violations,
            is_compliant=is_compliant,
        )

    def validate_text(
        self,
        text: str,
        *,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        platform: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Validate text against rules without modifying it.

        Returns:
            List of violations found.
        """
        rules = self.get_matching_rules(
            category=category, tags=tags, platform=platform
        )

        violations: list[dict[str, Any]] = []

        for rule in rules:
            for word in rule.forbidden_words:
                if word in text:
                    violations.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "type": "forbidden_word",
                        "word": word,
                        "severity": "error",
                    })

            for word in rule.required_words:
                if word not in text:
                    violations.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "type": "missing_required_word",
                        "word": word,
                        "severity": "warning",
                    })

        return violations


# Singleton engine instance
_engine_instance: Optional[SystemWordEngine] = None


def get_system_word_engine() -> SystemWordEngine:
    """Get or create the singleton SystemWordEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SystemWordEngine()
    return _engine_instance


async def load_rules_from_db(db: Any) -> None:
    """Load system word rules from database into the engine.

    Args:
        db: AsyncSession instance.
    """
    from app.models.system_word import SystemWordRuleModel  # type: ignore[import]
    from sqlalchemy import select

    engine = get_system_word_engine()

    stmt = select(SystemWordRuleModel).where(
        SystemWordRuleModel.enabled == True
    )
    result = await db.execute(stmt)
    rule_models = result.scalars().all()

    rules = [
        SystemWordRule(
            id=str(m.id),
            name=m.name,
            categories=m.categories or [],
            tags=m.tags or [],
            platforms=m.platforms or [],
            prefix_words=m.prefix_words or [],
            suffix_words=m.suffix_words or [],
            required_words=m.required_words or [],
            forbidden_words=m.forbidden_words or [],
            replacement_map=m.replacement_map or {},
            priority=m.priority or 0,
            enabled=m.enabled,
            description=m.description or "",
        )
        for m in rule_models
    ]

    engine.load_rules(rules)
    logger.info(f"Loaded {len(rules)} system word rules from database")
