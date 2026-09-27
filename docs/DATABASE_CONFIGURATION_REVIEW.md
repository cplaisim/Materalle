# Materalle-2 Database Configuration Review Report

**Date**: March 6, 2026
**Status**: RESEARCH ONLY - No changes made
**Reviewed Files**:
- `materalleapp/settings.py`
- `docker-compose.yml`
- `Dockerfile`
- `enroll/models.py`, `sage/models.py`
- `enroll/views.py`, `sage/views.py`
- `requirements.txt`
- Migration history (enroll, sage, grace, patience, website, agent)

---

## 1. PostgreSQL Connection Configuration

### Current Setup
**File**: `materalleapp/settings.py` (lines 86-99)

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "materalle_db"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

### Assessment: GOOD
- ✅ All credentials from environment variables (no hardcoded secrets)
- ✅ Sensible defaults for local development
- ✅ Correct PostgreSQL engine (`django.db.backends.postgresql`)
- ✅ Correct variable names match `.env` file

### Actual Runtime Values
From `.env` file:
```
DB_NAME=materalle_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
```

---

## 2. SQLite Fallback Configuration

### Current Setup
**File**: `materalleapp/settings.py` (lines 87-90)

```python
"sqlite": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / os.environ.get("SQLITE_NAME", "db.sqlite3"),
}
```

### Assessment: GOOD STRUCTURE, UNTESTED PATH
- ✅ Correctly structured for development fallback
- ✅ Uses `SQLITE_NAME` env var with sensible default
- ⚠️ **CONCERN**: SQLite fallback is defined but untested in production
- ⚠️ **CONCERN**: No documentation on how to switch between databases
- ⚠️ **CONCERN**: Django uses `"default"` alias by default; to use SQLite, code must explicitly specify `using='sqlite'` or reconfigure settings

### Recommendation
If SQLite is meant as a development-only alternative, add documentation in code comments. If meant for production failover, create a migration strategy to verify all features work with SQLite.

---

## 3. Django Admin & Student/Child Models

### Student Model Structure
**File**: `enroll/models.py` (lines 7-101)

**Key Fields**:
- **Primary Key**: `child_id` (AutoField, not BigAutoField)
- **Foreign Keys**:
  - `enrolled_by` → `settings.AUTH_USER_MODEL` (SET_NULL on delete)
  - `last_modified_by` → `settings.AUTH_USER_MODEL` (SET_NULL on delete)
- **ImageField**: `profile_picture` (upload_to='profile_pics/')

**Multi-Table Inheritance**:
```python
class Child(Student):
    is_checked_in = models.BooleanField(default=False)
    check_in_time = models.DateTimeField(null=True, blank=True)
```

### Migration History
**File**: `enroll/migrations/`

1. **0001_initial.py** (April 4, 2025): Creates Student model with custom PK `child_id` (AutoField)
2. **0002_alter_child_table.py** (April 5, 2025): `AlterModelTable(name="child", table=None)`
   - **PURPOSE**: Resets Child table name to Django's default (`enroll_child` instead of custom naming)
   - **IMPLICATION**: Child is multi-table inheritance; Django creates separate `enroll_child` table with foreign key to `enroll_student`

### Assessment: WORKING BUT WITH CAVEATS
- ✅ Migrations are applied and consistent
- ✅ Django admin integration works (`Student` & `Child` in INSTALLED_APPS)
- ⚠️ **PRIMARY KEY CONCERN**: `child_id` is AutoField (32-bit), not BigAutoField (64-bit)
  - AutoField max value: 2,147,483,647
  - At 1000 enrollments/year, you reach limit in ~2M years, so NOT an immediate risk
  - However, Django default is BigAutoField as of Django 3.2+
- ⚠️ **MULTI-TABLE INHERITANCE**: Creates extra JOIN on every Child query
  - `SELECT * FROM child JOIN student ON child.child_id = student.child_id`
  - Impacts performance if Child is frequently queried (e.g., attendance tracking)
