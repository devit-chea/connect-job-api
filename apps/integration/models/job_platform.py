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
    status = models.CharField(
        max_length=20,
        choices=ConnectorStatus.CHOICES,
        default=ConnectorStatus.ACTIVE,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=timezone.now)

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


class IntegrationUserMapping(AbstractBaseModel, AbstractBaseCompany):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        IntegrationPartner, on_delete=models.CASCADE, related_name="user_mappings"
    )
    local_user_id = models.CharField(max_length=100)
    # Nullable: mapping is created immediately on user creation even before ERP
    # responds with its own user ID. Filled in once ERP confirms the record.
    partner_user_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "integrate_user_mappings"
        unique_together = ("connection", "local_user_id")
