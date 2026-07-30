# ConnectJob API — Performance & Scalability Changes

**Date:** 2026-06-14
**Branch:** `feature/integration`
**Author:** davitchea

---

## Summary

10 changes across 4 phases targeting N+1 queries, missing DB indexes, Gunicorn capacity, Celery queue starvation, and ES inefficiencies. No API contracts were modified. All migrations are additive (index-only).

---

## Phase 1 — Quick Wins

### 1.1 Database Indexes (4 models, 3 migrations)

**Problem:** High-traffic filter columns had no indexes, causing full table scans on every login, job listing, and application lookup.

#### `apps/auth_oauth/models/auth_models.py`
**Migration:** `apps/auth_oauth/migrations/0005_user_performance_indexes.py`

```python
# Added to User.Meta.indexes
models.Index(fields=["email"],               name="user_email_idx"),
models.Index(fields=["status", "is_active"], name="user_status_active_idx"),
```

- `email` is not `unique=True` so Django never auto-indexed it; every login and `create_user` call did a full scan on `auth_user`.
- Composite `(status, is_active)` covers `UserManager.get_by_natural_key` and `UserManager.create_user` filters.

---

#### `apps/job_management_app/models/job_post_model.py`
**Migration:** `apps/job_management_app/migrations/0008_jobpost_performance_indexes.py`

```python
# Added to JobPostModel.Meta.indexes
models.Index(fields=["company_id", "is_deleted", "status"], name="jp_company_deleted_status_idx"),
models.Index(fields=["company_id", "create_ucp_id"],        name="jp_company_ucp_idx"),
models.Index(fields=["expire_date"],                         name="jp_expire_date_idx"),
models.Index(fields=["create_date"],                         name="jp_create_date_idx"),
```

- `(company_id, is_deleted, status)` covers `CompanyJobPostListView`, `DashboardRecruiterJobView`.
- `(company_id, create_ucp_id)` covers `RecruiterJobPostListView`.
- `expire_date` covers the public job-listing date-range filter.
- `create_date` covers ordering on dashboard and recruiter views.

---

#### `apps/job_management_app/models/job_application_model.py`
**Migration:** `apps/job_management_app/migrations/0008_jobpost_performance_indexes.py` (same migration)

```python
# Added to JobApplicationModel.Meta.indexes (existing indexes preserved)
models.Index(fields=["profile_id"],              name="ja_profile_idx"),
models.Index(fields=["job_post_id", "is_deleted"],name="ja_job_deleted_idx"),
models.Index(fields=["apply_date"],              name="ja_apply_date_idx"),
```

- `profile_id` covers applicant-scoped lookups across multiple views.
- `(job_post_id, is_deleted)` covers the recruiter applicant list (most common query).
- `apply_date` covers date-ordering on dashboard.

---

#### `apps/activity_tracking_app/models/job_post_user_state_model.py`
**Migration:** `apps/activity_tracking_app/migrations/0003_jobpostuserstate_performance_indexes.py`

```python
# Added to JobPostUserStateModel.Meta.indexes
models.Index(fields=["job_post_id", "status"],   name="jpus_post_status_idx"),
models.Index(fields=["user_company_profile_id"], name="jpus_ucp_idx"),
```

- `(job_post_id, status)` covers `get_is_saved` and `get_is_applied` in `JobPostDetailSerializer` — previously full scans on a table with millions of rows for popular job posts.

---

### 1.2 Gunicorn Capacity

**File:** `entrypoint-server.sh`

| Setting | Before | After |
|---|---|---|
| Workers | `2` (hardcoded) | `$(( 2 * $(nproc) + 1 ))` |
| Threads | `2` (hardcoded) | `4` |
| Timeout | `30s` | `120s` |

**Before:** 2 workers × 2 threads = **4 concurrent requests** maximum.  
**After (2-CPU pod):** 5 workers × 4 threads = **20 concurrent requests**.

