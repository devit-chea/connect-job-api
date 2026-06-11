from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional, TypedDict, Any
from uuid import UUID

from rest_framework import serializers as drf_serializers
from wdg_storage.service import FileStorageService

logger = logging.getLogger(__name__)

# Monkey-patch the  package wdg_storage to improve performance
_s3_engine_cache: dict = {}
_original_get_s3_engine = FileStorageService._get_s3_engine


def _cached_get_s3_engine(engine_type: str):
    if engine_type not in _s3_engine_cache:
        _s3_engine_cache[engine_type] = _original_get_s3_engine(engine_type)
    return _s3_engine_cache[engine_type]


FileStorageService._get_s3_engine = staticmethod(_cached_get_s3_engine)


class MinFile(TypedDict):
    file_path: Optional[str]
    file_type: Optional[str]
    file_name: Optional[str]
    file_size: Optional[str]
    original_file_name: Optional[str]


def _to_uuid(value: Any) -> Optional[UUID]:
    if not value:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError):
        return None


class FileURLService:
    """Fetch minimal file info keyed by FileStorageModel.file_id."""

    @classmethod
    def map_by_file_ids(
        cls,
        file_ids: Iterable[Optional[UUID]],
        presigned: bool = True,
    ) -> Dict[UUID, MinFile]:
        ids = [_to_uuid(i) for i in file_ids if i]
        if not ids:
            return {}

        try:
            results = FileStorageService.download_file_url(
                file_id=ids,
                presigned=presigned,
            )
        except ValueError:
            # No matching files found (deleted or missing)
            return {}
        except Exception:
            logger.exception(
                "Failed to fetch file URLs",
                extra={"file_ids": [str(i) for i in ids]},
            )
            return {}

        return {
            _to_uuid(r["file_id"]): {
                "file_path": r.get("url"),
                "file_type": r.get("file_type"),
                "file_name": r.get("stored_filename"),
                "file_size": round(r["file_size"] * 1024 * 1024) if r.get("file_size") is not None else None,
                "original_file_name": r.get("original_filename"),
            }
            for r in results
            if r.get("file_id")
        }

    @classmethod
    def present_profile_images(
        cls,
        prof,
        presigned: bool = True,
        *,
        include_cover: bool = True,
    ) -> Dict[str, Optional[MinFile]]:
        """
        Returns:
        {
          "profile_image": {"file_path": ..., "file_type": ...} | None,
          "cover_image":   {"file_path": ..., "file_type": ...} | None
        }
        """
        profile_uuid = _to_uuid(getattr(prof, "profile_picture_id", None))
        cover_uuid = _to_uuid(getattr(prof, "cover_picture_id", None)) if include_cover else None
        meta_by_id = cls.map_by_file_ids(
            filter(None, (profile_uuid, cover_uuid)),
            presigned=presigned,
        )
        return {
            "profile_image": meta_by_id.get(profile_uuid) if profile_uuid else None,
            "cover_image": meta_by_id.get(cover_uuid) if cover_uuid else None,
        }

class ImageListSerializer(drf_serializers.ListSerializer):
    """
    Resolves all profile/cover image URLs in a single DB query for the whole list,
    then exposes the result map via child serializer context (_file_url_map).
    """

    def to_representation(self, data):
        all_ids = []
        for instance in data:
            pid = getattr(instance, "profile_picture_id", None)
            cid = getattr(instance, "cover_picture_id", None)
            if pid:
                all_ids.append(pid)
            if cid:
                all_ids.append(cid)

        if all_ids:
            self.child.context["_file_url_map"] = FileURLService.map_by_file_ids(all_ids)

        return super().to_representation(data)

class ApplicationProfileImageListSerializer(drf_serializers.ListSerializer):

    def to_representation(self, data):
        all_ids = []
        for instance in data:
            profile = getattr(instance, "profile", None)
            if profile:
                pid = getattr(profile, "profile_picture_id", None)
                if pid:
                    all_ids.append(pid)

        if all_ids:
            self.child.context["_file_url_map"] = FileURLService.map_by_file_ids(all_ids)

        return super().to_representation(data)

def resolve_profile_images(instance, context: dict, include_cover: bool = True) -> dict:
    """
    Returns {"profile_image_url": ..., "cover_image_url": ...}.
    Reads from _file_url_map in context when available (set by ProfileImageListSerializer
    on list endpoints) to avoid per-item DB queries. Falls back to present_profile_images
    for detail endpoints.
    """
    file_map = context.get("_file_url_map")
    if file_map is not None:
        profile_uuid = _to_uuid(getattr(instance, "profile_picture_id", None))
        cover_uuid = _to_uuid(getattr(instance, "cover_picture_id", None)) if include_cover else None
        return {
            "profile_image_url": (file_map.get(profile_uuid) or {}).get("file_path"),
            "cover_image_url": (file_map.get(cover_uuid) or {}).get("file_path") if include_cover else None,
        }
    presentation = FileURLService.present_profile_images(instance, include_cover=include_cover)
    return {
        "profile_image_url": (presentation.get("profile_image") or {}).get("file_path"),
        "cover_image_url": (presentation.get("cover_image") or {}).get("file_path"),
    }