- ✅ Foreign key relationships properly configured with SET_NULL

### Database Representation
```
enroll_student:
  child_id (PK)          -> AutoField
  profile_picture
  child_name
  date_of_birth
  ... [40+ fields]
  enrolled_by_id (FK)
  enrollment_date
  last_modified_by_id (FK)
  last_modified

enroll_child:
  student_ptr_id (PK, FK) -> enroll_student.child_id
  is_checked_in
  check_in_time
```

### Recommendation
Consider documenting the multi-table inheritance approach. If query performance becomes an issue with thousands of children, evaluate:
1. Proxy model (if Child doesn't need separate table)
2. Abstract base class (if no inheritance needed)
3. Add database index on `check_in_time` and `is_checked_in` for attendance queries

---

## 4. Environment Variable Usage for DB Credentials

### Assessment: EXCELLENT
- ✅ Uses `python-dotenv` (in requirements.txt) to load `.env` file
- ✅ All DB credentials from env vars: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- ✅ Sensible defaults for development

### Current `.env` Values (from inspection)
```
DJANGO_SECRET_KEY=django-insecure-<REDACTED-ROTATE-THIS-KEY>
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1, https://materalle-2-x0qj.onrender.com/,*
DB_NAME=materalle_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
ANTHROPIC_API_KEY=sk-ant-api03-<REDACTED-ROTATE-THIS-KEY>
```

### CRITICAL SECURITY ISSUE ⛔
- `.env` file is checked into git repository with **sensitive API keys**
- `ANTHROPIC_API_KEY` is exposed in version control
- `DJANGO_SECRET_KEY` uses `django-insecure-` prefix (weak)
- **RECOMMENDATION**: Move `.env` to `.gitignore`, rotate all exposed keys immediately

### Docker Environment Override
**File**: `docker-compose.yml` (lines 23-26)

```yaml
environment:
  DJANGO_SETTINGS_MODULE: materalleapp.settings
  DB_HOST: db           # Overrides for Docker networking
  DB_PORT: 5432
```

**Assessment**: ✅ Correct override for Docker container communication

---

## 5. Docker Database Configuration

### docker-compose.yml Analysis
**File**: `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:15
    container_name: materalle_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME:-materalle_db}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    ...
    depends_on:
      - db
```

### Assessment: MOSTLY GOOD WITH CAVEATS
- ✅ PostgreSQL 15 is current and stable
- ✅ Proper data persistence with named volume `db_data:/var/lib/postgresql/data`
- ✅ Environment variables correctly passed to PostgreSQL
- ✅ Web service depends on `db` service
- ⚠️ **NO HEALTH CHECK**: `depends_on` only waits for container start, not database readiness
  - Django will fail to connect if `db` container hasn't finished initializing
  - Database takes ~3-5 seconds to become ready after container start
- ⚠️ **MISSING**: No explicit `--database` flag in migration commands
  - If both services start simultaneously, migrations may fail

### Recommended Fix for Health Check
```yaml
db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 5s
    timeout: 5s
    retries: 5

web:
  depends_on:
    db:
      condition: service_healthy
```

---

## 6. Storage Configuration (S3 vs Local)

### Current Setup
**File**: `materalleapp/settings.py` (lines 151-152)

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### Assessment: INCOMPLETE
- ✅ Local media storage configured (development default)
- ❌ **S3 NOT CONFIGURED**: Despite `django-storages` and `boto3` in requirements.txt
- ❌ **NO CONDITIONAL STORAGE BACKEND**: No environment-based switch between local and S3

### Expected for Production
**File**: `requirements.txt` (lines 30-31)

```
django-storages
boto3
```

**FINDING**: Packages are installed but not used in settings.py. This is a gap between dev and production.

### Recommendation
Add conditional storage configuration:

```python
if not DEBUG:  # Production
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_FILE_OVERWRITE = False
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
else:  # Development
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

---

## 7. Query Performance & N+1 Issues

### Current State
**Files Checked**: `enroll/views.py`, `sage/views.py`

**Key Findings**:

1. **sage/views.py, line 164**: Only instance of `prefetch_related()` found
   ```python
   ).prefetch_related('mealattendance_set')
   ```

2. **enroll/views.py, line 40-43**: Inefficient Child queries
   ```python
   student_list = Student.objects.all()
   # ...later...
   students = Child.objects.all()
   ```
   - No `select_related('enrolled_by')` or `select_related('last_modified_by')`
   - If rendering enrolled_by name in template, triggers N queries

3. **sage/views.py, line 38**: Full Child query without optimization
   ```python
   students = Child.objects.all()
   ```

### Assessment: OPTIMIZATION OPPORTUNITY
- ⚠️ **N+1 RISK**: Most views fetch full relationships without optimization
- ✅ No raw SQL calls detected (safe from injection)
- ✅ No complex aggregations that would strain DB

### Recommendations
Add to high-frequency views:
```python
Child.objects.select_related('enrolled_by', 'last_modified_by')
Meal.objects.prefetch_related('mealattendance_set')
```

---

## 8. Database Indexing

### Current Indexes
**Assessment**: DEFAULT ONLY
- ✅ Django auto-creates indexes for primary keys and foreign keys
- ⚠️ **MISSING**: No custom indexes on frequently queried fields

### Recommended Indexes

#### Critical for Attendance Tracking
`enroll/models.py` — Child model:
```python
class Child(Student):
    is_checked_in = models.BooleanField(default=False, db_index=True)
    check_in_time = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_checked_in', 'check_in_time']),
        ]
