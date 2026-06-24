"""Product Upload & Listing service.

Orchestrates the full product listing pipeline: validation, category mapping,
content generation, image upload, SKU creation, and submission to 抖店 API.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import DouyinAPIError, RateLimitExceeded
from app.core.security import sign_request
from app.models.product import (
    CategoryMapping,
    Product,
    ProductSKU,
    ProductStatus,
)

from .content_generator import AIContentGenerator
from .image_processor import ImageProcessor

logger = logging.getLogger(__name__)

# 抖店 Open API base URL
DOUYIN_API_BASE = "https://openapi-fxg.jinritemai.com"

# Batch upload concurrency limit
MAX_CONCURRENT_UPLOADS = 5


@dataclass
class ProductInput:
    """Input data for creating a product listing."""

    name: str
    description: str = ""
    images: list[str] = field(default_factory=list)
    category_id: str | None = None
    skus: list[dict[str, Any]] = field(default_factory=list)
    price: float = 0.0
    market_price: float = 0.0
    stock: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    auto_publish: bool = False


@dataclass
class Category:
    """Category node from the 抖店 category tree."""

    id: str
    name: str
    parent_id: str | None = None
    level: int = 0
    is_leaf: bool = False
    children: list["Category"] = field(default_factory=list)


@dataclass
class CategoryMatch:
    """Result of LLM-based category matching."""

    category_id: str
    category_name: str
    confidence: float
    path: list[str] = field(default_factory=list)


@dataclass
class CategoryTemplate:
    """Required attributes template for a category."""

    category_id: str
    category_name: str
    required_attributes: list[dict[str, Any]] = field(default_factory=list)
    optional_attributes: list[dict[str, Any]] = field(default_factory=list)
    image_requirements: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubmitResult:
    """Result from submitting a product to 抖店."""

    success: bool
    product_id: str | None = None
    error_message: str | None = None
    error_code: int | None = None


@dataclass
class BatchResult:
    """Result of a batch upload operation."""

    total: int
    succeeded: int
    failed: int
    results: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0


class ProductUploadService:
    """Orchestrates product upload and listing operations on 抖店.

    Provides the full pipeline from data validation through API submission,
    reducing per-SKU listing time from ~20 minutes to under 3 minutes.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.content_generator = AIContentGenerator()
        self.image_processor = ImageProcessor()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for 抖店 API calls."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=DOUYIN_API_BASE,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close underlying HTTP clients and resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        await self.content_generator.close()

    # ─────────────────────────────────────────────────────────────────────
    # Core pipeline
    # ─────────────────────────────────────────────────────────────────────

    async def create_product(self, data: ProductInput) -> Product:
        """Full product creation pipeline.

        Steps: validate -> categorize -> generate content -> upload images
        -> create SKUs -> submit to 抖店.

        Args:
            data: Product input data.

        Returns:
            The created Product model instance.

        Raises:
            DouyinAPIError: If any API call to 抖店 fails.
            ValueError: If input validation fails.
        """
        logger.info("Starting product creation pipeline for: %s", data.name)

        # Step 1: Category mapping
        if not data.category_id:
            match = await self.match_category(data.name, data.description)
            data.category_id = match.category_id
            category_name = match.category_name
            logger.info(
                "Auto-matched category: %s (%s) confidence=%.2f",
                match.category_name,
                match.category_id,
                match.confidence,
            )
        else:
            category_name = data.category_id  # Will be resolved below

        # Step 2: Fetch category template for required attributes
        template = await self.fetch_category_template(data.category_id)
        category_name = template.category_name

        # Step 3: Generate optimized content
        if data.keywords:
            keywords = data.keywords
        else:
            keywords = await self.content_generator.extract_seo_keywords(
                category_name, data.name
            )

        title = await self.content_generator.generate_title(
            data.name, category_name, keywords
        )

        product_info = {
            "name": data.name,
            "description": data.description,
            "category": category_name,
            "attributes": str(data.attributes),
        }
        description = await self.content_generator.generate_description(product_info)

        # Check for prohibited words
        prohibited_in_title = self.content_generator.check_prohibited_words(title)
        prohibited_in_desc = self.content_generator.check_prohibited_words(description)
        if prohibited_in_title:
            logger.warning(
                "Prohibited words in title, regenerating: %s", prohibited_in_title
            )
            title = await self.content_generator.generate_title(
                data.name, category_name, keywords
            )

        # Step 4: Upload images
        image_tokens: list[str] = []
        for image_path in data.images:
            # Validate and process image
            validation = self.image_processor.validate_image(image_path)
            if not validation.valid:
                # Try to fix common issues
                if any("dimension" in e.lower() for e in validation.errors):
                    image_path = self.image_processor.resize_image(image_path)
                if any("size" in e.lower() for e in validation.errors):
                    image_path = self.image_processor.compress_image(image_path)

            token = await self.upload_image(image_path)
            image_tokens.append(token)

        # Step 5: Create product record in database
        product = Product(
            name=title,
            category_id=data.category_id,
            category_name=category_name,
            description=description,
            status=ProductStatus.UPLOADING,
            images=image_tokens,
            sku_data={"skus": data.skus},
            price_range=f"{data.price:.2f}" if data.price else None,
        )
        self.db.add(product)
        await self.db.flush()

        # Step 6: Create SKU records
        for sku_data in data.skus:
            sku = ProductSKU(
                product_id=product.id,
                sku_name=sku_data.get("name", data.name),
                attributes=sku_data.get("attributes", {}),
                price=sku_data.get("price", data.price),
                market_price=sku_data.get("market_price", data.market_price),
                stock=sku_data.get("stock", data.stock),
                sku_image_url=sku_data.get("image_url"),
            )
            self.db.add(sku)

        await self.db.flush()

        # Step 7: Submit to 抖店
        result = await self.submit_product(product)
        if result.success:
            product.douyin_product_id = result.product_id
            product.status = ProductStatus.UNDER_REVIEW
            product.listing_submitted_at = datetime.utcnow()
            logger.info(
                "Product submitted successfully: douyin_id=%s", result.product_id
            )
        else:
            product.status = ProductStatus.REJECTED
            logger.error(
                "Product submission failed: %s (code=%s)",
                result.error_message,
                result.error_code,
            )

        await self.db.flush()
        return product

    async def batch_upload(self, products: list[ProductInput]) -> BatchResult:
        """Upload multiple products with concurrency throttling.

        Processes up to MAX_CONCURRENT_UPLOADS products simultaneously.

        Args:
            products: List of product input data.

        Returns:
            BatchResult with success/failure counts and details.
        """
        start_time = asyncio.get_event_loop().time()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
        results: list[dict[str, Any]] = []

        async def _upload_single(idx: int, data: ProductInput) -> dict[str, Any]:
            async with semaphore:
                try:
                    product = await self.create_product(data)
                    return {
                        "index": idx,
                        "success": True,
                        "product_id": str(product.id),
                        "douyin_product_id": product.douyin_product_id,
                        "name": data.name,
                    }
                except Exception as e:
                    logger.error(
                        "Batch upload item %d failed: %s", idx, str(e)
                    )
                    return {
                        "index": idx,
                        "success": False,
                        "name": data.name,
                        "error": str(e),
                    }

        tasks = [
            _upload_single(i, product_data)
            for i, product_data in enumerate(products)
        ]
        results = await asyncio.gather(*tasks)

        elapsed = asyncio.get_event_loop().time() - start_time
        succeeded = sum(1 for r in results if r["success"])

        batch_result = BatchResult(
            total=len(products),
            succeeded=succeeded,
            failed=len(products) - succeeded,
            results=results,
            duration_seconds=elapsed,
        )

        logger.info(
            "Batch upload completed: %d/%d succeeded in %.1fs",
            succeeded,
            len(products),
            elapsed,
        )
        return batch_result

    # ─────────────────────────────────────────────────────────────────────
    # Category operations
    # ─────────────────────────────────────────────────────────────────────

    async def get_category_tree(self) -> list[Category]:
        """Fetch the full category tree from 抖店 API.

        Calls: product.categoryTree

        Returns:
            List of top-level Category nodes with nested children.

        Raises:
            DouyinAPIError: If the API request fails.
        """
        path = "/product/categoryTree"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
        }

        sign_headers = sign_request("GET", path, params)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.get(path, params=params)

        if response.status_code != 200:
            raise DouyinAPIError(
                message="Failed to fetch category tree",
                status_code=response.status_code,
                response_body=response.text,
            )

        data = response.json()
        if data.get("err_no") != 0:
            raise DouyinAPIError(
                message=f"Category tree API error: {data.get('message', '')}",
                status_code=response.status_code,
                response_body=response.text,
            )

        categories = self._parse_category_tree(data.get("data", {}).get("category_list", []))
        return categories

    def _parse_category_tree(
        self, raw_list: list[dict], level: int = 0
    ) -> list[Category]:
        """Recursively parse the raw category tree response."""
        categories: list[Category] = []
        for item in raw_list:
            category = Category(
                id=str(item.get("id", "")),
                name=item.get("name", ""),
                parent_id=str(item.get("parent_id", "")) or None,
                level=level,
                is_leaf=item.get("is_leaf", False),
                children=self._parse_category_tree(
                    item.get("children", []), level + 1
                ),
            )
            categories.append(category)
        return categories

    async def match_category(
        self, product_name: str, description: str
    ) -> CategoryMatch:
        """Use LLM to suggest the best category match for a product.

        Args:
            product_name: Name of the product.
            description: Product description for context.

        Returns:
            CategoryMatch with the suggested category and confidence score.
        """
        # Fetch available categories for context
        categories = await self.get_category_tree()
        category_text = self._flatten_categories_for_prompt(categories)

        prompt = (
            "根据以下商品信息，从类目列表中选择最合适的叶子类目。\n\n"
            f"商品名称：{product_name}\n"
            f"商品描述：{description}\n\n"
            f"可选类目：\n{category_text}\n\n"
            "请返回JSON格式：\n"
            '{"category_id": "xxx", "category_name": "xxx", "confidence": 0.95, '
            '"path": ["一级类目", "二级类目", "三级类目"]}'
        )

        import json

        result_text = await self.content_generator._call_llm(prompt)

        try:
            # Parse LLM response as JSON
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(result_text)
            return CategoryMatch(
                category_id=str(result.get("category_id", "")),
                category_name=result.get("category_name", ""),
                confidence=float(result.get("confidence", 0.0)),
                path=result.get("path", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse category match response: %s", e)
            # Fallback: return empty match
            return CategoryMatch(
                category_id="",
                category_name="",
                confidence=0.0,
            )

    def _flatten_categories_for_prompt(
        self, categories: list[Category], prefix: str = ""
    ) -> str:
        """Flatten category tree into a text list for LLM prompt."""
        lines: list[str] = []
        for cat in categories:
            path = f"{prefix}/{cat.name}" if prefix else cat.name
            if cat.is_leaf:
                lines.append(f"- {path} (ID: {cat.id})")
            if cat.children:
                lines.extend(
                    self._flatten_categories_for_prompt(cat.children, path).split("\n")
                )
        return "\n".join(lines)

    async def fetch_category_template(self, category_id: str) -> CategoryTemplate:
        """Fetch required attributes template for a category.

        Calls: product.template.get

        Args:
            category_id: The leaf category ID.

        Returns:
            CategoryTemplate with required and optional attributes.

        Raises:
            DouyinAPIError: If the API request fails.
        """
        path = "/product/template/get"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
            "category_id": category_id,
        }

        sign_headers = sign_request("GET", path, params)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.get(path, params=params)

        if response.status_code != 200:
            raise DouyinAPIError(
                message=f"Failed to fetch category template for {category_id}",
                status_code=response.status_code,
                response_body=response.text,
            )

        data = response.json()
        if data.get("err_no") != 0:
            raise DouyinAPIError(
                message=f"Template API error: {data.get('message', '')}",
                status_code=response.status_code,
                response_body=response.text,
            )

        template_data = data.get("data", {})
        return CategoryTemplate(
            category_id=category_id,
            category_name=template_data.get("category_name", ""),
            required_attributes=template_data.get("required_attributes", []),
            optional_attributes=template_data.get("optional_attributes", []),
            image_requirements=template_data.get("image_requirements", {}),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Image upload
    # ─────────────────────────────────────────────────────────────────────

    async def upload_image(self, image_path: str) -> str:
        """Upload an image to 抖店 via material.upload API.

        Args:
            image_path: Local path to the image file.

        Returns:
            The material_token string for use in product creation.

        Raises:
            DouyinAPIError: If the upload fails.
            FileNotFoundError: If the image file does not exist.
        """
        import os

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        path = "/material/upload"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
        }

        sign_headers = sign_request("POST", path, params)
        params.update(sign_headers)

        client = await self._get_client()

        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/jpeg")}
            response = await client.post(path, params=params, files=files)

        if response.status_code != 200:
            raise DouyinAPIError(
                message=f"Image upload failed for {image_path}",
                status_code=response.status_code,
                response_body=response.text,
            )

        data = response.json()
        if data.get("err_no") != 0:
            raise DouyinAPIError(
                message=f"Image upload error: {data.get('message', '')}",
                status_code=response.status_code,
                response_body=response.text,
            )

        material_token = data.get("data", {}).get("material_token", "")
        if not material_token:
            raise DouyinAPIError(
                message="No material_token in upload response",
                status_code=response.status_code,
                response_body=response.text,
            )

        logger.info("Uploaded image '%s' -> token=%s", image_path, material_token[:20])
        return material_token

    # ─────────────────────────────────────────────────────────────────────
    # Product submission and lifecycle
    # ─────────────────────────────────────────────────────────────────────

    async def submit_product(self, product: Product) -> SubmitResult:
        """Submit a product to 抖店 for review.

        Calls: product.addV2

        Args:
            product: The Product model instance with all required data.

        Returns:
            SubmitResult indicating success or failure.

        Raises:
            DouyinAPIError: If the API call encounters an unexpected error.
        """
        path = "/product/addV2"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
        }

        # Build the product payload per 抖店 API spec
        payload = {
            "product": {
                "name": product.name,
                "category_id": int(product.category_id),
                "description": product.description,
                "pic": product.images,
                "pay_type": 0,  # Online payment
                "recommend_remark": "",
            },
            "skus": [],
        }

        # Add SKU data
        sku_list = product.sku_data.get("skus", [])
        for sku in sku_list:
            payload["skus"].append(
                {
                    "sku_name": sku.get("name", product.name),
                    "price": int(sku.get("price", 0) * 100),  # Convert to cents
                    "market_price": int(sku.get("market_price", 0) * 100),
                    "stock_num": sku.get("stock", 0),
                    "sku_attributes": sku.get("attributes", {}),
                }
            )

        import json

        body = json.dumps(payload, ensure_ascii=False)
        sign_headers = sign_request("POST", path, params, body=body)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.post(path, params=params, json=payload)

        if response.status_code != 200:
            return SubmitResult(
                success=False,
                error_message=f"HTTP {response.status_code}: {response.text[:200]}",
                error_code=response.status_code,
            )

        data = response.json()
        if data.get("err_no") != 0:
            return SubmitResult(
                success=False,
                error_message=data.get("message", "Unknown error"),
                error_code=data.get("err_no"),
            )

        product_id = str(data.get("data", {}).get("product_id", ""))
        return SubmitResult(success=True, product_id=product_id)

    async def publish_product(self, product_id: str) -> bool:
        """Publish a product (set online) after review approval.

        Calls: product.online

        Args:
            product_id: The 抖店 product ID.

        Returns:
            True if successfully published, False otherwise.
        """
        path = "/product/online"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
            "product_id": product_id,
        }

        sign_headers = sign_request("POST", path, params)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.post(path, params=params)

        if response.status_code != 200:
            logger.error(
                "Publish failed for product %s: HTTP %d",
                product_id,
                response.status_code,
            )
            return False

        data = response.json()
        if data.get("err_no") != 0:
            logger.error(
                "Publish API error for product %s: %s",
                product_id,
                data.get("message", ""),
            )
            return False

        logger.info("Product %s published successfully", product_id)
        return True

    async def check_product_status(self, product_id: str) -> ProductStatus:
        """Check the review/listing status of a product.

        Polls the 抖店 API for the current product status.

        Args:
            product_id: The 抖店 product ID.

        Returns:
            Current ProductStatus enum value.

        Raises:
            DouyinAPIError: If the status check fails.
        """
        path = "/product/detail"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
            "product_id": product_id,
        }

        sign_headers = sign_request("GET", path, params)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.get(path, params=params)

        if response.status_code != 200:
            raise DouyinAPIError(
                message=f"Status check failed for product {product_id}",
                status_code=response.status_code,
                response_body=response.text,
            )

        data = response.json()
        if data.get("err_no") != 0:
            raise DouyinAPIError(
                message=f"Status API error: {data.get('message', '')}",
                status_code=response.status_code,
                response_body=response.text,
            )

        # Map 抖店 status codes to our enum
        status_code = data.get("data", {}).get("status", 0)
        status_map = {
            0: ProductStatus.DRAFT,
            1: ProductStatus.UPLOADING,
            2: ProductStatus.UNDER_REVIEW,
            3: ProductStatus.APPROVED,
            4: ProductStatus.REJECTED,
            5: ProductStatus.ONLINE,
            6: ProductStatus.OFFLINE,
        }

        return status_map.get(status_code, ProductStatus.DRAFT)

    async def take_offline(self, product_id: str) -> bool:
        """Take a product offline.

        Calls: product.offline

        Args:
            product_id: The 抖店 product ID.

        Returns:
            True if successfully taken offline, False otherwise.
        """
        path = "/product/offline"
        params = {
            "access_token": settings.DOUYIN_ACCESS_TOKEN,
            "product_id": product_id,
        }

        sign_headers = sign_request("POST", path, params)
        params.update(sign_headers)

        client = await self._get_client()
        response = await client.post(path, params=params)

        if response.status_code != 200:
            logger.error(
                "Offline failed for product %s: HTTP %d",
                product_id,
                response.status_code,
            )
            return False

        data = response.json()
        if data.get("err_no") != 0:
            logger.error(
                "Offline API error for product %s: %s",
                product_id,
                data.get("message", ""),
            )
            return False

        logger.info("Product %s taken offline successfully", product_id)
        return True