The 30s timeout was causing Gunicorn to SIGKILL workers mid-response on ES-heavy endpoints (match rate, smart score queries can take 2–5s each).

---

### 1.3 Settings Tuning

**File:** `config/settings/base.py`

#### Permission Cache
```python
# Before
AUTH_PERMISSION_CACHE_ENABLED = env.bool("AUTH_PERMISSION_CACHE_ENABLED", False)
# After
AUTH_PERMISSION_CACHE_ENABLED = env.bool("AUTH_PERMISSION_CACHE_ENABLED", True)
```
Every role-gated view was hitting the DB to resolve permission sets on every request. The cache backend (Redis) was already wired up but disabled by default.

#### Database Persistent Connections
```python
# Added to DATABASES["default"]
"CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", 60),
```
Without this, every request opened a new TCP connection to PostgreSQL (+1–5 ms overhead). Set to `0` via env var when using PgBouncer.

#### Redis Connection Pool
```python
# Sentinel CACHES OPTIONS
"max_connections": env.int("REDIS_MAX_CONNECTIONS", 200),  # was hardcoded 100
"SOCKET_CONNECT_TIMEOUT": 5,
"SOCKET_TIMEOUT": 5,

# Standalone CACHES OPTIONS (same additions)
"max_connections": env.int("REDIS_MAX_CONNECTIONS", 200),
"SOCKET_CONNECT_TIMEOUT": 5,
"SOCKET_TIMEOUT": 5,
```
With `2N+1` Gunicorn workers + Celery workers, Redis connection demand under load can exceed 100. Socket timeouts prevent a slow Redis node from hanging a worker indefinitely.

---

## Phase 2 — Queryset Optimization

### 2.1 Eliminate N+1 in Job Post List Serializers

**Files:** `apps/job_management_app/views/job_post_view.py`, `apps/job_management_app/serializers/job_post_serializer.py`

**Problem:** `JobPostSerializer.to_representation()` executed two extra queries **per job post** in every list response:
1. `JobPostAdditionalFieldModel.objects.filter(job_post=instance)` — line 345
2. `instance.job_post_assigned_recruiters.filter(is_deleted=False)` — line 366

For a page of 10 job posts: **1 base query + 10 additional field queries + 10 recruiter queries = 21 queries.**

**Fix — shared prefetch helper added to `job_post_view.py`:**
```python
def _job_post_list_queryset(qs):
    return (
        qs
        .select_related(
            "company", "job_category", "job_location",
            "job_pipeline_config", "user_activity_count",
        )
        .prefetch_related(
            Prefetch(
                "additional_field",
                queryset=JobPostAdditionalFieldModel.objects.filter(is_deleted=False)
                         .values("code", "name", "description", "field_name"),
                to_attr="prefetched_additional_fields",
            ),
            Prefetch(
                "job_post_assigned_recruiters",
                queryset=JobPostAssignedRecruiterModel.objects.filter(
                    is_deleted=False
                ).select_related("assigned_ucp__profile"),
                to_attr="prefetched_recruiters",
            ),
        )
    )
```

Applied to `get_queryset()` in 5 views:
- `ApplicantJobPostView`
- `RecruiterJobPostView`
- `CompanyJobPostListView`
- `RecruiterJobPostListView._get_filtered_queryset`
- `OperatorJobPostView`

**Fix — serializer reads prefetched attrs with DB fallback (detail views still work):**
```python
# to_representation — additional fields
prefetched = getattr(instance, "prefetched_additional_fields", None)
grouped_fields = prefetched if prefetched is not None else list(
    JobPostAdditionalFieldModel.objects.filter(job_post=instance, is_deleted=False)
    .values("code", "name", "description", "field_name")
)

# to_representation — assigned recruiters
prefetched_recruiters = getattr(instance, "prefetched_recruiters", None)
assignments = prefetched_recruiters if prefetched_recruiters is not None else (
    instance.job_post_assigned_recruiters.filter(is_deleted=False)
    .select_related("assigned_ucp__profile")
)
```