```

#### For Attendance Logs
`enroll/models.py` — AttendanceLog model:
```python
class Meta:
    ordering = ['-check_in']
    indexes = [
        models.Index(fields=['child', 'check_in']),
        models.Index(fields=['recorded_by', 'check_in']),
    ]
```

#### For Sage Queries
`sage/models.py` — Meal model:
```python
class Meta:
    indexes = [
        models.Index(fields=['date', 'meal_type']),
    ]
```

---

## 9. Connection Pool Configuration

### Current State
**Assessment**: MISSING
- ❌ `CONN_MAX_AGE` not configured in DATABASES
- ❌ No `django-db-connection-pool` package in requirements.txt
- ❌ No pgbouncer mentioned in docker-compose.yml

### Impact
- Each request may create new database connection
- Connection overhead increases with request volume
- In production (Gunicorn 3 workers), can create 3+ simultaneous connections

### Recommendation for Production
Add to `materalleapp/settings.py`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        # ... existing config ...
        "CONN_MAX_AGE": 600,  # 10 minutes
        "OPTIONS": {
            "connect_timeout": 10,
        }
    }
}
```

Or for higher concurrency, add pgbouncer to docker-compose.yml.

---

## 10. Transaction Management

### Current State
**Assessment**: MISSING
- ❌ `ATOMIC_REQUESTS` not configured
- ⚠️ Individual view functions use `@transaction.atomic()` decorator sporadically

### Assessment
`enroll/views.py` line 15 imports `transaction`, but no global atomic request handling.

**Recommendation**:
For critical operations (enrollment, meal attendance), keep explicit transaction handling:
```python
@transaction.atomic
def enroll_student(request):
    ...
```

For less critical views, consider adding:
```python
DATABASES = {
    "default": {
        # ...
        "ATOMIC_REQUESTS": True,  # Wrap each request in transaction
    }
}
```

---

## 11. Admin Panel Database Access

### Assessment: STANDARD DJANGO ADMIN
- ✅ `django.contrib.admin` properly configured in INSTALLED_APPS
- ✅ Models (Student, Child, etc.) appear to be registered with admin
- ✅ Default Django admin queries are automatically optimized (bulk operations)

