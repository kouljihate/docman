# AGENTS.md — Document Manager

Project instructions for AI agents and contributors working in this repository.

## Standing rule: version every change and push it

At the end of **every** user request in this repository:

1. **Bump the version** (Semantic Versioning, `MAJOR.MINOR.PATCH`):
   - `PATCH` — bug fixes, small UI/text tweaks, docs or tooling changes.
   - `MINOR` — new features or endpoints, backwards compatible.
   - `MAJOR` — breaking changes: rebrands, data/schema or API incompatibilities.
2. **Update every place the version appears** (they must match):
   - `backend/config.py` → `VERSION` (single source of truth; shown in the UI
     badge and in `GET /api/health`).
   - `Dockerfile` → `ARG APP_VERSION=<version>`.
   - `docker-compose.yml` → `image: document-manager:${APP_VERSION:-<version>}`.
3. **Add a `CHANGELOG.md` entry** under the new version with the date and a
   short `Added` / `Changed` / `Fixed` summary.
4. **Commit** the change together with the version bump, with a message that
   describes why the change was made.
5. **Tag and push**: create annotated tag `v<version>` and push both the branch
   and the tag to `origin` (`master`):

   ```bash
   git tag -a v<version> -m "Document Manager <version>"
   git push origin master
   git push origin v<version>
   ```

Do not leave a request committed but unpushed, or pushed without its version
bump and tag.

## Running the app

- Cloud database: copy `.env.example` to `.env`, set `MONGO_URI` to the Atlas
  connection string (keep the `/cse` database name in the path), then
  `docker compose up --build` → http://localhost:5000. Percent-encode special
  characters in the password (`@` → `%40`) and quote the value, or an unquoted
  `&` in the query string breaks shell sourcing of `.env`.
- Bundled local MongoDB: `docker compose --profile local-db up --build` (no
  `.env` needed; the `mongo` service is an opt-in `local-db` profile). Stop it
  with `docker compose --profile local-db down`.
- Optional default admin: `docker compose exec app python seed.py` (`admin` / `admin123`)
- Version check: `curl http://localhost:5000/api/health` → `{"status":"ok","db":"connected","version":"..."}`

To move existing local data into a cloud database, keep the local stack up and
run the copy script (target from `MONGO_TARGET_URI` or `--target`):

```bash
docker compose --profile local-db up -d
docker compose exec app python copy_to_atlas.py --target "mongodb+srv://.../cse" --dry-run
docker compose exec app python copy_to_atlas.py --target "mongodb+srv://.../cse" --yes
```

It copies every collection and its indexes, refusing to overwrite a non-empty
target unless `--drop` (replace) or `--append` is passed. Uploaded files in
`backend/documents/` are not part of the copy.

## Tests

Tests use pytest with an in-memory MongoDB (`mongomock`), so no database is
needed. Inside a running stack:

```bash
docker compose exec -T app sh -c "pip install -q -r requirements-dev.txt"
docker compose exec -T app python -m pytest -q tests
```

`requirements-dev.txt` holds the test-only dependencies and `tests/` is excluded
from the Docker build context.

## Multi-company model

The app is multi-tenant. Roles (`backend/app/tenancy.py`):

| Profile | Scope |
| --- | --- |
| `main_admin` | Platform: companies, all users of every company (local admins, employees, customers), global dashboard, audit logs |
| `local_admin` | One company: customers, services, documents, tasks, activities, employees, messaging, reports, notifications, requests |
| `local_employee` | One company: tasks, activities, documents, reports, messaging, notifications, requests |
| `customer` | Own affairs/activities; requests go to their own local admin |

Every tenant collection carries `company_id`; API queries must use
`company_scope()` from `app/tenancy.py` and mutations must stamp `company_id`
(via `tenant_fields()`), otherwise data leaks across companies.

After upgrading an existing database run:

```bash
docker compose exec app python migrate_tenancy.py --main-admin admin
```

## Auth model

- The JWT session token is an `HttpOnly`, `SameSite=Lax` cookie; page scripts
  never see it, and API calls need no `Authorization` header.
- Every HTML page is wrapped in `login_required_page`; APIs use `@jwt_required()`.
- The first account registered at `/register` becomes the admin; later public
  registrations are always customers. Admins create staff via `/api/users`.
- Do not expose tokens to `localStorage` or inline JSON responses again.

## Layout

- `backend/` — Flask + Socket.IO backend, Jinja templates, static assets.
- `backend/documents/` — uploaded PDFs (mounted volume in Docker).
- `requests/` — request/screenshot folders written by the request feature.
- `cse_app/` — Flutter mobile client (not deployed by Docker or the web app).
