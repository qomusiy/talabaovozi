from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import jobs, settings_store
from app.audit import AuditMiddleware
from app.config import get_settings
from app.db import session_scope
from app.web import miniapp, survey
from app.web.admin import chats as admin_chats
from app.web.admin import dev as admin_dev
from app.web.admin import manage as admin_manage
from app.web.admin import records as admin_records
from app.web.admin import views as admin_views
from app.web.deps import LoginRequired, is_local_request
from app.web.security import SECURITY_HEADERS, same_origin


async def dashboard_online() -> bool:
    """May the dashboard be opened through the public address? ADMIN_LOCAL_ONLY=false in .env, or the switch on
    the dashboard's Bot page (which can only be turned on from this computer, as it is off until then)."""
    if not get_settings().admin_local_only:
        return True
    async with session_scope() as session:
        return bool(await settings_store.get(session, "admin_online"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await jobs.start()  # timetable auto-sync
    yield
    await jobs.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="Talaba Ovozi", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(AuditMiddleware)  # added first = runs inside the session middleware (it reads the session)
    app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key, session_cookie="admin_session",
                       max_age=12 * 3600, same_site="lax", https_only=False)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    app.include_router(survey.router)
    app.include_router(miniapp.router)
    app.include_router(admin_views.router)
    app.include_router(admin_manage.router)
    app.include_router(admin_records.router)
    app.include_router(admin_dev.router)
    app.include_router(admin_chats.router)

    @app.middleware("http")
    async def protect_admin(request: Request, call_next):
        if not request.url.path.startswith("/admin"):
            return await call_next(request)
        if not is_local_request(request) and not await dashboard_online():
            return PlainTextResponse("Not found", status_code=404)
        if request.method == "POST" and not same_origin(request):
            return PlainTextResponse("Forbidden", status_code=403)
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.exception_handler(LoginRequired)
    async def to_login(request: Request, _exc):
        return RedirectResponse(f"/admin/login?next={request.url.path}", status_code=303)

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/admin")

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        """The tunnel watchdog (scripts/tunnel.sh) checks the public address with this."""
        return PlainTextResponse("ok")

    return app


app = create_app()
