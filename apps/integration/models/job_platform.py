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



class IntegrationUserMapping(AbstractBaseModel, AbstractBaseCompany):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        IntegrationPartner, on_delete=models.CASCADE, related_name="user_mappings"
    )
    local_user_id = models.CharField(max_length=100)
    partner_user_id = models.CharField(max_length=100)

    class Meta:
        db_table = "integrate_user_mappings"
        unique_together = ("connection", "local_user_id")
