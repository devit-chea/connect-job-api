# Operator ↔ WingDigital Linking — Local Test Data

**Date:** 2026-07-30
**Environment:** `compose_local/docker-compose.local.yml` stack (`http://localhost:8000`)
**Purpose:** Test "one ConnectJob user linked to multiple integrated companies" entirely from the ConnectJob side — no WingDigital server needed. `IntegrationPartner` rows below were seeded directly via Django shell instead of the real `/operator/connect` handshake.

---

## 1. Operator account (created this session)

| Field | Value |
|---|---|
| Username | `operator_test` |
| Email | `operator_test@example.com` |
| Password | `Password123!` (repo's `DEFAULT_PASSWORD` from `.env`) |
| Type | `super_admin` |
| UserCompanyProfile id | `1` (company `1`, "Wing career") |

Created with:
```bash
docker exec job-platform-api-local python manage.py create_default_super_admin \
  --username operator_test --email operator_test@example.com
```

### Login

`POST {{base_url}}/api/login` — **note the path is `/api/login`, not `/api/auth/login`** (the existing Postman collection has the wrong path).

```json
{
  "username": "operator_test",
  "password": "Password123!",
  "type": "super_admin"
}
```

The `"type": "super_admin"` field is **required** — without it, `default_ucp_id` is never resolved (this account has no `default_user_profile_company` set, since `create_default_super_admin` doesn't set it), and the returned JWT has no `user_company_profile_id`/permission claims at all, so every permission-gated endpoint (`operator_manage_company`, `operator_manage_user`, etc.) 403s with `"Permission ... not found. Access denied by default."` regardless of the account's actual role.

With `type` included, the JWT payload contains: `user_id`, `profile_id`, `company_id`, `user_company_profile_id`, `type=super_admin`, `profile_status=approved`. Use the returned `access` token as `Authorization: Bearer <token>` on everything below.

---

## 2. Pre-seeded "integrated" companies

Companies `2` and `3` already exist from earlier testing and **already have an `admin_recruiter` assigned** — reusing them with `AdminUserSerializer` (`/api/operator/user`) for a *second* admin recruiter will hit the pre-existing conflict guard (`"A company already have ADMIN RECRUITER."`). Use companies `4`–`6` below for a clean multi-company test.

| company_id | name | IntegrationPartner status | tenant_id | notes |
|---|---|---|---|---|
| 2 | Test ERP Co | active | erp-tenant-2 | already has admin_recruiter `sokha.chan@example.com` |
| 3 | Second ERP Co | active | erp-tenant-3 | already has admin_recruiter `dara.kim@example.com`, recruiter `sokha.chan@example.com` |
| **4** | **Mekong Tech Ltd** | active | erp-tenant-mekong | fresh, no recruiters yet |
| **5** | **Angkor Finance Group** | active | erp-tenant-angkor | fresh, no recruiters yet |
| **6** | **Riverkid Logistics** | active | erp-tenant-riverkid | fresh, no recruiters yet |
| 1 | Wing career | **none** | — | use this to test the "no active integration" 400 guard |

Seed script (already run for 4–6; re-runnable for more):
```python
from apps.base.models.company_model import Company
from apps.integration.models.job_platform import IntegrationPartner
from apps.integration.constants import ConnectorStatus
from apps.integration.utils.crypto_utils import hash_sha256

companies_data = [
    {"name": "Mekong Tech Ltd", "email": "mekongtech@example.com", "tenant": "erp-tenant-mekong"},
    {"name": "Angkor Finance Group", "email": "angkorfinance@example.com", "tenant": "erp-tenant-angkor"},
    {"name": "Riverkid Logistics", "email": "riverkid@example.com", "tenant": "erp-tenant-riverkid"},
]
for c in companies_data:
    company = Company.objects.create(
        name=c["name"], email=c["email"], is_active=True,
        access_type="internal", is_agree_policy=True,
    )
    key_beta = f"mock_key_beta_{company.id}"
    IntegrationPartner.objects.create(
        organization_id=str(company.id),
        partner_tenant_id=c["tenant"],
        partner_outbound_key=key_beta,
        partner_outbound_hash=hash_sha256(key_beta),
        partner_inbound_key=f"mock_key_alpha_{company.id}",
        status=ConnectorStatus.ACTIVE,
    )
    print(f"company_id={company.id}  name={c['name']!r}")
```

---

## 3. Test A — one user, multiple integrated companies, single request

`POST {{base_url}}/api/operator/user` — requires `operator_manage_user` permission.

```json
{
  "username": "pisey.sok@example.com",
  "email": "pisey.sok@example.com",
  "first_name": "Pisey",
  "last_name": "Sok",
  "is_active": true,
  "password": "TestPass123!",
  "companies": [
    { "company_id": 4, "is_default": true,  "erp_user_id": "erp-mekong-u1" },
    { "company_id": 5, "is_default": false, "erp_user_id": "erp-angkor-u1" },
    { "company_id": 6, "is_default": false, "erp_user_id": "erp-riverkid-u1" }
  ]
}
```

`password` is sent plain — `AUTH_PASSWORD_ENCRYPTION=False` in `.env`, so `EncryptionMixin` is a no-op locally.

**Expect:** one `User`, three separate `UserCompanyProfile` rows, three separate `Profile` rows (each scoped to its own company), three `IntegrationUserMapping` rows each with `user_company_profile_id` pointing at the matching UCP.

---

## 4. Test B — same idea, one company per call

`OperatorIntegrationRecruiterView` — use `role_type: "recruiter"` (not `admin_recruiter`) so it doesn't collide with Test A's admin-recruiter conflict guard if run against the same companies. Use a different email than Test A.

```json
// POST {{base_url}}/api/v1/integration/operator/companies/4/recruiter
{ "erp_user_id": "erp-mekong-u2", "email": "vibol.heng@example.com", "first_name": "Vibol", "last_name": "Heng", "role_type": "recruiter" }
```
```json
// POST {{base_url}}/api/v1/integration/operator/companies/5/recruiter
{ "erp_user_id": "erp-angkor-u2", "email": "vibol.heng@example.com", "first_name": "Vibol", "last_name": "Heng", "role_type": "recruiter" }
```
```json
// POST {{base_url}}/api/v1/integration/operator/companies/6/recruiter
{ "erp_user_id": "erp-riverkid-u2", "email": "vibol.heng@example.com", "first_name": "Vibol", "last_name": "Heng", "role_type": "recruiter" }
```

---

## 5. Verification snippet

```python
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.models.profile_model import Profile
from apps.integration.models.job_platform import IntegrationUserMapping

u = User.objects.get(email="pisey.sok@example.com")  # or vibol.heng@example.com
for ucp in UserCompanyProfile.objects.filter(user=u):
    print(ucp.id, ucp.company_id, ucp.type, "profile_id=", ucp.profile_id)
for p in Profile.objects.filter(user=u):
    print("profile", p.id, "company_id=", p.company_id)
profile_ids = list(Profile.objects.filter(user=u).values_list("id", flat=True))
for m in IntegrationUserMapping.objects.filter(local_user_id__in=[str(pid) for pid in profile_ids]):
    print("mapping", m.local_user_id, "->", m.partner_user_id, "ucp=", m.user_company_profile_id)
```

---

## 6. Already-proven this session (companies 2 & 3)

| User | Email | Company | UCP id | Profile id | erp_user_id |
|---|---|---|---|---|---|
| id=2 | sokha.chan@example.com | 2 (Test ERP Co) | 2 | 2 | erp-user-001 |
| id=2 | sokha.chan@example.com | 3 (Second ERP Co) | 3 | 3 | erp-user-999 |
| id=3 | dara.kim@example.com | 3 (Second ERP Co) | 4 | 4 | erp-user-dara-3 |

Confirms: same `User` (id=2) across two companies got **two distinct `Profile` rows** (2 and 3), each correctly scoped to its own company — the exact bug that was fixed. Guard paths also verified: duplicate UCP → 400; company with no active integration (company `1`) → 400.

## Gotchas

- `AdminUserSerializer` always assigns `type=admin_recruiter` — only one per company is allowed (pre-existing conflict guard). Use `OperatorIntegrationRecruiterView` with `role_type: "recruiter"` if you need a second person at the same company.
- `erp_user_id` on a company with no active `IntegrationPartner` → 400 up front, before any DB writes (validated in `AdminUserSerializer.validate_companies`).
- All of this data lives only in the local `compose_local` Postgres volume — nothing was sent to a real WingDigital instance.
