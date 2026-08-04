# Record Scope Feature — Verification Test Data

Snapshot of the data created/used to verify the per-permission `record_scope`
(own/all/shared) feature end-to-end against the local `compose_local` stack.
All calls were made with in-memory-minted JWTs via
`rest_framework.test.APIClient` (Django shell) — no tokens were persisted to
disk.

## Company

| id | name |
|---|---|
| 4 | Mekong Tech Ltd |

## Permission under test

| id | codename | name |
|---|---|---|
| 45 | `admin_recruiter_manage_user` | Manage User |

## Users / UserCompanyProfiles (company 4)

| UCP id | User email | User id | Type | Role(s) | `create_ucp_id` | `create_uid` | Notes |
|---|---|---|---|---|---|---|---|
| 5 | pisey.sok@example.com | 4 | admin_recruiter | 2 (Admin Recruiter Default Role) | `None` | 1 | Company admin_recruiter; owns Team Lead A & Recruiter X |
| 8 | vibol.heng@example.com | 5 | recruiter | 3 (Recruiter Default Role) | `None` | `None` | Pre-existing record, created **before** the `create_ucp_id` stamping fix — left as `None` deliberately (no retroactive backfill) |
| 12 | verify.recruiter1.1785731705@example.com | 7 | recruiter | 7 (Mekong Custom Recruiter Role, test artifact) | `None` | `None` | Same as above — pre-fix legacy record |
| 14 | team.lead.a.1785750311@example.com | 9 | recruiter | 9 (Mekong Team Lead Role — own scope) | **5** | **4** | Created by Pisey with explicit `roles: [9]`; used as the "OWN scope" viewer |
| 15 | recruiter.x.1785750311@example.com | 10 | recruiter | 7 (fallback role — unordered `.first()` picked an older custom role, not a bug, see below) | **5** | **4** | Created by Pisey with no explicit role (fallback path) |
| 16 | recruiter.c.1785750349@example.com | 11 | recruiter | 3 (Recruiter Default Role) | **14** | **9** | Created by **Team Lead A**, not Pisey — proves `create_ucp_id` stamps the actual caller, not just top-level admin_recruiters |

## Operator

| UCP id | User email | Type | Roles |
|---|---|---|---|
| 1 | operator_test@example.com | super_admin | 1 |

## Roles

| Role id | Name | Code | Type | `custom_for_ucp_id` | RolePermission (perm 45) |
|---|---|---|---|---|---|
| 2 | Admin Recruiter Default Role | `ADMIN_RECRUITER_ROLE` | admin_recruiter | — | `perm_type=allowed`, `record_scope=all` (backfilled by migration `0009`, preserving pre-feature company-wide visibility) |
| 3 | Recruiter Default Role | `RECRUITER_ROLE` | recruiter | — | (no `admin_recruiter_manage_user` grant — plain recruiters don't manage other recruiters) |
| 7 | Mekong Custom Recruiter Role 1785731474670 | `MEKONG_CUSTOM_...` | recruiter | 5 | test artifact from an earlier session, unrelated to this feature |
| 9 | Mekong Team Lead Role (own scope) | `MEKONG_TEAM_LEAD_OWN` | recruiter | 5 | `perm_type=allowed`, `record_scope` toggled during verification: `own` → `shared` → `all` → `own` (final state) |

## Sharing grant

| Share id | `target_ucp` | `viewer_ucp` | `create_ucp_id` (who granted it) | Created |
|---|---|---|---|---|
| 1 | 15 (Recruiter X) | 14 (Team Lead A) | 5 (Pisey) | 2026-08-03 09:49:36 UTC |

Created via `POST /api/recruiter_admin/user-shares` as Pisey — grants Team
Lead A read-only visibility into Recruiter X's record without transferring
ownership.

## Verification matrix

All calls against `GET /api/recruiter_admin/users` as **Team Lead A** (UCP 14, role 9):

| Role 9 `record_scope` | Expected result | Actual result | Result |
|---|---|---|---|
| `own` | Only records Team Lead A created (Recruiter C) | `[recruiter.c...]` | ✅ |
| `shared` | Own + explicitly shared (Recruiter C, Recruiter X) | `[recruiter.c..., recruiter.x...]` | ✅ |
| `all` | Every active recruiter at company 4 (matches Pisey's own list under the `all`-scope default role) | `[recruiter.c..., recruiter.x..., team.lead.a..., verify.recruiter1...]` — identical to Pisey's list | ✅ |

Additional checks:

- **`create_ucp_id` stamping fix** — UCPs 14/15/16 (created after the fix) all show a real `create_ucp_id`/`create_uid`; UCPs 8/12 (created before the fix, untouched/no backfill) correctly remain `None`.
- **Cache invalidation** — primed the permission cache key `permissions:user:9:ucp:14` directly, called `RoleSerializer._invalidate_permission_cache(role)` under `AUTH_PERMISSION_CACHE_ENABLED=True`, confirmed the key was deleted (key format matches exactly what `PermissionService.fetch_permissions` computes at read time).
- **Backfill migration** — pre-existing `RolePermission` id 32 (role 2 × permission 45) shows `record_scope=all` post-migration, not the new column's `own` default — no regression for existing admin_recruiter grants.
- **Job-post scoping regression** — confirmed via `git diff` that `apps/base/utils/custom_filter.py` and `apps/auth_oauth/models/role_model.py` have zero changes, and `PermissionService.get_user_roles_and_permissions()`/`effective_scope()` are untouched; the new `get_record_scope()` method is a pure addition.

## Known non-issues in this data

- **Role 7 fallback on Recruiter X**: when Pisey created Recruiter X without an explicit `roles` list, the fallback selector (`get_allowed_recruiter_roles()`, a separate/earlier feature) picked role 7 instead of role 9 because both share `custom_for_ucp_id=5` and the fallback takes an unordered `.first()`. Not a record-scope bug — verification used `create_ucp_id` directly rather than relying on which role got assigned.

## Separate pre-existing bug found during regression check (not part of this feature)

`GET /api/recruiter/job_post` (and other list views routed through
`_job_post_list_queryset` in `apps/job_management_app/views/job_post_view.py`)
currently 500s:

```
ValueError: Prefetch querysets cannot use raw(), values(), and values_list().
```

Caused by a `Prefetch("additional_field", queryset=...values(...))` call.
Confirmed pre-existing via `git log` (file last touched in committed commit
`fd17028`, not modified by this feature's diff) — flagged here for
visibility, not fixed as part of this work.
