import mimetypes
import os
import sys
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import quote, urlencode

from flask import Flask, make_response, redirect, render_template, request
from flask_jwt_extended import JWTManager, decode_token

from app.page_registry import catalogue_summary, page_info as lookup_page_info
from app.socketio_server import socketio
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    MAIN_ADMIN,
    normalize_role,
)
from app.translations import t as translate
from config import VERSION, settings

# The self-hosted fonts are TrueType files; some platforms map .ttf to
# application/octet-stream, which browsers may refuse to load.
mimetypes.add_type("font/ttf", ".ttf")

jwt = JWTManager()


def _app_root():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "app")
    return os.path.dirname(os.path.abspath(__file__))


def current_user():
    """Return the logged-in user document, or None."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        decoded = decode_token(token)
        from bson import ObjectId

        from app.database import get_db

        return get_db().users.find_one({"_id": ObjectId(decoded["sub"])})
    except Exception:
        return None


def login_required_page(view):
    """Send anonymous visitors to the login page instead of rendering a shell."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            target = request.path
            if request.query_string:
                target += "?" + request.query_string.decode()
            return redirect("/login?next=" + quote(target, safe="/?=&"))
        return view(*args, **kwargs)
    return wrapper


def page_roles(*allowed):
    """Require a signed-in user whose (normalized) role is in `allowed`."""
    def decorator(view):
        @wraps(view)
        @login_required_page
        def wrapper(*args, **kwargs):
            user = current_user()
            if normalize_role(user.get("role")) not in allowed:
                return render_template("forbidden.html", active_page=""), 403
            return view(*args, **kwargs)
        return wrapper
    return decorator


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(_app_root(), "templates"),
        static_folder=os.path.join(_app_root(), "static"),
        static_url_path="/static",
    )
    app.secret_key = settings.jwt_secret_key

    app.config["JWT_SECRET_KEY"] = settings.jwt_secret_key
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = settings.jwt_access_token_expires
    app.config["MONGO_URI"] = settings.mongo_uri
    # The session token lives in an HttpOnly cookie. Bearer headers stay
    # accepted so existing API clients keep working.
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token"
    app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_COOKIE_SECURE"] = settings.cookie_secure
    # SameSite=Lax plus a same-origin app covers CSRF, and the double-submit
    # header would need client changes on every mutating request.
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False

    jwt.init_app(app)

    from app.routes.activities import activities_bp
    from app.routes.affairs import affairs_bp
    from app.routes.audit import audit_bp
    from app.routes.auth import auth_bp
    from app.routes.companies import companies_bp
    from app.routes.company import company_bp
    from app.routes.customers import customers_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.documents import documents_bp
    from app.routes.reports import reports_bp
    from app.routes.requests import requests_bp
    from app.routes.services import services_bp
    from app.routes.tasks import tasks_bp
    from app.routes.users import users_bp

    for blueprint in (
        auth_bp,
        users_bp,
        companies_bp,
        affairs_bp,
        services_bp,
        tasks_bp,
        dashboard_bp,
        reports_bp,
        audit_bp,
        customers_bp,
        activities_bp,
        requests_bp,
        documents_bp,
        company_bp,
    ):
        app.register_blueprint(blueprint)

    @app.context_processor
    def inject_globals():
        lang = request.args.get("lang") or request.cookies.get("lang") or "en"
        if lang not in ("en", "ar", "fr"):
            lang = "en"

        def _(key):
            return translate(key, lang)

        user = current_user()
        if user is not None:
            # Older records/tokens may still say "admin"/"employee".
            user["role"] = normalize_role(user.get("role"))

        user_id = str(user["_id"]) if user else None

        # Where the footer language switcher returns to: the current page,
        # keeping every query argument except the language itself.
        footer_next = request.path
        if request.args:
            remaining = [(k, v) for k, v in request.args.items(multi=True) if k != "lang"]
            if remaining:
                footer_next += "?" + urlencode(remaining)

        company = None
        if user is not None:
            try:
                from app.database import get_db

                db = get_db()
                if user.get("company_id"):
                    company = db.companies.find_one({"_id": user["company_id"]})
                elif normalize_role(user.get("role")) == MAIN_ADMIN:
                    # Platform header falls back to the legacy settings
                    # document so the product name still renders.
                    company = db.company_settings.find_one()
            except Exception:
                company = None

        return dict(
            _=_,
            lang=lang,
            user=user,
            user_role=normalize_role(user.get("role")) if user else None,
            user_id=user_id,
            now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            version=VERSION,
            company=company,
            footer_next=footer_next,
            # Catalogue entry of the page being rendered (None for API routes),
            # used by the footer page-id badge and its information dialog.
            page_info=lookup_page_info(request.endpoint),
            page_catalogue=catalogue_summary(),
        )

    # ── Web Routes ──────────────────────────────────────────

    @app.route("/")
    def index():
        return redirect("/login")

    @app.route("/login")
    def login_page():
        if current_user() is not None:
            return redirect("/dashboard")
        lang = request.args.get("lang") or request.cookies.get("lang") or "en"
        if lang not in ("en", "ar", "fr"):
            lang = "en"
        nxt = request.args.get("next", "")
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = ""
        company = None
        try:
            from app.database import get_db

            company = get_db().company_settings.find_one()
        except Exception:
            pass
        resp = make_response(render_template("login.html", lang=lang, company=company, next_url=nxt))
        resp.set_cookie("lang", lang, max_age=365 * 24 * 3600)
        return resp

    @app.route("/register")
    def register_page():
        lang = request.args.get("lang") or request.cookies.get("lang") or "en"
        if lang not in ("en", "ar", "fr"):
            lang = "en"
        company = None
        try:
            from app.database import get_db

            company = get_db().company_settings.find_one()
        except Exception:
            pass
        resp = make_response(render_template("register.html", lang=lang, company=company))
        resp.set_cookie("lang", lang, max_age=365 * 24 * 3600)
        return resp

    @app.route("/set-language")
    def set_language():
        """Footer language switcher: remember the choice, then come back."""
        lang = request.args.get("lang", "en")
        if lang not in ("en", "ar", "fr"):
            lang = "en"
        nxt = request.args.get("next", "/dashboard")
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = "/dashboard"
        resp = make_response(redirect(nxt))
        resp.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax")
        return resp

    @app.route("/dashboard")
    @login_required_page
    def dashboard_page():
        role = normalize_role((current_user() or {}).get("role"))
        if role == LOCAL_EMPLOYEE:
            return redirect("/employee-dashboard")
        if role == CUSTOMER:
            return redirect("/my-space")
        return render_template("dashboard.html", active_page="dashboard")

    @app.route("/companies")
    @page_roles(MAIN_ADMIN)
    def companies_page():
        return render_template("companies.html", active_page="companies")

    @app.route("/my-space")
    @page_roles(CUSTOMER)
    def my_space_page():
        from bson import ObjectId

        from app.database import get_db

        db = get_db()
        me = current_user()
        affairs = list(db.affairs.find({"customer_id": me["_id"], "company_id": me.get("company_id")}).sort("name", 1))
        activities = list(
            db.activities.find({"customer_id": me["_id"], "company_id": me.get("company_id")})
            .sort("created_at", -1)
            .limit(20)
        )
        return render_template(
            "my_space.html", active_page="my_space", affairs=affairs, activities=activities
        )

    @app.route("/tasks")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def tasks_page():
        return render_template("tasks.html", active_page="tasks")

    @app.route("/tasks/create")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def task_create_page():
        return render_template("task_create.html", active_page="tasks")

    @app.route("/affairs")
    @page_roles(MAIN_ADMIN, LOCAL_ADMIN)
    def affairs_page():
        return render_template("affairs.html", active_page="affairs")

    @app.route("/services")
    @page_roles(LOCAL_ADMIN)
    def services_page():
        return render_template("services.html", active_page="services")

    @app.route("/users")
    @page_roles(MAIN_ADMIN, LOCAL_ADMIN)
    def users_page():
        return render_template("users.html", active_page="users")

    @app.route("/reports")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def reports_page():
        return render_template("reports.html", active_page="reports")

    @app.route("/audit")
    @page_roles(MAIN_ADMIN)
    def audit_page():
        return render_template("audit.html", active_page="audit")

    @app.route("/activities")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def activities_page():
        return render_template("activities.html", active_page="activities")

    @app.route("/notifications")
    @login_required_page
    def notifications_page():
        return render_template("notifications.html", active_page="notifications")

    @app.route("/employee-dashboard")
    @page_roles(LOCAL_EMPLOYEE)
    def employee_dashboard_page():
        return render_template("employee_dashboard.html", active_page="employee_dashboard")

    @app.route("/messaging")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def messaging_page():
        return render_template("messaging.html", active_page="messaging")

    @app.route("/customers")
    @page_roles(LOCAL_ADMIN)
    def customers_page():
        return render_template("customers.html", active_page="customers")

    @app.route("/customers/<customer_id>")
    @page_roles(LOCAL_ADMIN)
    def customer_detail_page(customer_id):
        return render_template("customer_detail.html", active_page="customers", customer_id=customer_id)

    @app.route("/requests")
    @login_required_page
    def requests_page():
        return render_template("requests.html", active_page="requests")

    @app.route("/documents")
    @page_roles(LOCAL_ADMIN, LOCAL_EMPLOYEE)
    def documents_page():
        return render_template("documents.html", active_page="documents")

    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    @app.route("/api/health")
    def health():
        from app.database import get_db

        try:
            get_db().command("ping")
            return {"status": "ok", "db": "connected", "version": VERSION}
        except Exception:
            return {"status": "error", "db": "disconnected", "version": VERSION}, 503

    return app
