"""Routers for serving the PWA and admin static frontends."""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR

router = APIRouter()

STATIC_DIR = BASE_DIR / "app" / "static"


def _serve(relative_path: str) -> FileResponse:
    return FileResponse(STATIC_DIR / relative_path)


@router.get("/", include_in_schema=False)
async def index():
    """Root page redirects to the PWA app."""
    return _serve("app/index.html")


@router.get("/app", include_in_schema=False)
async def pwa_app():
    return _serve("app/index.html")


@router.get("/admin", include_in_schema=False)
async def admin_page():
    return _serve("admin/index.html")


@router.get("/manifest.json", include_in_schema=False)
async def manifest():
    return _serve("app/manifest.json")


@router.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    return _serve("app/service-worker.js")


# Static assets (js, css, icons) for both frontends
router.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)