Same guard applied to `JobPostListSerializer.get_assigned_recruiters()`.

**Result:** Page of 10 job posts: **21 queries → 3 queries.**

---

### 2.2 Add `profile` to Application View Querysets

**File:** `apps/job_management_app/views/job_application_views.py`

**Problem:** `RecruiterJobApplicationView.get_queryset()` had `select_related("job_post", "pipeline_step", "pipeline_status")` but was missing `"profile"`. The recruiter applicant list view (`RecruiterJobListApplicantsView`) had no `select_related` at all. `JobApplicationView` was also missing the profile FK.

**Fix:** Added `"profile"` to all three querysets:

```python
# JobApplicationView.get_queryset
queryset.select_related("job_post", "pipeline_step", "pipeline_status", "profile")

# RecruiterJobApplicationView.get_queryset (added "profile")
.select_related("job_post", "pipeline_step", "pipeline_status", "profile")

# RecruiterJobListApplicantsView.list (inline queryset)
JobApplicationModel.objects.filter(job_post_id=job_post_id)
    .select_related("job_post", "pipeline_step", "pipeline_status", "profile")
```

**Result:** Recruiter applicant list (50 applicants): **~50 profile FK queries → 0.**

---

### 2.3 Collapse Dashboard Count Queries

**File:** `apps/dashboard/views/dashboard_job_views.py`

**Problem:** `JobStatsView.get()` called `.count()` four separate times against the same queryset — 4 SQL `SELECT COUNT(*)` round-trips.

**Fix:** Replaced with a single `aggregate()` using `Count(Case(When(...)))`:

```python
today = timezone.localdate()
stats = qs.aggregate(
    total_jobs=Count("id"),
    active_jobs=Count(Case(
        When(status=JobPostStatusTypes.ACTIVE.value, expire_date__gte=today, then=1),
        output_field=IntegerField(),
    )),
    closed_jobs=Count(Case(
        When(status=JobPostStatusTypes.ACTIVE.value,
             expire_date__isnull=False, expire_date__lt=today, then=1),
        output_field=IntegerField(),
    )),
    on_hold_jobs=Count(Case(
        When(status=JobPostStatusTypes.INACTIVE.value, then=1),
        output_field=IntegerField(),
    )),
)
```

Also added a 60-second response cache keyed on `company_id` + query params:
```python
cache_key = f"dashboard_job_stats:{request.company_id}:{request.query_params.urlencode()}"
cached = cache.get(cache_key)
if cached is not None:
    return Response(cached)
# ... build stats ...
cache.set(cache_key, final_data, timeout=60)
```

**Result:** 4 DB round-trips → 1. Multiple recruiters on the same dashboard in the same 60s window share one DB query.

---

### 2.4 Cache `JobCategoryModel` Icon Lookup

**File:** `apps/job_management_app/serializers/job_post_serializer.py`

**Problem:** `_get_category_icon_map()` queried `JobCategoryModel` on every list request. Categories are seeded data — they change only when the management command `default_job_categories_config` runs.

**Fix:** Added a 1-hour Django cache layer:
```python
CACHE_KEY = "job_category_icon_map"
cached = cache.get(CACHE_KEY)
if cached is not None:
    self.context["category_icon_map"] = cached
    return cached

# ... existing DB query ...

cache.set(CACHE_KEY, icon_map, timeout=3600)
```

**Invalidation:** Add `cache.delete("job_category_icon_map")` to `default_job_categories_config` management command when categories are re-seeded.

---

## Phase 3 — Celery & Elasticsearch

### 3.1 ES Bulk Sync via `helpers.bulk`

**File:** `apps/elasticsearch_app/services/job_post_es_sync_services.py`

**Problem:** `JobPostESSyncServices.bulk_sync()` iterated job posts one-by-one calling `doc.update(job_post)` per item — one HTTP round-trip to ES per document.  
For 200 job posts triggered by a company save: **200 ES HTTP calls.**

