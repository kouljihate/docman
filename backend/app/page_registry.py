"""Stable identifiers for every page and dialog in the web UI.

Every HTML page resolves to one :data:`PAGES` entry (keyed by Flask endpoint)
and carries its ``id`` in the footer as a badge. Clicking that badge opens
``#pageInfoModal`` built from this catalogue, so the route, roles, features,
modals and API endpoints of the page are always one click away.

Modals are keyed by their DOM element id and identified by ``MDL-...``.
"""

# Dialog rendered by ``base.html``: the footer settings icon opens it on every
# page, signed in or not.
BASE_MODALS = ("settingsModal",)

# Dialogs that live in ``dashboard_base.html`` and therefore appear on every
# dashboard-backed page.
SHARED_MODALS = (
    "sidebarOffcanvas",
    "deleteModal",
    "companySetupModal",
    "changePasswordModal",
    "headerSendModal",
)

MODALS = {
    "settingsModal": {
        "id": "MDL-SETTINGS",
        "element": "settingsModal",
        "title": "Settings",
        "purpose": "Opened by the gear icon in the shared footer; picks the interface language and applies it through GET /set-language.",
    },
    "sidebarOffcanvas": {
        "id": "PNL-SIDEBAR",
        "element": "sidebarOffcanvas",
        "title": "Navigation sidebar (mobile)",
        "purpose": "Off-canvas copy of the role-aware navigation for small screens.",
    },
    "deleteModal": {
        "id": "MDL-DELETE",
        "element": "deleteModal",
        "title": "Delete confirmation",
        "purpose": "Shared confirmation shown by every list page before a record is deleted.",
    },
    "companySetupModal": {
        "id": "MDL-COMPANY-SETUP",
        "element": "companySetupModal",
        "title": "Company settings",
        "purpose": "Local admin edits the company profile, legal identifiers, logo and social links.",
    },
    "changePasswordModal": {
        "id": "MDL-CHANGE-PASSWORD",
        "element": "changePasswordModal",
        "title": "Change password",
        "purpose": "Local admin changes their own password through POST /api/auth/change-password.",
    },
    "headerSendModal": {
        "id": "MDL-HEADER-SEND",
        "element": "headerSendModal",
        "title": "Send notification",
        "purpose": "Header paper-plane button: sends an in-app notification to a staff member.",
    },
    "companyModal": {
        "id": "MDL-COMPANY-FORM",
        "element": "companyModal",
        "title": "Create / edit company",
        "purpose": "Main admin creates a tenant together with its first local admin, or edits an existing company's profile (the admin block is create-only).",
    },
    "userModal": {
        "id": "MDL-USER-FORM",
        "element": "userModal",
        "title": "Create / edit user",
        "purpose": "Adds a local admin, employee or customer and edits their details, role and company.",
    },
    "viewUserModal": {
        "id": "MDL-USER-VIEW",
        "element": "viewUserModal",
        "title": "User details",
        "purpose": "Read-only profile of a user with their recent activity log.",
    },
    "customerModal": {
        "id": "MDL-CUSTOMER-FORM",
        "element": "customerModal",
        "title": "Create / edit customer",
        "purpose": "Customer identity, CIN, photo ID, contact details and status.",
    },
    "bulkModal": {
        "id": "MDL-CUSTOMER-BULK",
        "element": "bulkModal",
        "title": "Bulk customer import",
        "purpose": "Imports a CSV of customers through POST /api/customers/bulk.",
    },
    "affairModal": {
        "id": "MDL-AFFAIR-FORM",
        "element": "affairModal",
        "title": "Create / edit affair",
        "purpose": "Affair of a customer with its services and assignee; saving generates activities.",
    },
    "serviceModal": {
        "id": "MDL-SERVICE-FORM",
        "element": "serviceModal",
        "title": "Create / edit service",
        "purpose": "Service line with its task list, price and description.",
    },
    "taskDetailModal": {
        "id": "MDL-TASK-DETAIL",
        "element": "taskDetailModal",
        "title": "Task details",
        "purpose": "Description, audit history and quick status buttons for one task.",
    },
    "taskEditModal": {
        "id": "MDL-TASK-EDIT",
        "element": "taskEditModal",
        "title": "Edit task",
        "purpose": "Edits the title, description and status of a task via PUT /api/tasks/<id>.",
    },
    "activityModal": {
        "id": "MDL-ACTIVITY-FORM",
        "element": "activityModal",
        "title": "Create activity",
        "purpose": "New activity for a customer: affair, tasks, assignee and due date.",
    },
    "noteModal": {
        "id": "MDL-ACTIVITY-NOTE",
        "element": "noteModal",
        "title": "Activity note",
        "purpose": "Appends a comment to an activity's timeline.",
    },
    "uploadDocumentModal": {
        "id": "MDL-DOCUMENT-UPLOAD",
        "element": "uploadDocumentModal",
        "title": "Upload document",
        "purpose": "Uploads a PDF and links it to a customer and service.",
    },
    "sendNotificationModal": {
        "id": "MDL-NOTIFICATION-SEND",
        "element": "sendNotificationModal",
        "title": "Send notification",
        "purpose": "Notifications page composer for sending a message to a staff member.",
    },
    "pageInfoModal": {
        "id": "MDL-PAGE-INFO",
        "element": "pageInfoModal",
        "title": "Page information",
        "purpose": "Opened by the Page Information badge in the shared footer; lists everything registered about the page.",
    },
}

