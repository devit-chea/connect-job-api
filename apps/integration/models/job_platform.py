import uuid

from django.db import models
from django.utils import timezone
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.integration.constants import ConnectorStatus
from apps.integration.utils.crypto_utils import EncryptedTextField


class IntegrationPartner(AbstractBaseModel, AbstractBaseCompany):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.CharField(max_length=100, unique=True)
    partner_tenant_id = models.CharField(max_length=100)  # Stores ERP Company ID
    partner_outbound_key = EncryptedTextField()  # Key_Beta (AES)
    partner_outbound_hash = models.CharField(
        max_length=64, unique=True
    )  # High-performance lookup hash
    partner_inbound_key = EncryptedTextField()  # Key_Alpha (AES)
    erp_domain = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Base URL of the Connect ERP instance (from company.integrate_domain). "
                  "Used by outbound sync services instead of the global CONNECTOR_INTEGRATION_URL setting.",
    )
    status = models.CharField(
        max_length=20,
        choices=ConnectorStatus.CHOICES,
        default=ConnectorStatus.ACTIVE,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrate_partner"


class IntegrationHandshake(AbstractBaseModel, AbstractBaseCompany):
    temporary_code = models.CharField(max_length=100, primary_key=True)
    state = models.CharField(max_length=100)
    code_challenge = models.CharField(max_length=128)
    organization_id = models.CharField(max_length=100, db_index=True)
    redirect_uri = models.URLField(max_length=500,null=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "integrate_handshakes"



class MappingType(models.TextChoices):
    FREE = "free", "Free"      # Direct field-to-field copy, no value translation
    MAPPED = "mapped", "Mapped"  # Has value-level mappings (enums / choice fields)


class IntegrationFieldMapping(AbstractBaseModel):
    """
    Maps one ERP field name to one ConnectJob field name for a given partner.
    Optionally stores a fallback default_value used when the ERP omits the field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(
        IntegrationPartner,
        on_delete=models.CASCADE,
        related_name="field_mappings",
    )
    source_field = models.CharField(max_length=100)   # ConnectJob canonical field name
    target_field = models.CharField(max_length=100)   # ERP field name
    mapping_type = models.CharField(
        max_length=20,
        choices=MappingType.choices,
        default=MappingType.FREE,
    )
    default_value = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrate_field_mapping"
        unique_together = ("partner", "source_field")


class IntegrationValueMapping(AbstractBaseModel):
    """
    Maps one ERP field value to one ConnectJob field value within a field mapping.
    Used for choice/enum fields where both systems use different labels.
    Example: ERP sends "FIN" → ConnectJob expects "Finance & Accounting"
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field_mapping = models.ForeignKey(
        IntegrationFieldMapping,
        on_delete=models.CASCADE,
        related_name="value_mappings",
    )
    source_value = models.CharField(max_length=255)   # ConnectJob value
    target_value = models.CharField(max_length=255)   # ERP value
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrate_value_mapping"
        # One ERP value can only map to ONE ConnectJob value (no ambiguity during
        # transform). Multiple ERP values may share the same ConnectJob value
        # (many-to-one), so we do NOT constrain uniqueness on source_value.
        unique_together = ("field_mapping", "target_value")


class SyncLogType:
    JOB_POST_INBOUND = "job_post_inbound"       # ERP → ConnectJob job post
    PIPELINE_OUTBOUND = "pipeline_outbound"     # ConnectJob → ERP pipeline move
    APPLICANT_OUTBOUND = "applicant_outbound"   # ConnectJob → ERP applicant sync
    PIPELINE_INBOUND = "pipeline_inbound"       # ERP → ConnectJob pipeline update

    CHOICES = (
        (JOB_POST_INBOUND, "Inbound Job Post"),
        (PIPELINE_OUTBOUND, "Outbound Pipeline Sync"),
        (APPLICANT_OUTBOUND, "Outbound Applicant Sync"),
        (PIPELINE_INBOUND, "Inbound Pipeline Update"),
    )


class SyncLogStatus:
    FAILED = "failed"
    RETRYING = "retrying"
    SUCCESS = "success"

    CHOICES = (
        (FAILED, "Failed"),
        (RETRYING, "Retrying"),
        (SUCCESS, "Success"),
    )


class IntegrationSyncLog(AbstractBaseModel):
    """
    Persists every sync failure so operators can review payloads, error messages,
    and trigger manual retries without tailing logs or Celery internals.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(
        IntegrationPartner,
        on_delete=models.CASCADE,
        related_name="sync_logs",
        null=True,
        blank=True,
    )
    sync_type = models.CharField(max_length=30, choices=SyncLogType.CHOICES, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=SyncLogStatus.CHOICES,
        default=SyncLogStatus.FAILED,
        db_index=True,
    )
    # Flexible reference: application_id, job_post_id, ucp_id, etc.
    reference_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    # Full raw payload so failures can be replayed without data loss
    payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True, default="")
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integration_sync_log"
        ordering = ["-created_at"]


class IntegrationUserMapping(AbstractBaseModel, AbstractBaseCompany):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        IntegrationPartner, on_delete=models.CASCADE, related_name="user_mappings"
    )
    local_user_id = models.CharField(max_length=100)
    # Nullable: mapping is created immediately on user creation even before ERP
    # responds with its own user ID. Filled in once ERP confirms the record.
    partner_user_id = models.CharField(max_length=100, null=True, blank=True)
    # Direct link to the specific company membership this ERP identity belongs
    # to. A ConnectJob user (Profile) can hold multiple UserCompanyProfiles —
    # one per company — so local_user_id (== profile_id) alone is ambiguous
    # across companies. Set for recruiter/admin mappings; left null for
    # applicant mappings, since applicants have no UserCompanyProfile.
    user_company_profile = models.ForeignKey(
        "auth_oauth.UserCompanyProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integration_user_mappings",
    )

    class Meta:
        db_table = "integrate_user_mappings"
        unique_together = (
            ("connection", "local_user_id"),
            ("connection", "user_company_profile"),
        )
