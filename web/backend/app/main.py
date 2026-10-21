"""Run from the repository root: python -m uvicorn web.backend.app.main:app."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings
from .jobs import JobConflict, Jobs
from .routes import router


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    jobs = Jobs(settings)

    @asynccontextmanager
    async def lifespan(app):
        jobs.restore()
        yield
        await jobs.shutdown()

    app = FastAPI(title="OCR Workbench API", version="1.0.0", lifespan=lifespan)
    app.state.settings, app.state.jobs = settings, jobs
    app.include_router(router)

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # Prevent another website from using this local process-launching API.
        origin = request.headers.get("origin")
        allowed = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"}
        host_header = request.headers.get("host", "")
        host = host_header.split(":")[0]
        allowed.add(f"http://{host_header}")
        if host not in ("127.0.0.1", "localhost", "testserver") or (origin and origin not in allowed):
            return JSONResponse({"detail": "เว็บนี้รองรับการใช้งานผ่าน localhost เท่านั้น"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(JobConflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "API route not found"}, status_code=404)
        file = (settings.frontend / path).resolve()
        if not file.is_relative_to(settings.frontend.resolve()):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if file.is_file():
            return FileResponse(file)
        if path.startswith("assets/"):
            return JSONResponse({"detail": "Asset not found"}, status_code=404)
        index = settings.frontend / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend ยังไม่ได้ build: cd web/frontend && npm run build"}, status_code=503)

    return app


app = create_app()