PAGES = {
    "login_page": {
        "id": "PG-LOGIN",
        "title": "Sign in",
        "route": "/login",
        "layout": "auth",
        "template": "login.html",
        "roles": ["anonymous"],
        "summary": "Username and password sign-in. On success the session cookie is set and the visitor is sent to the requested page or /dashboard.",
        "features": [
            "Sign-in form (username + password)",
            "Redirect back to the page that required a login",
            "Shared footer: app name, settings icon (language dialog) and tri-state database status icon, Page Information and version badges",
            "Link to the registration page",
        ],
        "modals": [],
        "apis": ["POST /api/auth/login", "GET /api/health", "GET /set-language"],
    },
    "register_page": {
        "id": "PG-REGISTER",
        "title": "Sign up",
        "route": "/register",
        "layout": "auth",
        "template": "register.html",
        "roles": ["anonymous"],
        "summary": "Public registration. The first account on an empty install becomes the platform main admin; every later sign-up joins the selected company as a customer.",
        "features": [
            "Full name, username, email, phone and password form",
            "Company picker fed by /api/companies/public",
            "Bootstrap of the first main admin account",
            "Shared footer: app name, settings icon, database status icon, Page Information and version badges",
        ],
        "modals": [],
        "apis": [
            "GET /api/companies/public",
            "POST /api/auth/register",
            "GET /set-language",
        ],
    },
    "dashboard_page": {
        "id": "PG-DASHBOARD",
        "title": "Dashboard",
        "route": "/dashboard",
        "layout": "dashboard",
        "template": "dashboard.html",
        "roles": ["main_admin", "local_admin"],
        "summary": "Company / platform overview: KPI cards and charts built from the statistics endpoint. Employees and customers are redirected to their own dashboards.",
        "features": [
            "KPI cards (companies affairs, services, users, customers, activities)",
            "Task status and per-service charts",
            "Recent activity feed",
        ],
        "modals": [],
        "apis": ["GET /api/dashboard/stats"],
    },
    "employee_dashboard_page": {
        "id": "PG-EMPLOYEE-DASHBOARD",
        "title": "My dashboard",
        "route": "/employee-dashboard",
        "layout": "dashboard",
        "template": "employee_dashboard.html",
        "roles": ["local_employee"],
        "summary": "Personal workspace for a local employee: counters of their pending, in-progress and completed activities plus unread notifications.",
        "features": [
            "Activity counters by status",
            "Unread notification counter",
            "Shortcuts to tasks, activities and notifications",
        ],
        "modals": [],
        "apis": ["GET /api/dashboard/employee-stats"],
    },
    "companies_page": {
        "id": "PG-COMPANIES",
        "title": "Companies",
        "route": "/companies",
        "layout": "dashboard",
        "template": "companies.html",
        "roles": ["main_admin"],
        "summary": "Tenant management for the platform main admin: create a company with its first local admin, edit its profile, activate or deactivate it and delete a tenant.",
        "features": [
            "Company table with logo, legal identifiers and status",
            "Create company dialog (profile, ICE/RC/IF, contact, social links)",
            "Edit company profile from the circular action buttons of each row",
            "Activate / deactivate and delete a tenant",
        ],
        "modals": ["companyModal"],
        "apis": ["GET /api/companies/", "POST /api/companies/", "PUT /api/companies/<id>", "DELETE /api/companies/<id>"],
    },
    "users_page": {
        "id": "PG-USERS",
        "title": "Users",
        "route": "/users",
        "layout": "dashboard",
        "template": "users.html",
        "roles": ["main_admin", "local_admin"],
        "summary": "User administration. The main admin manages every account of every company; a local admin manages only their own company's employees and customers.",
        "features": [
            "User table with role, status and company filters",
            "Create / edit user dialog (role, company, contact details)",
            "Read-only user profile with recent activities",
            "Tenant scoping through company_scope()",
        ],
        "modals": ["userModal", "viewUserModal"],
        "apis": [
            "GET /api/users/",
            "POST /api/users/",
            "PUT /api/users/<id>",
            "DELETE /api/users/<id>",
            "GET /api/companies/",
            "GET /api/activities/?assigned_to=<id>",
        ],
    },
    "customers_page": {
        "id": "PG-CUSTOMERS",
        "title": "Customers",
        "route": "/customers",
        "layout": "dashboard",
        "template": "customers.html",
        "roles": ["local_admin"],
        "summary": "Customer directory of the current company, with CIN, photo ID, contact details and per-customer affair and task counts.",
        "features": [
            "Searchable customer table with pagination",
            "Create / edit customer dialog (identity, CIN, photo, status)",
            "CSV bulk import",
            "Link to the customer detail page",
        ],
        "modals": ["customerModal", "bulkModal"],
        "apis": ["GET /api/customers/", "POST /api/customers/", "PUT /api/customers/<id>", "DELETE /api/customers/<id>", "POST /api/customers/bulk"],
    },
    "customer_detail_page": {
        "id": "PG-CUSTOMER-DETAIL",
        "title": "Customer detail",
        "route": "/customers/<customer_id>",
        "layout": "dashboard",
        "template": "customer_detail.html",
        "roles": ["local_admin"],
        "summary": "Everything about one customer: profile, photo ID, their affairs and the tasks attached to them.",
        "features": [
            "Customer profile summary",
            "Affairs and tasks of the customer",
            "Back link to the customer list",
        ],
        "modals": [],
        "apis": ["GET /api/customers/<customer_id>", "GET /api/tasks/?customer_id=<customer_id>"],
    },
    "affairs_page": {
        "id": "PG-AFFAIRS",
        "title": "Affairs",
        "route": "/affairs",
        "layout": "dashboard",
        "template": "affairs.html",
        "roles": ["local_admin"],
        "summary": "Affairs of the company, each with a readable reference (A + YYMMDD-HHMM), its customer, services, assignee and generated activity counters.",
        "features": [
            "Affair table with reference, customer, services and assignee",
            "Create / edit affair dialog (services, assignee)",
            "Automatic activity generation per attached service",
        ],
        "modals": ["affairModal"],
        "apis": [
            "GET /api/affairs/",
            "POST /api/affairs/",
            "PUT /api/affairs/<id>",
            "DELETE /api/affairs/<id>",
            "GET /api/customers/",
            "GET /api/services/",
            "GET /api/users/assignees",
        ],
    },
    "services_page": {
        "id": "PG-SERVICES",
        "title": "Services",
        "route": "/services",
        "layout": "dashboard",
        "template": "services.html",
        "roles": ["local_admin"],
        "summary": "Service lines offered by the company. Each service holds its task list, which affairs reuse when they generate activities.",
        "features": [
            "Service cards / table with price and task count",
            "Create / edit service dialog with its tasks",
            "Expandable task panel grouped by service",
        ],
        "modals": ["serviceModal"],
        "apis": ["GET /api/services/", "POST /api/services/", "PUT /api/services/<id>", "DELETE /api/services/<id>", "GET /api/tasks/"],
    },
    "tasks_page": {
        "id": "PG-TASKS",
        "title": "Task management",
        "route": "/tasks",
        "layout": "dashboard",
        "template": "tasks.html",
        "roles": ["local_admin", "local_employee"],
        "summary": "All tasks of the company. Rows open the task detail dialog; the pencil edits the task and local admins can delete it.",
        "features": [
            "Task table with title and description",
            "Task detail dialog with audit history and quick status buttons",
            "Edit dialog (title, description, status)",
            "Delete with confirmation (local admin only)",
        ],
        "modals": ["taskDetailModal", "taskEditModal"],
        "apis": [
            "GET /api/tasks/",
            "GET /api/tasks/<id>",
            "PUT /api/tasks/<id>",
            "DELETE /api/tasks/<id>",
            "GET /api/audit/logs?entity_type=task&entity_id=<id>",
        ],
    },
    "task_create_page": {
        "id": "PG-TASK-CREATE",
        "title": "Create task",
        "route": "/tasks/create",
        "layout": "dashboard",
        "template": "task_create.html",
        "roles": ["local_admin"],
        "summary": "Standalone form for adding a task (title, description, service, assignee and due date) outside an activity.",
        "features": [
            "Task form with service and assignee pickers",
            "Validation and success toast",
        ],
        "modals": [],
        "apis": ["POST /api/tasks/"],
    },
    "activities_page": {
        "id": "PG-ACTIVITIES",
        "title": "Activity management",
        "route": "/activities",
        "layout": "dashboard",
        "template": "activities.html",
        "roles": ["local_admin", "local_employee"],
        "summary": "Activities assigned to staff, linked to their affair, customer and tasks. Local admins create them; employees work on the ones assigned to them.",
        "features": [
            "Activity list with affair reference, assignee and status",
            "Create activity dialog (customer, affair, tasks, assignee)",
            "Note dialog appending to the activity timeline",
        ],
        "modals": ["activityModal", "noteModal"],
        "apis": [
            "GET /api/activities/",
            "POST /api/activities/",
            "PUT /api/activities/<id>",
            "GET /api/customers/",
            "GET /api/tasks/",
            "GET /api/users/?role=employee",
        ],
    },
    "documents_page": {
        "id": "PG-DOCUMENTS",
        "title": "Document management",
        "route": "/documents",
        "layout": "dashboard",
        "template": "documents.html",
        "roles": ["local_admin", "local_employee"],
        "summary": "PDF documents uploaded by the company and linked to a customer and service; customers only reach their own files through the API.",
        "features": [
            "Document table with customer, service and upload date",
            "Upload dialog (PDF + customer + service)",
            "Download and delete per document",
        ],
        "modals": ["uploadDocumentModal"],
        "apis": ["GET /api/documents/", "POST /api/documents/", "GET /api/documents/<id>/download", "DELETE /api/documents/<id>", "GET /api/customers/", "GET /api/services/"],
    },
    "reports_page": {
        "id": "PG-REPORTS",
        "title": "Reports",
        "route": "/reports",
        "layout": "dashboard",
        "template": "reports.html",
        "roles": ["local_admin", "local_employee"],
        "summary": "Server-rendered PDF reports (tasks, services, users) generated with reportlab and downloaded from the API.",
        "features": [
            "Task report PDF",
            "Service report PDF",
            "User report PDF",
        ],
        "modals": [],
        "apis": ["GET /api/reports/tasks", "GET /api/reports/services", "GET /api/reports/users"],
    },
    "audit_page": {
        "id": "PG-AUDIT",
        "title": "Audit logs",
        "route": "/audit",
        "layout": "dashboard",
        "template": "audit.html",
        "roles": ["main_admin"],
        "summary": "Platform-wide audit trail filtered by entity, action and user, refreshed live through the notification socket.",
        "features": [
            "Audit table with actor, action, entity and timestamp",
            "Filters by entity type, action and user",
            "Live refresh on new audit events",
        ],
        "modals": [],
        "apis": ["GET /api/audit/logs"],
    },
    "messaging_page": {
        "id": "PG-MESSAGING",
        "title": "Messaging",
        "route": "/messaging",
        "layout": "dashboard",
        "template": "messaging.html",
        "roles": ["local_admin", "local_employee"],
        "summary": "Bulk WhatsApp messaging: pick customers, write one message and open a pre-filled wa.me conversation for each of them.",
        "features": [
            "Customer picker with select-all",
            "Message composer",
            "One wa.me tab per selected customer with a phone number",
        ],
        "modals": [],
        "apis": ["GET /api/customers/"],
    },
    "notifications_page": {
        "id": "PG-NOTIFICATIONS",
        "title": "Notifications",
        "route": "/notifications",
        "layout": "dashboard",
        "template": "notifications.html",
        "roles": ["main_admin", "local_admin", "local_employee", "customer"],
        "summary": "In-app notifications of the signed-in user, with mark-as-read, mark-all-read and a composer for staff messages.",
        "features": [
            "Notification list with read state",
            "Mark one / mark all as read",
            "Send notification dialog",
        ],
        "modals": ["sendNotificationModal"],
        "apis": [
            "GET /api/activities/notifications",
            "POST /api/activities/notifications/read",
            "GET /api/activities/notifications/unread-count",
            "GET /api/users/?role=employee",
        ],
    },
    "requests_page": {
        "id": "PG-REQUESTS",
        "title": "Request management",
        "route": "/requests",
        "layout": "dashboard",
        "template": "requests.html",
        "roles": ["main_admin", "local_admin", "local_employee", "customer"],
        "summary": "Support / change request form that stores the request with its screenshots and routes it to local admins as a notification.",
        "features": [
            "Request title and content form",
            "Screenshot attachments with preview",
            "Stored folder name returned on success",
        ],
        "modals": [],
        "apis": ["POST /api/requests/"],
    },
    "my_space_page": {
        "id": "PG-MY-SPACE",
        "title": "My space",
        "route": "/my-space",
        "layout": "dashboard",
        "template": "my_space.html",
        "roles": ["customer"],
        "summary": "Customer portal: the customer's own affairs, their latest activities and a shortcut to open a request.",
        "features": [
            "Own affairs with references",
            "Recent activities of the customer",
            "Shortcut to the request form",
        ],
        "modals": [],
        "apis": [],
    },
}


def _resolve(page):
    """Return a page entry with its modal ids expanded to catalogue entries."""
    entry = dict(page)
    ids = list(BASE_MODALS)
    if page["layout"] == "dashboard":
        ids += [modal for modal in SHARED_MODALS if modal not in ids]
    ids += [modal for modal in page["modals"] if modal not in ids]
    entry["modals"] = [MODALS[modal] for modal in ids]
    return entry


def page_info(endpoint):
    """Catalogue entry of a Flask endpoint, or None when it is not a page."""
    page = PAGES.get(endpoint)
    return _resolve(page) if page else None


def catalogue_summary():
    """Counts shown at the bottom of the page-info dialog."""
    return {"pages": len(PAGES), "modals": len(MODALS)}