### Potential Concern
- ⚠️ **MANY FIELDS**: Student model has 40+ fields; admin list view may be slow
- **Recommendation**: Add ModelAdmin class with `list_display` and `search_fields` limits

---

## 12. Dockerfile Issues

### Current Setup
**File**: `Dockerfile`

**ISSUE**: Duplicate FROM statements
- Lines 1-27: First complete Dockerfile (Python setup + dependencies)
- Lines 28-58: Duplicate Dockerfile definition (Python 3.11-slim again)

**Analysis**:
```dockerfile
FROM python:3.11-slim         # Lines 1
# ... build + install ...
EXPOSE 8000
CMD [...]

FROM python:3.11-slim         # Lines 29 - DUPLICATE
# ... build + install again ...
```

**Impact**: Multi-stage build likely intended but incorrectly merged
- Only the final `FROM` is used (lines 29-58)
- First 27 lines are wasted
- Correct approach: Use AS alias for multi-stage builds

**Recommendation**:
Remove lines 1-27, or refactor to:
```dockerfile
FROM python:3.11-slim AS builder
# Build stage

FROM python:3.11-slim AS runtime
# Runtime stage (copy from builder)
```

---

## Summary: Issues by Severity

### 🔴 CRITICAL
1. **Exposed Secrets**: `.env` checked into git with API keys
2. **Weak SECRET_KEY**: Uses `django-insecure-` prefix
3. **Dockerfile Duplication**: Wasted layer, unclear intent

### 🟡 HIGH
1. **No Connection Pooling**: Production scalability risk
2. **No S3 Configuration**: Storage not ready despite packages installed
3. **Missing Health Check**: Docker db container may not be ready
4. **No Query Optimization**: N+1 risk in frequently-used views

### 🟠 MEDIUM
1. **No Database Indexes**: Performance degradation as data grows
2. **Multi-Table Inheritance**: Extra JOIN overhead for Child queries
3. **AutoField vs BigAutoField**: Edge case, but not Django standard
4. **Missing CORS Security**: `CORS_ALLOW_ALL_ORIGINS = True`

### 🔵 LOW
1. **DEBUG=True in .env**: Should be False in production
2. **Unsecured SQLite fallback**: If used in production, lacks encryption
3. **Incomplete transaction management**: ATOMIC_REQUESTS not set

---

## Recommendations Summary

| Priority | Action | File | Est. Effort |
|----------|--------|------|------------|
| CRITICAL | Move .env to .gitignore, rotate API keys | .gitignore | 5 min |
| CRITICAL | Generate new SECRET_KEY (50+ chars) | .env | 5 min |
| HIGH | Configure S3 storage for production | materalleapp/settings.py | 30 min |
| HIGH | Add connection pooling (CONN_MAX_AGE or pgbouncer) | materalleapp/settings.py, docker-compose.yml | 20 min |
| HIGH | Add database health check to docker-compose.yml | docker-compose.yml | 10 min |
| MEDIUM | Add database indexes to models | enroll/models.py, sage/models.py | 30 min |
| MEDIUM | Add select_related/prefetch_related to views | enroll/views.py, sage/views.py | 40 min |
| MEDIUM | Fix Dockerfile (remove duplication) | Dockerfile | 10 min |
| LOW | Enable HTTPS settings for production | materalleapp/settings.py | 15 min |
| LOW | Document SQLite fallback usage | materalleapp/settings.py (comments) | 5 min |

---

## Verification Steps Completed

- ✅ Read all settings files
- ✅ Inspected database configuration (DATABASES, env vars)
- ✅ Reviewed Student/Child model structure and migrations
- ✅ Checked Docker configuration against Django settings
- ✅ Analyzed query patterns in views
- ✅ Verified migration status (`showmigrations` output)
- ✅ Ran `python manage.py check` (passed, with 6 security warnings)
- ✅ Examined requirements.txt for database packages
- ✅ Checked for S3/storage configuration (missing)

**No code changes were made.** This is a research report only.
