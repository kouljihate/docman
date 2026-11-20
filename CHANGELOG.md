# Changelog

All notable changes to Document Manager are recorded here.
The version is defined once in `backend/config.py` (`VERSION`) and follows
[Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [3.0.0] - 2026-11-20

Multi-company (tenant) release with four profiles. **Breaking:** roles are now
`main_admin`, `local_admin`, `local_employee` and `customer`, and every record
belongs to a company.

### Added
- `companies` collection plus a platform API (`/api/companies`) and a
  **Companies** page for the main administrator: create a company together
  with its first local admin, activate/deactivate, delete a tenant.
- Four profiles with enforced permissions:
  - **Main Admin** – company accounts, global dashboard, platform audit logs.
  - **Local Admin** – their company's customers, services, documents, tasks,
    activities, employees, messaging, reports, notifications and requests.
  - **Local Employee** – tasks, activities, documents, reports, messaging,
    notifications and requests.
  - **Customer** – own affairs/activities plus requests routed to their own
    local admin.
- `app/tenancy.py`: shared role helpers, `company_scope()` and role decorators
  applied to every API route.
- `/my-space` customer page, company picker on the public sign-up form, and a
  role-aware navigation built from `_nav.html`.
- `backend/migrate_tenancy.py` to move an existing single-company install to
  the tenant model (default company, legacy roles, backfilled `company_id`).

### Changed
- The first registered account bootstraps the `main_admin`; later public
  sign-ups always join an existing company as a customer.
- Requests are stored as tenant records routed to a local admin (previously a
  folder committed to Git), with in-app notifications.
- Company settings are per company; the main admin manages them through the
  Companies page.

### Fixed
- Cross-tenant data leaks: every query on users, customers, affairs, services,
  tasks, activities, documents, requests, notifications and audit logs is now
  scoped to the caller's company.

## [2.1.2] - 2026-11-20

### Added
- The application footer shows the running version as a badge at the end of
  the footer (right side in LTR, left in RTL), matching the login card badge.

## [2.1.1] - 2026-11-20

### Changed
- The project now lives in the `kouljihate/docman` GitHub repository
  (previously `kouljihate/cse`); the full history and tags were pushed there.

## [2.1.0] - 2026-11-20

Security release fixing the findings from the code review.

### Security
- Public registration can no longer create privileged accounts: the first
  account bootstraps the administrator, every later sign-up is a customer.
- The session token is delivered only as an `HttpOnly` cookie; page scripts no
  longer receive or store it. `COOKIE_SECURE` turns on the `Secure` flag for
  HTTPS deployments.
- Every application page now requires a signed-in user instead of serving its
  shell anonymously.
- Customers can only list, read or download their own documents; staff and
  admin access is unchanged. Invalid document ids return 404, not 500.
- Logout clears the session cookie.

### Added
- `tests/` pytest suite (`requirements-dev.txt`) covering page guards,
  registration roles, cookie flags and document ownership.
- gunicorn serves the app in the Docker image instead of the Werkzeug
  development server.

### Changed
- Bearer tokens are still accepted, so existing API clients keep working.
- Docker image version/tag is 2.1.0.

### Removed
- Unused `weasyprint` dependency (reports are rendered with reportlab),
  dropped from `requirements.txt` and the PyInstaller build.

## [2.0.1] - 2026-11-20

### Added
- `AGENTS.md` documenting the project rule that every change bumps the version,
  updates this changelog and is tagged and pushed to GitHub.

## [2.0.0] - 2026-11-20

### Changed
- Renamed the application from "Global Service & Document Manager" to
  **Document Manager** (UI, page titles, PDF report headers, build scripts).
- New application logo replacing the Cabinet Express Service artwork.
- Default admin email for seeding is now `admin@docmanager.local`.

### Added
- `Dockerfile` and `docker-compose.yml` for local runs (app + MongoDB),
  with persistent volumes for the database, uploaded PDFs and requests.
- `.dockerignore` to keep secrets, virtualenvs and build output out of images.
- `/api/health` now reports the running `version`.
- Docker image is labelled and tagged with the application version.

### Fixed
- `requirements.txt` was missing `email-validator`, which crashed the app on
  a clean install.
- `--db-host` / `MONGO_HOST` had no effect because the MongoDB URI was
  overridden after the database client had already been created.
- Debug mode (and its reloader) was always enabled regardless of `--debug`.
- Binding address is configurable via `--host` (needed for containers).
- Creating a request no longer fails when Git is unavailable; the request is
  saved and a warning is returned instead.

## Earlier releases

- 1.5.0 — Rebrand to Global Service & Document Manager, new features.
- 1.4.0 — Previous feature release.
