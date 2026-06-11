from __future__ import annotations

import uuid
from typing import Any, Optional, Dict
from uuid import UUID

from rest_framework import serializers

from apps.auth_oauth.models.profile_model import Profile, ProfileDocumentModel
from apps.auth_oauth.serializers.user_profile_serializer import UserProfileSerializer

DEFAULT_WEIGHTS = {
    "personal_details": 20.0,
    "work_experience": 35.0,
    "education": 15.0,
    "skills": 15.0,
    "about": 5.0,
    "languages": 5.0,
    "cv": 5.0,
}
RECRUITER_WEIGHTS = {
    "profile_details": 20.0,
    "company_info": 60.0,
    "professional_details": 20.0,
}


def _bool(v):
    return v is not None and str(v).strip() != ""


def _has_any(seq):
    return bool(seq and len(seq) > 0)


def _cv_present_via_document(profile_id: int) -> bool:
    return ProfileDocumentModel.objects.filter(
        profile_id=profile_id,
        document_type=ProfileDocumentModel.DocumentType.CV,
        is_deleted=False,
    ).exists()


class UserProfileService:

    @staticmethod
    def create(data):
        user_profile_serializer = UserProfileSerializer(data=data)
        user_profile_serializer.is_valid(raise_exception=True)
        user_profile_instance = user_profile_serializer.save()
        return user_profile_instance

    @staticmethod
    def update(instance, data, partial=True):
        user_profile_serializer = UserProfileSerializer(data=data, instance=instance, partial=partial)
        user_profile_serializer.is_valid(raise_exception=True)
        user_profile_instance = user_profile_serializer.save()
        return user_profile_instance

    @staticmethod
    def get_by_id(profile_id):
        return Profile.objects.filter(
            id=profile_id,
        ).first()

    @staticmethod
    def to_uuid(value: Any) -> Optional[UUID]:
        if not value:
            return None
        try:
            return value if isinstance(value, UUID) else UUID(str(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def validate_file_id(value):
        if not value:
            return None
        try:
            return uuid.UUID(value)
        except ValueError:
            raise serializers.ValidationError("file_id must be a valid UUID string.")

    @staticmethod
    def collect_files_ids(files):
        if files is None or files == []: # Temp condition prevention.
            return []
    
        file_ids = []
        for i, item in enumerate(files):
            if not isinstance(item, dict) or "file_id" not in item:
                raise serializers.ValidationError({"file_id": "This field is required."})
            try:
                file_ids.append(str(uuid.UUID(str(item["file_id"]))))
            except Exception:
                raise serializers.ValidationError({"file_id": "invalid UUID."})
        return file_ids

    @staticmethod
    def mb_compute_profile_completion(rep) -> dict:
        # Personal Details (20%)
        pd_fields = [
            rep.get("first_name"),
            rep.get("last_name"),
            rep.get("current_position"),
            rep.get("date_of_birth"),
            rep.get("phone_number"),
            rep.get("gender"),
            rep.get("email"),
            rep.get("location") or rep.get("location_name"),
        ]
        filled = sum(1 for v in pd_fields if _bool(v))
        personal_details = (filled / len(pd_fields)) * 20.0

        # Work experience (35%)
        work_exp = 35.0 if _has_any(rep.get("work_experiences")) else 0.0

        # Education (15%)
        education = 15.0 if _has_any(rep.get("educations")) else 0.0

        # Skills (x3) 15% -> up to first 3 skills, 5% each
        skills_count = len(rep.get("skills") or [])
        skills = min(skills_count, 3) * 5.0  # 0..15

        # About (5%)
        about = 5.0 if _bool(rep.get("about_me")) else 0.0

        # Languages (5%)
        languages = 5.0 if _has_any(rep.get("languages")) else 0.0

        #  CV (5%)
        cv_present = _cv_present_via_document(rep.get("id"))
        cv = 5.0 if cv_present else 0.0
        total = personal_details + work_exp + education + skills + about + languages + cv
        total = max(0.0, min(100.0, total))
        return {
            "percent": round(total)
        }

    @staticmethod
    def _compute_applicant(*, profile: Any) -> Dict[str, int]:
        w = DEFAULT_WEIGHTS

        # Personal Details
        pd_values = [
            getattr(profile, "first_name", None),
            getattr(profile, "last_name", None),
            getattr(profile, "current_position", None),
            getattr(profile, "date_of_birth", None),
            getattr(profile, "phone_number", None),
            getattr(profile, "gender", None),
            getattr(profile, "email", None),
            (getattr(profile, "location", None) or getattr(profile, "location_name", None)),
        ]
        filled = sum(1 for v in pd_values if _bool(v))
        personal_details = (filled / len(pd_values)) * w["personal_details"]

        # Work experience (binary)
        work_experience = w["work_experience"] if bool(getattr(profile, "work_experiences_exists", False)) else 0.0

        # Education (binary)
        education = w["education"] if bool(getattr(profile, "educations_exists", False)) else 0.0

        # Skills (count up to 3)
        skills_count = int(getattr(profile, "skills_count", 0) or 0)
        skills = min(skills_count, 3) * (w["skills"] / 3.0)

        about = w["about"] if _bool(getattr(profile, "about_me", "")) else 0.0

        languages = w["languages"] if bool(getattr(profile, "languages_exists", False)) else 0.0
        # CV
        cv = w["cv"] if bool(getattr(profile, "cv_exists", False)) else 0.0

        total = personal_details + work_experience + education + skills + about + languages + cv
        total = max(0.0, min(100.0, total))
        return {"percent": round(total)}

    @staticmethod
    def _compute_recruiter(*, profile: Any, company: Any | None) -> Dict[str, int]:
        w = RECRUITER_WEIGHTS
        # 1) Profile details (20%)
        prof_fields = [
            getattr(profile, "first_name", None),
            getattr(profile, "last_name", None),
            getattr(profile, "phone_number", None),
            getattr(profile, "email", None),
        ]
        prof_details = (sum(1 for v in prof_fields if _bool(v)) / len(prof_fields)) * w["profile_details"]
        # Company info (60%)
        c = company
        company_fields = [
            getattr(c, "name", None),
            getattr(c, "email", None),
            getattr(c, "profile_picture_id", None),
            getattr(c, "address", None),
            getattr(c, "industry", None),
            getattr(c, "company_size", None),
            getattr(c, "profile_picture_id", None),
        ] if c is not None else []
        company_denominator = len(company_fields) if company_fields else 1
        company_info = (sum(1 for v in company_fields if _bool(v)) / company_denominator) * w["company_info"]

        # 3) Professional details (20%)
        professional_fields = [
            getattr(profile, "current_position", None),
            (getattr(profile, "linkedin_profile", None) or getattr(profile, "website", None)),
        ]
        professional = (sum(1 for v in professional_fields if _bool(v)) / len(professional_fields)) * w[
            "professional_details"]

        total = prof_details + company_info + professional
        return {"percent": round(max(0.0, min(100.0, total)))}

    @staticmethod
    def web_compute_profile_completion(*, profile: Any) -> Dict[str, int]:
        ptype = (getattr(profile, "profile_type", "") or "").lower()
        if ptype in {"recruiter", "admin_recruiter"}:
            return UserProfileService._compute_recruiter(profile=profile, company=getattr(profile, "company", None))
        return UserProfileService._compute_applicant(profile=profile)
