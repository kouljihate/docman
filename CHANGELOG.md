# Changelog

All notable changes to Document Manager are recorded here.
The version is defined once in `backend/config.py` (`VERSION`) and follows
[Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [3.21.3] - 2026-11-26

### Added
- **`backend/scripts/`**: one operational script per user-management request,
  runnable inside the stack. `add_users.py` creates accounts of a given role
  (`local_employee`, `customer`, `local_admin`) for one company or all of them,
  with a fixed count or a range such as `3-7`. `remove_users.py` removes the
  accounts of a role, cascading a customer's affairs, activities,
  notifications, documents and payments. Both preview with `--dry-run` and
  apply with `--yes`, and share their name, username and cascade helpers in
  `_common.py`.

## [3.21.2] - 2026-11-26

### Added
- **`delete_customers.py`**: removes every customer account together with its
  cascaded data (affairs, the activities and notifications generated from them,
  documents and payments), mirroring the per-customer delete endpoint.
  `--dry-run` previews the counts; `--yes` applies the removal.

## [3.21.1] - 2026-11-26

### Added
- **`seed_employees.py`**: tops every company up to a deterministic 3-7
  `local_employee` accounts (Moroccan names, unique usernames and e-mails,
  default password `looklook`). Companies that already have enough employees
  are skipped, so re-running is safe; `--dry-run` previews the plan.

## [3.21.0] - 2026-11-26

### Added
- **PG-AFFAIRS edit and delete buttons on the platform view**: every row of the
  platform administrator's affairs table now has circular *Edit* and *Delete*
  buttons in the Actions column, in addition to the local admin's own view. The
  edit dialog loads its customers, services and assignees from the affair's own
  company, so the platform admin never sees another tenant's catalogue.

## [3.20.1] - 2026-11-25

### Changed
- **PG-AUDIT confirmation uses an in-app modal**: the Clean button no longer
  relies on the browser's `confirm()` prompt. It opens a Bootstrap modal with
  the warning text and Cancel / Clean actions, so the confirmation matches the
  rest of the UI and is localized.

## [3.20.0] - 2026-11-25

### Added
- **PG-AUDIT card header with a Clean button**: the audit trail card now has a
  header whose right side holds a *Clean* button. It asks for confirmation, then
  calls the new `DELETE /api/audit/logs` endpoint (main administrator only) to
  delete the platform-wide audit entries and refreshes the table.

## [3.19.2] - 2026-11-25

### Fixed
- **PG-LOGIN shows the error for wrong credentials**: the client dropped the
  login endpoint's own `401` and redirected to `/login`, so the alert never
  appeared. `apiRequest` now skips the session-expiry redirect for sign-in
  (`skipAuthRedirect`), and the page displays the server message with the
  localized "Invalid username or password" fallback, focusing the password
  field.

## [3.19.1] - 2026-11-25

### Fixed
- **Seeded companies now get a logo**: each demo tenant receives a branded SVG
  monogram data URL (initials of the two meaningful name words, Moroccan
  palette), so the header, footer and companies table show a logo instead of the
  placeholder icon. `seed_companies.py` stores it in the `logo` field.

## [3.19.0] - 2026-11-25

### Added
- **`seed_companies.py` creates realistic demo tenants**: 100 curated Moroccan
  company names (logistics, BTP, IT, accounting, agro-food, textile, real
  estate, medical, tourism, …) with matching legal information, address, city,
  region, postal code, contact e-mail and website (slug-based `.ma` domain, so
  every company is unique). Companies named after a city are based there.
- Each seeded company gets a **local admin** with a Moroccan full name, a unique
  `initial.lastname` username, its own e-mail and the default password
  `looklook` (one bcrypt hash is reused: the password is the same by design).
  `--delete` removes the seeded companies and their documents.

## [3.18.0] - 2026-11-25

### Changed
- **Companies page paginated** (25 rows per page): `GET /api/companies/` now
  accepts `page`, `per_page` (max 200) and `q`, and returns
  `{items, page, per_page, total, pages}`. The table renders a server-side pager
  using the existing pagination styles, and the client-side table paginator
  skips tables marked `data-server-pagination`. Search is escaped before it is
  used as a regex.
- **Company counters in one aggregation**: the six per-row counters (local
  admins, employees, customers, affairs, documents, tasks) are now computed by a
  single `$lookup` aggregation for the whole page instead of six
  `count_documents` calls per company, so listing 100+ tenants no longer runs
  hundreds of queries.

## [3.17.1] - 2026-11-24

### Added
- **`seed_companies.py`**: creates a batch of clearly named test companies
  (`Test Company 001` … `Test Company 100` by default, with Moroccan legal and
  contact fields), skips names that already exist so it can be re-run, and
  supports `--count`, `--prefix`, `--dry-run` and `--delete` (which removes the
  prefixed companies together with every document carrying their
  `company_id`).

## [3.17.0] - 2026-11-24

### Added
- **Payments module** (`PG-PAYMENTS`, `/payments`) for local admins only: a
  per-customer payment list (amount, currency, due date, method, notes, status)
  with create / edit dialog, one-click **mark as paid**, delete confirmation and
  a status filter. Pending payments past their due date are flagged **Overdue**.
- `GET|POST /api/payments/`, `GET|PUT|DELETE /api/payments/<id>`, scoped to the
  caller's company and restricted to `local_admin`.
- **Due-payment alert on the dashboard**: local admins see how many payments are
  due within seven days and how many are overdue, with a link to `/payments`
  (`payments_due_count` / `payments_overdue_count` in `/api/dashboard/stats`).

## [3.16.0] - 2026-11-24

### Added
- **Share, Copy and Screenshot actions** in the page-info dialog header, next
  to its close button. Share uses the native share sheet (falling back to the
  clipboard), Copy puts the page id, title, route, URL and summary on the
  clipboard, and Screenshot saves the dialog as a `page-info-<ID>.png` image
  (via html2canvas). New `share`, `copy`, `screenshot`, `copied`,
  `screenshot_saved` and `action_failed` translations in EN / عربي / FR.

## [3.15.1] - 2026-11-24

### Changed
- The page-id badge's dialog no longer repeats a `Page information` heading:
  its title is now the info icon plus the page id (for example `PG-TASKS`), and
  the dialog is registered as **Page details**.

## [3.15.0] - 2026-11-24

### Added
- **Affairs page for the platform admin** (`PG-AFFAIRS`): a read-only list of
  every company's affairs with a **Company** column, reachable from the sidebar
  and from the dashboard, and filterable per company with
  `/affairs?company=<id>`.
- **Affairs counter per company** in the Companies table; it links to that
  company's affairs (`GET /api/companies/` gains `affairs_count`).
- `GET /api/affairs/?company_id=<id>` for the platform admin, and `company_id`
  / `company_name` on every affair response.

### Changed
- The dashboard no longer merges the two entities into one "Companies Affairs"
  card: **Companies** and **Affairs** are separate KPI cards, each linking to
  its own page (the Companies card is only shown to the platform admin).

## [3.14.1] - 2026-11-24

### Changed
- The right-hand page badge of the shared footer now shows only the page id
  (for example `PG-LOGIN`, `PG-TASKS`); the `Page Information` label was
  removed on every page. The badge still opens the page-info dialog.

## [3.14.0] - 2026-11-24

### Changed
- The middle column of the shared footer is now icon-only: a gear that opens a
  **Settings** dialog to pick the interface language (EN / عربي / FR) and a
  database icon that reports the connection state by colour — orange while the
  health check runs, green when connected, red when disconnected.

### Added
- `#settingsModal` in `base.html`, so the language form (`GET /set-language`)
  is reachable from every page, including the sign-in and registration
  screens. Registered as `MDL-SETTINGS` in the page catalogue.

## [3.13.0] - 2026-11-23

### Added
- **Edit** action on every row of the Companies page (`PG-COMPANIES`): the
  shared company dialog now opens in edit mode with the tenant's profile
  pre-filled and saves through `PUT /api/companies/<id>`. The first local
  admin block stays create-only.

### Changed
- The action column of the Companies table uses circular icon buttons, like
  the Users and Customers tables.

## [3.12.0] - 2026-11-23

### Added
- The dashboard opens with a **Companies Affairs** counter card, placed before
  the services / users / customers / activities cards. It counts every affair
  visible to the signed-in profile (their company, or all companies for the
  platform admin) and links to `/affairs` (local admin) or `/companies`
  (platform admin). `GET /api/dashboard/stats` now returns `affairs_count`.

### Changed
- The five KPI cards share one equal-width row on large screens and wrap two
  per row on phones.

## [3.11.0] - 2026-11-23

### Added
- A shared application footer on **every** page (dashboard layouts and the
  sign-in / registration screens), always split into three columns:
  - left: application / company name, social icons and legal identifiers;
  - middle: settings — the EN / عربي / FR language switcher and a live
    database status pill fed by `GET /api/health`;
  - right: two rounded badges, **Page Information** (opens the page dialog)
    and the running **version**.

### Changed
- `GET /set-language?lang=<code>&next=<path>` stores the language cookie and
  returns to the current page, so the footer switcher works everywhere (it
  used to exist only on the sign-in card). `next` is restricted to local
  paths.
- The sign-in / registration language follows the saved cookie.
- Both footer badges use pill-shaped corners.

## [3.10.1] - 2026-11-23

### Changed
- The **Affaires** menu entry now sits directly after **Dashboard** in the
  local admin navigation, so the affairs list is the first entry after the
  dashboard.

## [3.10.0] - 2026-11-23

### Added
- `backend/app/page_registry.py` catalogues every page and dialog with a
  stable identifier: pages use `PG-...` ids keyed by Flask endpoint (route,
  template, roles, summary, features, modals and API endpoints), dialogs use
  `MDL-...` ids keyed by their DOM element id.
- Every page footer now shows the id of the page as a small badge (right side
  of the dashboard footer and of the sign-in/registration card). Clicking it
  opens a **Page information** dialog listing the page id, title, route,
  template, roles, features, every modal/panel on the page with its id and
  purpose, and the API endpoints it calls. The id is also exposed as
  `<meta name="page-id">`.
- `tests/test_page_registry.py` checks that every registered page maps to a
  real Flask endpoint, that ids are unique, that each page's modals exist in
  its template and that the badge renders with the right id.

## [3.9.3] - 2026-11-22

### Changed
- The loading overlay no longer uses the old animated GIF. It now shows a
  frosted card with a gradient ring spinner and the translated "Loading"
  caption, drawn in SVG/CSS so it stays sharp on every screen and respects
  `prefers-reduced-motion`. `static/img/loader.gif` was removed.

## [3.9.2] - 2026-11-22

### Fixed
- Service Management showed a task count per service but its expanded
  **Tasks** panel always said "No tasks found": `GET /api/tasks/` did not
  return `service_id`, which the panel uses to group tasks by service. Task
  responses now include `service_id` (and `assigned_to`).

## [3.9.1] - 2026-11-22

### Changed
- Task list actions are now **Edit** and **Delete**: the eye button was replaced
  by a pencil that opens an edit dialog for the task title, description and
  status (saved through `PUT /api/tasks/<id>`), and Delete stays available to
  local admins. Clicking the row still opens the task details.

## [3.9.0] - 2026-11-22

### Added
- Every affair now carries a readable reference built as `A` + `YYMMDD` +
  `-` + `HHMM`, e.g. `A261122-1930`, generated when the affair is created and
  unique inside the company (a second affair opened in the same minute moves to
  the next free minute).
- `backend/migrate_affair_references.py` backfills references on existing
  affairs from their creation time; it skips affairs that already have one.
- The affairs table shows an **Affair ID** column, the edit dialog shows the
  reference read-only, the activities list shows the reference next to the
  affair name and the customer space shows it before the affair name.

## [3.8.1] - 2026-11-22

### Added
- `backend/app/utils/task_title.py`: extracts a short title from a long task
  sentence (first clause, cut at a word boundary, trailing articles and
  prepositions trimmed).
- `backend/migrate_task_titles.py`: applies that extraction to every task row,
  moves the full original title into the description and leaves tasks with an
  already short title untouched. Supports `--dry-run`, `--company` and
  `--max-chars`, and is idempotent.

### Changed
- Task rows now show a short label in the title column, with the complete
  sentence kept in the description (also used by the activity task lists).

## [3.8.0] - 2026-11-22

### Added
- "Affaires" menu entry for local admins: a single page listing every
  affair of the company with its customer, services, assignee and generated
  activity counters.
- An affair can now attach services and an assignee (employee or local
  manager). Saving it generates one activity per service, carrying that
  service's tasks, and notifies the assignee.
- `POST /api/affairs/<id>/activities` generates the missing activities of an
  affair on demand and is idempotent (already-generated services are kept).
- `GET /api/users/assignees` lists the active employees and local managers
  who can receive activities.

### Changed
- Activity creation accepts a local manager as assignee, not only an
  employee, and can link the activity to its parent affair.
- The activities list shows the parent affair under the activity title.
- Deleting an affair deletes the activities and notifications it generated.

## [3.7.2] - 2026-11-22

### Added
- `test/seed_services_tasks.py`: seeds the six service lines (conseil
  juridique, conseil fiscal, organisation entreprise, étude, domiciliation,
  recouvrement des créances) with their main tasks (36 tasks, six per
  service) in the selected company. It is idempotent, matches services by
  name regardless of case, reuses a local admin as task author and supports
  `--company` and `--dry-run`.

## [3.7.1] - 2026-11-22

### Changed
- Customer list: the "Customer Since" column is removed, leaving the table
  with name, CIN, email, phone, affairs, status, tasks and actions.

## [3.7.0] - 2026-11-22

### Added
- Client-side table pagination: every table whose body holds more than
  10 rows now shows a Bootstrap pagination bar (previous / next / page
  numbers, plus a "showing x–y of n" summary) and displays 10 rows per
  page. It applies to all list pages (customers, companies, users,
  services, documents, tasks, activities, audit, affairs, notifications,
  requests and the detail tables) and re-pages automatically when a page
  script re-renders its table. Labels are translated in EN, Arabic and
  French.

## [3.6.3] - 2026-11-22

### Added
- Global loading overlay: a centred animated GIF (`static/img/loader.gif`)
  fades in on the initial page load, on every link navigation and form
  submit, and for the whole life of any `fetch()` request, then fades out
  when loading finishes. Concurrent requests are counted so the overlay
  stays up until the last one completes.

## [3.6.2] - 2026-11-20

### Added
- `test/generate_customers.py`: bulk customer seeding tool with Moroccan
  names, phones and CINs. It posts to `POST /api/customers/bulk` as a local
  admin, or writes the same documents directly (`--via mongo`) when no
  local-admin password is available; supports `--count`, `--dry-run` and
  `--company` (database `cse` was seeded with 100 customers).

## [3.6.1] - 2026-11-20

### Fixed
- The Create Company (and company setup) dialog no longer grows past the
  screen: its form is now the scrolling flex column, so the body scrolls inside
  the viewport and the footer buttons stay visible.

## [3.6.0] - 2026-11-20

### Added
- Every modal now has the trianglify artwork as its background. Each time a
  modal opens, its header, body and footer are given three different images
  from the bundled set, under a white veil so forms stay readable.

## [3.5.2] - 2026-11-20

### Changed
- The navigation sidebar (desktop and mobile offcanvas) now uses the same
  random trianglify backdrop as the page, under a translucent blue veil so the
  menu stays legible.

## [3.5.1] - 2026-11-20

### Changed
- Hovering the database icon on the sign-in and registration pages now shows
  the live connection state ("Database: connected" / "Database: disconnected")
  instead of the generic "Database Status" label, translated for EN/AR/FR.

## [3.5.0] - 2026-11-20

### Added
- Self-hosted default fonts: Comfortaa (300/400/700) for Latin text and
  VIP-Rawy (400/700) for Arabic, loaded from `/static/fonts` instead of Google
  Fonts.
- Random trianglify backdrop on every page: one of the ten bundled images in
  `/static/img` is chosen on each load and shown behind a light veil, with the
  sign-in card using a translucent overlay so it stays readable.

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
