"""Knowledge base manager for FAQ matching and auto-extraction.

Provides semantic search over known question-answer pairs, and can
automatically extract new FAQ entries from conversation histories.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.modules.feedback.schemas import KBEntry

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """Manages a knowledge base of FAQ entries for automated responses.

    Uses embedding-based semantic search to find relevant answers,
    and provides utilities to grow the KB from conversation logs.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        # In-memory store; production would use a vector DB (e.g., Milvus, Qdrant)
        self._entries: list[KBEntry] = []

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses the configured AI API's embedding endpoint.
        """
        client = await self._get_client()
        try:
            response = await client.post(
                f"{settings.AI_API_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-3-small",
                    "input": text[:2000],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except httpx.HTTPError as e:
            logger.error("Embedding API error: %s", e)
            return []
        finally:
            if self._http_client is None:
                await client.aclose()

    def _cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    async def search(
        self,
        query: str,
        product_id: str | None = None,
        top_k: int = 3,
        threshold: float = 0.75,
    ) -> list[KBEntry]:
        """Search the knowledge base for entries matching the query.

        Uses semantic similarity (embeddings) for matching. Optionally
        filters by product_id for product-specific FAQ.

        Args:
            query: The customer's question or search text.
            product_id: Optional product ID to narrow results.
            top_k: Maximum number of results to return.
            threshold: Minimum similarity score to include a result.

        Returns:
            List of KBEntry objects sorted by relevance, with
            similarity_score populated.
        """
        if not query.strip():
            return []

        query_embedding = await self._get_embedding(query)
        if not query_embedding:
            # Fallback to keyword matching when embeddings are unavailable
            return self._keyword_search(query, product_id, top_k)

        candidates = self._entries
        if product_id:
            candidates = [
                e for e in candidates
                if e.product_id == product_id or e.product_id == ""
            ]

        # Score each entry
        scored: list[tuple[float, KBEntry]] = []
        for entry in candidates:
            entry_embedding = await self._get_embedding(entry.question)
            if not entry_embedding:
                continue
            score = self._cosine_similarity(query_embedding, entry_embedding)
            if score >= threshold:
                entry_copy = entry.model_copy()
                entry_copy.similarity_score = score
                scored.append((score, entry_copy))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def _keyword_search(
        self,
        query: str,
        product_id: str | None,
        top_k: int,
    ) -> list[KBEntry]:
        """Simple keyword-based fallback search."""
        query_lower = query.lower()
        results: list[tuple[float, KBEntry]] = []

        candidates = self._entries
        if product_id:
            candidates = [
                e for e in candidates
                if e.product_id == product_id or e.product_id == ""
            ]

        for entry in candidates:
            question_lower = entry.question.lower()
            # Count overlapping characters as a rough relevance metric
            common_chars = sum(
                1 for c in query_lower if c in question_lower
            )
            if len(query_lower) > 0:
                score = common_chars / len(query_lower)
            else:
                score = 0.0

            if score > 0.3:
                entry_copy = entry.model_copy()
                entry_copy.similarity_score = score
                results.append((score, entry_copy))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:top_k]]

    async def add_entry(
        self,
        question: str,
        answer: str,
        category: str = "",
        product_id: str = "",
    ) -> KBEntry:
        """Add a new FAQ entry to the knowledge base.

        Args:
            question: The question text.
            answer: The answer text.
            category: Optional category label for organization.
            product_id: Optional product ID for product-specific FAQ.

        Returns:
            The created KBEntry with generated ID.
        """
        entry = KBEntry(
            id=str(uuid.uuid4()),
            question=question,
            answer=answer,
            category=category,
            product_id=product_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._entries.append(entry)
        logger.info(
            "Added KB entry id=%s category=%s product_id=%s",
            entry.id,
            category,
            product_id,
        )
        return entry

    async def extract_from_conversation(
        self,
        conversation_history: list[dict[str, str]],
    ) -> list[tuple[str, str]]:
        """Automatically extract FAQ pairs from a conversation history.

        Uses LLM to identify question-answer pairs suitable for the
        knowledge base from human agent conversations.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'.

        Returns:
            List of (question, answer) tuples extracted from the conversation.
        """
        if not conversation_history:
            return []

        # Build conversation text
        conv_text = "\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation_history
        )

        prompt = f"""Analyze the following customer service conversation and extract
reusable FAQ question-answer pairs. Only extract pairs where the answer is
informative and could help future customers with similar questions.

Conversation:
\"\"\"
{conv_text[:3000]}
\"\"\"

Respond with a JSON array of objects, each with "question" and "answer" keys.
If no useful FAQ pairs exist, return an empty array [].
"""

        client = await self._get_client()
        try:
            response = await client.post(
                f"{settings.AI_API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Parse the response
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                content = "\n".join(lines)

            pairs_data = json.loads(content)
            result: list[tuple[str, str]] = []
            for item in pairs_data:
                q = item.get("question", "").strip()
                a = item.get("answer", "").strip()
                if q and a:
                    result.append((q, a))

            logger.info("Extracted %d FAQ pairs from conversation", len(result))
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.error("FAQ extraction failed: %s", e)
            return []
        finally:
            if self._http_client is None:
                await client.aclose()

    def list_entries(
        self,
        category: str | None = None,
        product_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[KBEntry]:
        """List knowledge base entries with optional filtering.

        Args:
            category: Filter by category.
            product_id: Filter by product ID.
            offset: Pagination offset.
            limit: Maximum entries to return.

        Returns:
            Filtered list of KBEntry objects.
        """
        results = self._entries
        if category:
            results = [e for e in results if e.category == category]
        if product_id:
            results = [e for e in results if e.product_id == product_id]
        return results[offset : offset + limit]

    @property
    def entry_count(self) -> int:
        """Return the total number of entries in the knowledge base."""
        return len(self._entries)
