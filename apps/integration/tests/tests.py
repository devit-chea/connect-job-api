"""
Integration app test suite.

Coverage:
  1. CryptoUtilsTests          — AES-256-GCM encrypt/decrypt, SHA-256 helpers
  2. TransformErpPayloadTests  — free, mapped, fallback-to-default, fallback-to-raw,
                                  omitted-field default, unmapped key, inactive mapping
  3. SeedDefaultMappingsTests  — count, idempotency
  4. ConnectorKeyAuthTests     — X-CONNECTOR-KEY missing/wrong/valid on disconnect + publish
  5. PKCEHandshakeTests        — initialize auth guard, exchange bad verifier,
                                  exchange expired, exchange happy path (ERP mocked)
"""
import base64
from datetime import timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.base.models.company_model import Company
from apps.integration.constants import (
    ConnectorStatus,
    DEFAULT_CATEGORY_VALUE_MAPPINGS,
    DEFAULT_FIELD_MAPPINGS,
)
from apps.integration.models.job_platform import (
    IntegrationFieldMapping,
    IntegrationHandshake,
    IntegrationPartner,
    IntegrationValueMapping,
    MappingType,
)
from apps.integration.utils.crypto_utils import (
    base64url_encode_sha256,
    decrypt_aes_256_gcm,
    encrypt_aes_256_gcm,
    hash_sha256,
)
from apps.integration.utils.mapping_utils import seed_default_field_mappings, transform_erp_payload

# Deterministic 32-byte key (b'\xab' × 32, base64url-encoded)
TEST_KEY = base64.urlsafe_b64encode(b"\xab" * 32).decode()

INTEGRATION_SETTINGS = dict(
    CONNECTOR_INTEGRATION_KEY=TEST_KEY,
    CONNECTOR_INTEGRATION_URL="http://erp.test",
    ELASTICSEARCH_DSL_AUTOSYNC=False,
)

# Patches that prevent any ES network call during tests.
# CompanyDocument is imported lazily inside signal functions so we patch at source.
_ES_PATCHES = [
    "apps.elasticsearch_app.search.global_search_document.CompanyDocument.update",
    "apps.integration.services.company_integration_service._es_sync_company",
]


