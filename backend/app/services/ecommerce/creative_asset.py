"""Creative asset version management - compare and rollback."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession


class AssetVersion:
    """Represents a single version of a creative asset."""

    def __init__(
        self,
        *,
        version_id: str,
        asset_id: str,
        version_number: int,
        asset_type: str,
        content_url: str,
        thumbnail_url: str = "",
        metadata: Optional[dict[str, Any]] = None,
        created_by: str = "",
        created_at: Optional[datetime] = None,
        is_current: bool = False,
    ):
        self.version_id = version_id
        self.asset_id = asset_id
        self.version_number = version_number
        self.asset_type = asset_type
        self.content_url = content_url
        self.thumbnail_url = thumbnail_url
        self.metadata = metadata or {}
        self.created_by = created_by
        self.created_at = created_at or datetime.utcnow()
        self.is_current = is_current


class AssetDiff:
    """Difference between two asset versions."""

    def __init__(
        self,
        *,
        from_version: int,
        to_version: int,
        changes: list[dict[str, Any]],
        metadata_diff: dict[str, Any],
    ):
        self.from_version = from_version
        self.to_version = to_version
        self.changes = changes
        self.metadata_diff = metadata_diff


class CreativeAssetService:
    """Service for managing creative asset versions with compare and rollback."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_asset(
        self,
        *,
        product_id: UUID,
        asset_type: str,
        content_url: str,
        thumbnail_url: str = "",
        metadata: Optional[dict[str, Any]] = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Create a new asset with its initial version (v1).

        Args:
            product_id: Associated product UUID.
            asset_type: Type of asset (image, video, copy, etc.).
            content_url: URL to the asset content.
            thumbnail_url: URL to thumbnail preview.
            metadata: Additional metadata (dimensions, format, AI params, etc.).
            created_by: Creator identifier.

        Returns:
            Created asset with version information.
        """
        from app.models.creative_asset import (  # type: ignore[import]
            CreativeAsset,
            CreativeAssetVersion,
        )

        # Create the asset record
        asset = CreativeAsset(
            product_id=product_id,
            asset_type=asset_type,
            current_version=1,
            status="active",
            metadata=metadata or {},
        )
        self.db.add(asset)
        await self.db.flush()

        # Create initial version
        version = CreativeAssetVersion(
            asset_id=asset.id,
            version_number=1,
            content_url=content_url,
            thumbnail_url=thumbnail_url,
            metadata=metadata or {},
            created_by=created_by,
            is_current=True,
        )
        self.db.add(version)
        await self.db.flush()

        return self._serialize_asset(asset, version)

    async def add_version(
        self,
        asset_id: UUID,
        *,
        content_url: str,
        thumbnail_url: str = "",
        metadata: Optional[dict[str, Any]] = None,
        created_by: str = "system",
        change_description: str = "",
    ) -> dict[str, Any]:
        """Add a new version to an existing asset.

        The new version becomes the current version.

        Args:
            asset_id: UUID of the asset.
            content_url: URL to the new version content.
            thumbnail_url: Thumbnail URL.
            metadata: Version-specific metadata.
            created_by: Creator identifier.
            change_description: Description of what changed.

        Returns:
            Updated asset with new version info.

        Raises:
            ValueError: If asset not found.
        """
        from app.models.creative_asset import (  # type: ignore[import]
            CreativeAsset,
            CreativeAssetVersion,
        )

        # Get current asset
        stmt = select(CreativeAsset).where(CreativeAsset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")

        # Unset current flag on previous version
        prev_stmt = select(CreativeAssetVersion).where(
            and_(
                CreativeAssetVersion.asset_id == asset_id,
                CreativeAssetVersion.is_current == True,
            )
        )
        prev_result = await self.db.execute(prev_stmt)
        prev_version = prev_result.scalar_one_or_none()
        if prev_version:
            prev_version.is_current = False

        # Create new version
        new_version_number = asset.current_version + 1
        new_version = CreativeAssetVersion(
            asset_id=asset_id,
            version_number=new_version_number,
            content_url=content_url,
            thumbnail_url=thumbnail_url,
            metadata={
                **(metadata or {}),
                "change_description": change_description,
            },
            created_by=created_by,
            is_current=True,
        )
        self.db.add(new_version)

        # Update asset current version
        asset.current_version = new_version_number
        asset.updated_at = datetime.utcnow()

        await self.db.flush()
        return self._serialize_asset(asset, new_version)

    async def get_version_history(
        self, asset_id: UUID
    ) -> list[dict[str, Any]]:
        """Get all versions of an asset ordered by version number.

        Args:
            asset_id: UUID of the asset.

        Returns:
            List of version records.
        """
        from app.models.creative_asset import CreativeAssetVersion  # type: ignore[import]

        stmt = (
            select(CreativeAssetVersion)
            .where(CreativeAssetVersion.asset_id == asset_id)
            .order_by(CreativeAssetVersion.version_number.desc())
        )
        result = await self.db.execute(stmt)
        versions = result.scalars().all()
        return [self._serialize_version(v) for v in versions]

    async def compare_versions(
        self, asset_id: UUID, from_version: int, to_version: int
    ) -> AssetDiff:
        """Compare two versions of an asset.

        Args:
            asset_id: UUID of the asset.
            from_version: Source version number.
            to_version: Target version number.

        Returns:
            AssetDiff describing the differences.

        Raises:
            ValueError: If either version not found.
        """
        from app.models.creative_asset import CreativeAssetVersion  # type: ignore[import]

        # Fetch both versions
        stmt_from = select(CreativeAssetVersion).where(
            and_(
                CreativeAssetVersion.asset_id == asset_id,
                CreativeAssetVersion.version_number == from_version,
            )
        )
        stmt_to = select(CreativeAssetVersion).where(
            and_(
                CreativeAssetVersion.asset_id == asset_id,
                CreativeAssetVersion.version_number == to_version,
            )
        )

        result_from = await self.db.execute(stmt_from)
        result_to = await self.db.execute(stmt_to)

        ver_from = result_from.scalar_one_or_none()
        ver_to = result_to.scalar_one_or_none()

        if ver_from is None:
            raise ValueError(f"Version {from_version} not found for asset {asset_id}")
        if ver_to is None:
            raise ValueError(f"Version {to_version} not found for asset {asset_id}")

        # Compute differences
        changes: list[dict[str, Any]] = []

        if ver_from.content_url != ver_to.content_url:
            changes.append({
                "field": "content_url",
                "from": ver_from.content_url,
                "to": ver_to.content_url,
            })

        if ver_from.thumbnail_url != ver_to.thumbnail_url:
            changes.append({
                "field": "thumbnail_url",
                "from": ver_from.thumbnail_url,
                "to": ver_to.thumbnail_url,
            })

        # Compare metadata
        metadata_diff = self._diff_metadata(
            ver_from.metadata or {}, ver_to.metadata or {}
        )

        return AssetDiff(
            from_version=from_version,
            to_version=to_version,
            changes=changes,
            metadata_diff=metadata_diff,
        )

    async def rollback_to_version(
        self, asset_id: UUID, target_version: int, *, rolled_back_by: str = "system"
    ) -> dict[str, Any]:
        """Rollback an asset to a previous version.

        This creates a new version that is a copy of the target version,
        preserving the version history (non-destructive rollback).

        Args:
            asset_id: UUID of the asset.
            target_version: Version number to rollback to.
            rolled_back_by: Who triggered the rollback.

        Returns:
            The new version (copy of target).

        Raises:
            ValueError: If target version not found.
        """
        from app.models.creative_asset import CreativeAssetVersion  # type: ignore[import]

        # Fetch target version
        stmt = select(CreativeAssetVersion).where(
            and_(
                CreativeAssetVersion.asset_id == asset_id,
                CreativeAssetVersion.version_number == target_version,
            )
        )
        result = await self.db.execute(stmt)
        target = result.scalar_one_or_none()
        if target is None:
            raise ValueError(
                f"Version {target_version} not found for asset {asset_id}"
            )

        # Create a new version that copies the target
        return await self.add_version(
            asset_id,
            content_url=target.content_url,
            thumbnail_url=target.thumbnail_url,
            metadata={
                **(target.metadata or {}),
                "rollback_from_version": target_version,
            },
            created_by=rolled_back_by,
            change_description=f"Rollback to version {target_version}",
        )

    async def delete_asset(self, asset_id: UUID) -> bool:
        """Soft-delete an asset and all its versions.

        Returns:
            True if asset was found and deleted.
        """
        from app.models.creative_asset import CreativeAsset  # type: ignore[import]

        stmt = select(CreativeAsset).where(CreativeAsset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        if asset is None:
            return False

        asset.status = "deleted"
        asset.updated_at = datetime.utcnow()
        await self.db.flush()
        return True

    @staticmethod
    def _diff_metadata(
        meta_from: dict[str, Any], meta_to: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute a simple diff between two metadata dictionaries."""
        diff: dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}

        all_keys = set(meta_from.keys()) | set(meta_to.keys())
        for key in all_keys:
            if key not in meta_from:
                diff["added"][key] = meta_to[key]
            elif key not in meta_to:
                diff["removed"][key] = meta_from[key]
            elif meta_from[key] != meta_to[key]:
                diff["changed"][key] = {
                    "from": meta_from[key],
                    "to": meta_to[key],
                }

        return diff

    @staticmethod
    def _serialize_asset(asset: Any, version: Any) -> dict[str, Any]:
        """Serialize asset with current version info."""
        return {
            "id": str(asset.id),
            "product_id": str(asset.product_id) if asset.product_id else None,
            "asset_type": asset.asset_type,
            "current_version": asset.current_version,
            "status": asset.status,
            "content_url": version.content_url,
            "thumbnail_url": version.thumbnail_url,
            "metadata": asset.metadata,
            "version_metadata": version.metadata,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
            "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        }

    @staticmethod
    def _serialize_version(version: Any) -> dict[str, Any]:
        """Serialize a version record."""
        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "content_url": version.content_url,
            "thumbnail_url": version.thumbnail_url,
            "metadata": version.metadata,
            "created_by": version.created_by,
            "is_current": version.is_current,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