**Fix:** Replaced with `elasticsearch.helpers.bulk()`:
```python
from elasticsearch.helpers import bulk as es_bulk
from elasticsearch_dsl.connections import connections

def _iter_actions():
    for job_post in job_posts:
        if fields:
            yield {
                "_op_type": "update",
                "_index": JobPostDocument.Index.name,
                "_id": job_post.id,
                "doc": build_es_partial_update_doc(doc, job_post, fields),
                "doc_as_upsert": True,
            }
        else:
            yield {
                "_op_type": "index",
                "_index": JobPostDocument.Index.name,
                "_id": job_post.id,
                "_source": doc.prepare(job_post),
            }

success, errors = es_bulk(
    connections.get_connection(),
    _iter_actions(),
    chunk_size=500,
    raise_on_error=False,
)
```

**Result:** 200 job posts: **200 HTTP calls → 1 HTTP call** (chunked at 500).

---

### 3.2 Fix Double ES Round-Trip in Global Search

**File:** `apps/elasticsearch_app/views/elastic_global_search_view.py`

**Problem:** For both companies and people the view called `.count()` then `.execute()` separately — 2 ES calls per entity type, 4+ total per global search request.

```python
# Before
total_companies = company_search.count()          # ES call 1
company_results = company_search[:limit].execute() # ES call 2
```

**Fix:** Execute once and read total from response:
```python
# After
company_response = company_search[:self.PAGE_LIMIT].execute()  # ES call 1 only
total_companies = company_response.hits.total.value
company_results = company_response
```

Same fix applied for `people_search`.

**Result:** Global search: **4 ES calls → 2 ES calls.**

---

### 3.3 Celery Task Queue Routing

**Files:** `config/settings/base.py`, `entrypoint-celery.sh`

**Problem:** All tasks shared a single default queue. A burst of 500 ES sync tasks (triggered by a bulk company update) would starve email, activity flush, and ERP sync tasks.

**Fix — routing rules in `config/settings/base.py`:**
```python
CELERY_TASK_ROUTES = {
    "elastic_task.*":                                               {"queue": "es_sync"},
    "activity_tracking.bulk_update_job_post_activity_counts_to_es": {"queue": "es_sync"},
    "activity_tracking.flush_redis_counters_to_db":                 {"queue": "activity"},
    "activity_tracking.flush_dirty_job_post_ids":                   {"queue": "activity"},
    "activity_tracking.increment_activity":                         {"queue": "activity"},
    "integration.*":                                                {"queue": "erp_sync"},
}
```

**Fix — `entrypoint-celery.sh` runs 4 separate worker processes:**
```bash
celery -A config worker --queues=es_sync    -c ${CELERY_ES_CONCURRENCY:-2}       &
celery -A config worker --queues=activity   -c ${CELERY_ACTIVITY_CONCURRENCY:-3}  &
celery -A config worker --queues=erp_sync   -c ${CELERY_ERP_CONCURRENCY:-2}       &
celery -A config worker --queues=celery     -c ${CELERY_CONCURRENCY:-4}           # default queue
wait
```

Each queue's concurrency is independently tunable via env vars.

---

### 3.4 Chunk Dirty Job Post ID Flush

**File:** `apps/activity_tracking_app/tasks/tasks.py`

**Problem:** `flush_dirty_job_post_ids` called `.pop_dirty_job_post_ids()` which loads **all** dirty IDs at once and dispatches them in a **single Celery message**. With 10,000 dirty IDs, that's one huge JSON payload in the broker.

**Fix:** Dispatch in 500-item chunks:
```python
_DIRTY_FLUSH_CHUNK_SIZE = 500

@shared_task(name="activity_tracking.flush_dirty_job_post_ids")
def flush_dirty_job_post_ids():
    dirty_ids = DirtyRedisSyncService.pop_dirty_job_post_ids()
    if not dirty_ids:
        return
    for i in range(0, len(dirty_ids), _DIRTY_FLUSH_CHUNK_SIZE):
        chunk = dirty_ids[i:i + _DIRTY_FLUSH_CHUNK_SIZE]
        bulk_update_job_post_activity_counts_to_es.delay(chunk)
```