class _ESMockMixin:
    """Mixin that disables all ES network calls for the lifetime of the test class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._es_patchers = [patch(target, MagicMock()) for target in _ES_PATCHES]
        for p in cls._es_patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls._es_patchers:
            p.stop()
        super().tearDownClass()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_company(name="Test Corp"):
    return Company.objects.create(name=name)


def make_partner(company, key_beta="outbound_key_beta", status=ConnectorStatus.ACTIVE):
    return IntegrationPartner.objects.create(
        organization_id=str(company.id),
        partner_tenant_id="ERP-TENANT-001",
        partner_outbound_key=key_beta,
        partner_outbound_hash=hash_sha256(key_beta),
        partner_inbound_key="inbound_key_alpha",
        status=status,
    )


def make_handshake(organization_id, code_verifier, expires_in_seconds=600):
    code_challenge = base64url_encode_sha256(code_verifier)
    temporary_code = "tmp_testcode_abc"
    state = "state_teststate_xyz"
    return IntegrationHandshake.objects.create(
        temporary_code=temporary_code,
        state=state,
        code_challenge=code_challenge,
        organization_id=organization_id,
        redirect_uri="http://web.test/integration/callback?state=" + state,
        expires_at=timezone.now() + timedelta(seconds=expires_in_seconds),
    ), temporary_code, state


# ─────────────────────────────────────────────────────────────────────────────
# 1. Crypto utilities
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**INTEGRATION_SETTINGS)
class CryptoUtilsTests(_ESMockMixin, TestCase):

    def test_sha256_is_deterministic(self):
        self.assertEqual(hash_sha256("hello"), hash_sha256("hello"))

    def test_sha256_different_inputs_differ(self):
        self.assertNotEqual(hash_sha256("a"), hash_sha256("b"))

    def test_sha256_is_64_hex_chars(self):
        self.assertEqual(len(hash_sha256("anything")), 64)

    def test_base64url_sha256_has_no_padding(self):
        challenge = base64url_encode_sha256("some-verifier-value")
        self.assertNotIn("=", challenge)

    def test_base64url_sha256_uses_url_safe_alphabet(self):
        challenge = base64url_encode_sha256("some-verifier-value")
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-secret-api-key"
        self.assertEqual(decrypt_aes_256_gcm(encrypt_aes_256_gcm(plaintext)), plaintext)

    def test_encrypt_empty_returns_empty(self):
        self.assertEqual(encrypt_aes_256_gcm(""), "")

    def test_decrypt_empty_returns_empty(self):
        self.assertEqual(decrypt_aes_256_gcm(""), "")

    def test_encryption_nonce_is_random(self):
        c1 = encrypt_aes_256_gcm("same")
        c2 = encrypt_aes_256_gcm("same")
        self.assertNotEqual(c1, c2)

    def test_encrypted_field_transparent_on_partner(self):
        company = make_company()
        partner = make_partner(company, key_beta="plain_text_key")
        partner.refresh_from_db()
        self.assertEqual(partner.partner_outbound_key, "plain_text_key")
        self.assertEqual(partner.partner_inbound_key, "inbound_key_alpha")


# ─────────────────────────────────────────────────────────────────────────────
# 2. transform_erp_payload
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**INTEGRATION_SETTINGS)
class TransformErpPayloadTests(_ESMockMixin, TestCase):

    def setUp(self):
        self.company = make_company()
        self.partner = make_partner(self.company)

    def _mapping(self, source, target, mtype=MappingType.FREE, default=None, active=True):
        return IntegrationFieldMapping.objects.create(
            partner=self.partner,
            source_field=source,
            target_field=target,
            mapping_type=mtype,
            default_value=default,
            is_active=active,
        )

    def _transform(self, erp_payload):
        return transform_erp_payload(str(self.partner.id), erp_payload)

    # ── Free field (direct rename) ────────────────────────────────────────────

    def test_free_field_renames_erp_key(self):
        self._mapping("title", "position")
        self.assertEqual(self._transform({"position": "Senior Dev"})["title"], "Senior Dev")

    def test_free_field_preserves_value_unchanged(self):
        self._mapping("job_code", "job_code")
        self.assertEqual(self._transform({"job_code": "JOB-001"})["job_code"], "JOB-001")

    # ── Mapped field (value translation) ─────────────────────────────────────

    def test_mapped_field_translates_value(self):
        fm = self._mapping("category", "job_category", MappingType.MAPPED, "Other")
        IntegrationValueMapping.objects.create(
            field_mapping=fm,
            source_value="Finance & Accounting",
            target_value="Finance",
        )
        self.assertEqual(self._transform({"job_category": "Finance"})["category"], "Finance & Accounting")

    def test_mapped_field_falls_back_to_default_when_no_value_match(self):
        self._mapping("category", "job_category", MappingType.MAPPED, "Other")
        self.assertEqual(self._transform({"job_category": "UnknownCategory"})["category"], "Other")

    def test_mapped_field_keeps_raw_erp_value_when_no_match_and_no_default(self):
        self._mapping("category", "job_category", MappingType.MAPPED, None)
        self.assertEqual(self._transform({"job_category": "RawValue"})["category"], "RawValue")

    def test_many_erp_values_translate_to_same_connectjob_value(self):
        fm = self._mapping("category", "job_category", MappingType.MAPPED, "Other")
        IntegrationValueMapping.objects.create(field_mapping=fm, source_value="Finance & Accounting", target_value="Finance")
        IntegrationValueMapping.objects.create(field_mapping=fm, source_value="Finance & Accounting", target_value="Tax")
        r1 = self._transform({"job_category": "Finance"})
        r2 = self._transform({"job_category": "Tax"})
        self.assertEqual(r1["category"], "Finance & Accounting")
        self.assertEqual(r2["category"], "Finance & Accounting")

    # ── Defaults for omitted ERP fields ──────────────────────────────────────

    def test_omitted_erp_field_gets_default_value(self):
        self._mapping("salary_type", "salary_type", default="NEGOTIABLE")
        self.assertEqual(self._transform({})["salary_type"], "NEGOTIABLE")

    def test_omitted_erp_field_absent_from_result_when_no_default(self):
        self._mapping("title", "position", default=None)
        self.assertNotIn("title", self._transform({}))

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_unmapped_erp_key_is_skipped(self):
        self._mapping("title", "position")
        result = self._transform({"position": "Dev", "unknown_key": "ignored"})
        self.assertNotIn("unknown_key", result)

    def test_inactive_mapping_is_ignored(self):
        self._mapping("title", "position", active=False)
        self.assertNotIn("title", self._transform({"position": "Dev"}))

    def test_empty_payload_only_yields_defaults(self):
        self._mapping("hire_no", "no_of_positions", default="1")
        self._mapping("title", "position", default=None)
        result = self._transform({})
        self.assertEqual(result.get("hire_no"), "1")
        self.assertNotIn("title", result)


# ─────────────────────────────────────────────────────────────────────────────
# 3. seed_default_field_mappings
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**INTEGRATION_SETTINGS)
class SeedDefaultMappingsTests(_ESMockMixin, TestCase):

    def setUp(self):
        self.company = make_company()
        self.partner = make_partner(self.company)

    def test_seeds_correct_number_of_field_mappings(self):
        seed_default_field_mappings(self.partner)
        count = IntegrationFieldMapping.objects.filter(partner=self.partner).count()
        self.assertEqual(count, len(DEFAULT_FIELD_MAPPINGS))

    def test_seeds_correct_number_of_category_value_mappings(self):
        seed_default_field_mappings(self.partner)
        category_fm = IntegrationFieldMapping.objects.get(
            partner=self.partner, source_field="category"
        )
        count = IntegrationValueMapping.objects.filter(field_mapping=category_fm).count()
        self.assertEqual(count, len(DEFAULT_CATEGORY_VALUE_MAPPINGS))

    def test_seeding_is_idempotent(self):
        seed_default_field_mappings(self.partner)
        seed_default_field_mappings(self.partner)
        fm_count = IntegrationFieldMapping.objects.filter(partner=self.partner).count()
        category_fm = IntegrationFieldMapping.objects.get(
            partner=self.partner, source_field="category"
        )
        vm_count = IntegrationValueMapping.objects.filter(field_mapping=category_fm).count()
        self.assertEqual(fm_count, len(DEFAULT_FIELD_MAPPINGS))
        self.assertEqual(vm_count, len(DEFAULT_CATEGORY_VALUE_MAPPINGS))

    def test_existing_custom_mapping_is_not_overwritten(self):
        IntegrationFieldMapping.objects.create(
            partner=self.partner,
            source_field="title",
            target_field="custom_position_field",
            is_active=True,
        )
        seed_default_field_mappings(self.partner)
        fm = IntegrationFieldMapping.objects.get(partner=self.partner, source_field="title")
        self.assertEqual(fm.target_field, "custom_position_field")

    def test_category_mapping_has_mapped_type(self):
        seed_default_field_mappings(self.partner)
        fm = IntegrationFieldMapping.objects.get(partner=self.partner, source_field="category")
        self.assertEqual(fm.mapping_type, MappingType.MAPPED)

    def test_category_mapping_has_other_as_default(self):
        seed_default_field_mappings(self.partner)
        fm = IntegrationFieldMapping.objects.get(partner=self.partner, source_field="category")
        self.assertEqual(fm.default_value, "Other")


# ─────────────────────────────────────────────────────────────────────────────
# 4. X-CONNECTOR-KEY auth guard
# ─────────────────────────────────────────────────────────────────────────────

DISCONNECT_URL = "/api/v1/integration/disconnect"
PUBLISH_URL = "/api/v1/integration/jobs/publish"


@override_settings(**INTEGRATION_SETTINGS)
class ConnectorKeyAuthTests(_ESMockMixin, APITestCase):

    def setUp(self):
        self.company = make_company()
        self.key_beta = "test_outbound_key_beta"
        self.partner = make_partner(self.company, key_beta=self.key_beta)

    # ── POST /disconnect ──────────────────────────────────────────────────────

    def test_disconnect_missing_key_returns_401(self):
        response = self.client.post(DISCONNECT_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_disconnect_wrong_key_returns_403(self):
        response = self.client.post(DISCONNECT_URL, HTTP_X_CONNECTOR_KEY="wrong-key")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disconnect_valid_key_disconnects_partner(self):
        response = self.client.post(DISCONNECT_URL, HTTP_X_CONNECTOR_KEY=self.key_beta)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.status, ConnectorStatus.DISCONNECTED)

    def test_disconnect_valid_key_on_already_disconnected_partner_returns_403(self):
        self.partner.status = ConnectorStatus.DISCONNECTED
        self.partner.save(update_fields=["status"])
        response = self.client.post(DISCONNECT_URL, HTTP_X_CONNECTOR_KEY=self.key_beta)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── POST /jobs/publish ────────────────────────────────────────────────────

    def test_publish_missing_key_returns_401(self):
        response = self.client.post(PUBLISH_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_publish_wrong_key_returns_403(self):
        response = self.client.post(PUBLISH_URL, {}, format="json", HTTP_X_CONNECTOR_KEY="bad-key")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_valid_key_passes_auth(self):
        # Valid key passes auth but an empty payload fails serializer validation (400), not auth.
        response = self.client.post(
            PUBLISH_URL, {}, format="json", HTTP_X_CONNECTOR_KEY=self.key_beta
        )
        self.assertNotIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ─────────────────────────────────────────────────────────────────────────────
# 5. PKCE handshake  (initialize + exchange)
# ─────────────────────────────────────────────────────────────────────────────

INITIALIZE_URL = "/api/v1/integration/initialize"
EXCHANGE_URL = "/api/v1/integration/exchange"


@override_settings(**INTEGRATION_SETTINGS)
class PKCEHandshakeTests(_ESMockMixin, APITestCase):

    def setUp(self):
        from apps.auth_oauth.models.auth_models import User
        self.company = make_company()
        # integrate_domain is required before InitializeHandshakeView can proceed.
        self.company.integrate_domain = "http://erp.test"
        self.company.save(update_fields=["integrate_domain"])
        self.user = User.objects.create_user(
            email="tester@example.com",
            username="tester",
            password="test-pass-123",
        )

    def _auth_as_company(self, company_id):
        from apps.core.middleware.requests import CustomJWTRequest
        self.client.force_authenticate(user=self.user)
        return patch.object(
            CustomJWTRequest,
            "company_id",
            new_callable=PropertyMock,
            return_value=str(company_id),
        )

    # ── Initialize ────────────────────────────────────────────────────────────

    def test_initialize_requires_authentication(self):
        response = self.client.post(INITIALIZE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_initialize_returns_authorize_url_and_verifier(self):
        with self._auth_as_company(self.company.id):
            response = self.client.post(INITIALIZE_URL)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        for key in ("authorize_url", "code_verifier", "state", "temporary_code", "redirect_uri"):
            self.assertIn(key, data)

    def test_initialize_blocks_when_already_active(self):
        make_partner(self.company)
        with self._auth_as_company(self.company.id):
            response = self.client.post(INITIALIZE_URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_initialize_allowed_after_disconnect(self):
        make_partner(self.company, status=ConnectorStatus.DISCONNECTED)
        with self._auth_as_company(self.company.id):
            response = self.client.post(INITIALIZE_URL)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ── Exchange ──────────────────────────────────────────────────────────────

    def test_exchange_requires_authentication(self):
        response = self.client.post(EXCHANGE_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_exchange_missing_code_verifier_returns_400(self):
        _, tmp_code, state = make_handshake(str(self.company.id), "my_verifier")
        payload = {
            "temporary_code": tmp_code,
            "state": state,
            "authorization_code": "auth_code_xyz",
        }
        with self._auth_as_company(self.company.id):
            response = self.client.post(EXCHANGE_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing code verifier", response.json().get("message", ""))

    def test_exchange_wrong_code_verifier_returns_400(self):
        _, tmp_code, state = make_handshake(str(self.company.id), "correct_verifier")
        payload = {
            "temporary_code": tmp_code,
            "state": state,
            "authorization_code": "auth_code_xyz",
        }
        with self._auth_as_company(self.company.id):
            response = self.client.post(
                EXCHANGE_URL,
                payload,
                format="json",
                HTTP_X_CODE_VERIFIER="wrong_verifier",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("PKCE", response.json().get("message", ""))

    def test_exchange_expired_handshake_returns_400(self):
        _, tmp_code, state = make_handshake(
            str(self.company.id), "my_verifier", expires_in_seconds=-1
        )
        payload = {
            "temporary_code": tmp_code,
            "state": state,
            "authorization_code": "auth_code_xyz",
        }
        with self._auth_as_company(self.company.id):
            response = self.client.post(
                EXCHANGE_URL,
                payload,
                format="json",
                HTTP_X_CODE_VERIFIER="my_verifier",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.json().get("message", "").lower())

    def test_exchange_state_mismatch_returns_400(self):
        _, tmp_code, _ = make_handshake(str(self.company.id), "my_verifier")
        payload = {
            "temporary_code": tmp_code,
            "state": "wrong_state",
            "authorization_code": "auth_code_xyz",
        }
        with self._auth_as_company(self.company.id):
            response = self.client.post(
                EXCHANGE_URL,
                payload,
                format="json",
                HTTP_X_CODE_VERIFIER="my_verifier",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("State mismatch", response.json().get("message", ""))

    def test_exchange_nonexistent_temporary_code_returns_400(self):
        payload = {
            "temporary_code": "nonexistent_code",
            "state": "some_state",
            "authorization_code": "auth_code_xyz",
        }
        with self._auth_as_company(self.company.id):
            response = self.client.post(
                EXCHANGE_URL,
                payload,
                format="json",
                HTTP_X_CODE_VERIFIER="some_verifier",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exchange_happy_path_creates_partner_and_default_mappings(self):
        verifier = "good_verifier_abc123"
        _, tmp_code, state = make_handshake(str(self.company.id), verifier)
        payload = {
            "temporary_code": tmp_code,
            "state": state,
            "authorization_code": "auth_code_xyz",
        }
        erp_finalize_response = MagicMock()
        erp_finalize_response.status_code = 200
        erp_finalize_response.json.return_value = {
            "key_alpha": "erp_generated_key_alpha",
            "erp_company_id": "ERP-COMPANY-42",
        }

        with self._auth_as_company(self.company.id):
            with patch("apps.integration.views.job_platform_view.requests.post", return_value=erp_finalize_response):
                response = self.client.post(
                    EXCHANGE_URL,
                    payload,
                    format="json",
                    HTTP_X_CODE_VERIFIER=verifier,
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        partner = IntegrationPartner.objects.filter(
            organization_id=str(self.company.id),
            status=ConnectorStatus.ACTIVE,
        ).first()
        self.assertIsNotNone(partner)
        self.assertEqual(partner.partner_tenant_id, "ERP-COMPANY-42")

        fm_count = IntegrationFieldMapping.objects.filter(partner=partner).count()
        self.assertEqual(fm_count, len(DEFAULT_FIELD_MAPPINGS))

        category_fm = IntegrationFieldMapping.objects.get(partner=partner, source_field="category")
        vm_count = IntegrationValueMapping.objects.filter(field_mapping=category_fm).count()
        self.assertEqual(vm_count, len(DEFAULT_CATEGORY_VALUE_MAPPINGS))

    def test_exchange_consumes_handshake(self):
        verifier = "verifier_once_only"
        _, tmp_code, state = make_handshake(str(self.company.id), verifier)
        payload = {
            "temporary_code": tmp_code,
            "state": state,
            "authorization_code": "auth_code_xyz",
        }
        erp_finalize_response = MagicMock()
        erp_finalize_response.status_code = 200
        erp_finalize_response.json.return_value = {
            "key_alpha": "alpha_key",
            "erp_company_id": "ERP-001",
        }

        with self._auth_as_company(self.company.id):
            with patch("apps.integration.views.job_platform_view.requests.post", return_value=erp_finalize_response):
                self.client.post(
                    EXCHANGE_URL,
                    payload,
                    format="json",
                    HTTP_X_CODE_VERIFIER=verifier,
                )

        self.assertFalse(
            IntegrationHandshake.objects.filter(temporary_code=tmp_code).exists(),
            "Handshake must be deleted after a successful exchange.",
        )
