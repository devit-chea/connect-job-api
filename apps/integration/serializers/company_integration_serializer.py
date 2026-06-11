from rest_framework import serializers

from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.constants.base_constants import Status
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField

from apps.base.serializers.country_serializer import CountryInfoSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.utils.file_management_util import resolve_profile_images


class CompanyIntegrationInboundSerializer(serializers.Serializer):
    """
    Validates and normalises the payload sent by an external platform
    when it wants to register/sync its company into our system.

    Required fields: name, integrate_domain
    Everything else is optional — we merge with any existing record.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    name = serializers.CharField(max_length=255)
    integrate_domain = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=255, required=False, allow_null=True)

    # ── Contact ───────────────────────────────────────────────────────────────
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=255)
    linkedin_email = serializers.EmailField(
        required=False, allow_null=True, allow_blank=True
    )

    # ── Address ───────────────────────────────────────────────────────────────
    street = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    address = serializers.CharField()
    city_name = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    postal_code = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )

    # ── FK lookups (accept PK or leave null) ─────────────────────────────────
    city = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    country = PresentablePrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        presentation_serializer=CountryInfoSerializer,
        required=False,
        allow_null=True,
    )

    # ── Profile ───────────────────────────────────────────────────────────────
    description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    about_me = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry = serializers.CharField()
    company_size = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    found_date = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    logo_description = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )

    # ── Media IDs (stored as char references, e.g. CDN asset IDs) ────────────
    profile_picture_id = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    cover_picture_id = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )

    def validate_integrate_domain(self, value):
        """Normalise to lowercase, strip trailing slash."""
        return value.lower().rstrip("/")


    def validate_country_id(self, value):
        if value is not None and not Country.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                f"Country with id={value} does not exist."
            )
        return value

    def validate(self, attrs):
        """
        Prevent a domain collision: two different DB companies cannot share
        the same integrate_domain.  We allow the *same* company to re-sync.
        """
        domain = attrs["integrate_domain"]
        instance = self.context.get("instance")  # set by the service on update
        qs = Company.objects.filter(integrate_domain=domain, is_integrate=True)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"integrate_domain": f"Domain '{domain}' is already registered."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["status"] = Status.APPROVED
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(resolve_profile_images(instance, self.context))
        return data


# ── Response serializers ───────────────────────────────────────────────────────


class CompanyIntegrationSummarySerializer(serializers.ModelSerializer):
    """Lightweight read serializer returned after register/sync."""

    country_name = serializers.SerializerMethodField()
    city_name_resolved = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "website",
            "integrate_domain",
            "is_integrate",
            "code",
            "status",
            "access_type",
            "entry_type",
            "industry",
            "company_size",
            "country_id",
            "country_name",
            "city_id",
            "city_name",
            "city_name_resolved",
            "latitude",
            "longitude",
        ]

    def get_country_name(self, obj):
        return obj.country.name if obj.country_id else None

    def get_city_name_resolved(self, obj):
        if obj.city_id:
            return obj.city.name
        return obj.city_name  # fallback to free-text city_name


class CompanyIntegrationDetailSerializer(CompanyIntegrationSummarySerializer):
    """Full read serializer for GET /integrations/<id>/."""

    class Meta(CompanyIntegrationSummarySerializer.Meta):
        fields = CompanyIntegrationSummarySerializer.Meta.fields + [
            "phone_number",
            "street",
            "address",
            "postal_code",
            "description",
            "about_me",
            "found_date",
            "logo_description",
            "profile_picture_id",
            "cover_picture_id",
            "linkedin_email",
            "is_active",
            "is_agree_policy",
            "parent_id",
        ]