**Result:** 10,000 IDs → 20 tasks of 500, each <5 KB payload. Work distributes across multiple workers.

---

## Phase 4 — Middleware

### 4.1 Remove Redis Round-Trip from Audit Middleware

**File:** `apps/core/middleware/audilog_middleware.py`

**Problem:** `JWTAuditlogMiddleware._authenticate_jwt()` called `CustomJWTAuthentication.get_validated_token()`, which includes a **Redis JTI check** (`redis_client.get(f"access_jti:{jti}")`). This Redis call happened on **every authenticated request**, in addition to the same check already performed by DRF's view-layer authentication.

**Fix:** Use the base `JWTAuthentication.get_validated_token()` (signature + expiry check only, no Redis) for the audit actor resolution. DRF's full auth (including JTI revocation) still runs in the view layer.

```python
# Before
auth = CustomJWTAuthentication()
validated_token = auth.get_validated_token(raw_token)  # includes Redis JTI check

# After
base_auth = JWTAuthentication()
validated_token = base_auth.get_validated_token(raw_token)  # signature only, no Redis
return custom_auth.get_user(validated_token)
```

**Result:** Saves **1 Redis round-trip per authenticated request** (~1–3 ms under normal load, more under Redis latency).

---

## Files Changed

| File | Type |
|---|---|
| `apps/auth_oauth/models/auth_models.py` | Model (indexes added) |
| `apps/auth_oauth/migrations/0005_user_performance_indexes.py` | New migration |
| `apps/job_management_app/models/job_post_model.py` | Model (indexes added) |
| `apps/job_management_app/models/job_application_model.py` | Model (indexes added) |
| `apps/job_management_app/migrations/0008_jobpost_performance_indexes.py` | New migration |
| `apps/activity_tracking_app/models/job_post_user_state_model.py` | Model (indexes added) |
| `apps/activity_tracking_app/migrations/0003_jobpostuserstate_performance_indexes.py` | New migration |
| `entrypoint-server.sh` | Gunicorn config |
| `entrypoint-celery.sh` | Celery worker config |
| `config/settings/base.py` | Settings (cache, DB, Redis, Celery routes) |
| `apps/job_management_app/views/job_post_view.py` | View (prefetch chain) |
| `apps/job_management_app/serializers/job_post_serializer.py` | Serializer (N+1 fix, category cache) |
| `apps/job_management_app/views/job_application_views.py` | View (select_related) |
| `apps/dashboard/views/dashboard_job_views.py` | View (aggregate, cache) |
| `apps/elasticsearch_app/services/job_post_es_sync_services.py` | Service (helpers.bulk) |
| `apps/elasticsearch_app/views/elastic_global_search_view.py` | View (count+execute fix) |
| `apps/activity_tracking_app/tasks/tasks.py` | Task (chunked flush) |
| `apps/core/middleware/audilog_middleware.py` | Middleware (Redis skip) |

---

## How to Apply

```bash
# 1. Run migrations
python manage.py migrate

# 2. Rebuild Docker image (Gunicorn/Celery entrypoint changes)
docker compose -f compose_local/docker-compose.local.yml up --build

# 3. Invalidate category icon cache after re-seeding categories
python manage.py default_job_categories_config
# add cache.delete("job_category_icon_map") to that command for auto-invalidation
```

## Verification

```bash
# Confirm indexes exist in PostgreSQL
psql -U postgres -d job_platform_local -c "\d+ auth_user"
psql -U postgres -d job_platform_local -c "\d+ job_post"

# Check permission cache is active after first authenticated request
redis-cli keys "*permission*"

# Verify Celery queues are routed correctly
celery -A config inspect active_queues

# Confirm DB query count on list endpoints dropped (requires django-silk or DEBUG toolbar)
# Expected: job post list ≤ 5 queries, was 21+
```
