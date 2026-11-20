# Changelog

All notable changes to Document Manager are recorded here.
The version is defined once in `backend/config.py` (`VERSION`) and follows
[Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [3.4.1] - 2026-11-20

### Fixed
- Documented how to write the Atlas connection string into `.env`: special
  characters in the password must be percent-encoded (`@` → `%40`) and the
  value quoted, otherwise an unquoted `&` in the query string truncates the
  line when the file is sourced by a shell.

## [3.4.0] - 2026-11-20

### Added
- `.env.example` documenting `MONGO_URI` and the other stack settings, so the
  app can be pointed at a cloud MongoDB (Atlas) without editing the compose
  file.
- `backend/copy_to_atlas.py`: copies every local collection (documents and their
  indexes, `_id` values preserved) into a cloud database, with a dry run, an
  explicit `--yes` gate, `--drop`/`--append` handling for a non-empty target and
  a document-count check afterwards.

### Changed
- The bundled `mongo` service is now an opt-in Compose profile (`local-db`) and
  the app's dependency on it is `required: false`, so the stack can run against
  a cloud database alone: `docker compose up --build` (cloud) versus
  `docker compose --profile local-db up --build` (local).
- `MONGO_URI` in `docker-compose.yml` is now read from the environment
  (`.env`) instead of being hardcoded to the local container.

## [3.3.0] - 2026-11-20

### Added
- Customer creation now records the **CIN** (Moroccan national identity card,
  stored uppercase) and a **photo ID**: the identity document is picked as an
  image, downscaled in the browser and stored with the customer.
- The customers list shows the CIN and a thumbnail, the customer detail page
  shows the CIN and the full photo, and both fields are editable when a customer
  is updated. Bulk customer import accepts a `cin` column and the CSV template
  includes it.

## [3.2.0] - 2026-11-20

### Added
- Company creation now captures the full Moroccan company profile: logo upload,
  legal form (SARL, SARL AU, SA, SAS, SNC, SCS, auto-entrepreneur, association,
  cooperative, branch), ICE (validated as exactly 15 digits), RC (registre de
  commerce), IF (identifiant fiscal), patente, CNSS number, share capital, city,
  region, postal code, country (defaults to Maroc), website and contact details.
- The company settings modal (local admin) edits the same fields and the logo;
  the uploaded logo is shown in the header, the companies list and the ICE is
  shown in the footer.

### Changed
- Logos are picked as image files, downscaled in the browser to 320 px and
  stored as a data URL (max ~650 KB); an http(s) URL is still accepted.
- Company settings now only overwrite the fields that were submitted, so a
  partial save no longer clears the logo or the legal identifiers.

## [3.1.1] - 2026-11-20

### Fixed
- Removed the Company Setup modal that appeared automatically on the login and
  registration pages (and for local admins) when no company record existed. It
  blocked the auth screen on a fresh install, and companies are now created by
  the main admin from the Companies page. The company settings modal itself is
  still available from the user menu.

## [3.1.0] - 2026-11-20

### Added
- The main administrator now has the **Users** page and platform-wide user
  management: list every tenant user across all companies, filter by role,
  status and company, create local admins, employees and customers in any
  company, edit their details/role, move them between companies and delete
  them. Main-admin accounts themselves are not editable from this page.

### Changed
- `/users` and `/api/users` are open to the main admin as well as local admins;
  a local admin still only manages their own company's employees and customers.
- User API responses include `company_id` so the main admin can see which
  company each account belongs to.

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
