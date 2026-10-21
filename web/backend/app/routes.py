"""The small local HTTP API consumed by the React client."""
import asyncio
import json
import subprocess

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from .catalog import build_command, catalog, dataset
from .jobs import JobConflict
from .results import Results
from .schemas import JobRequest

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    code = "import importlib.util,json;print(json.dumps({n:bool(importlib.util.find_spec(n)) for n in ('paddleocr','PySide6','cv2')}))"
    try:
        def inspect():
            return subprocess.run([settings.python, "-c", code], capture_output=True, text=True, timeout=5)
        result = await asyncio.to_thread(inspect)
        dependencies = json.loads(result.stdout) if result.returncode == 0 else {}
        error = result.stderr.strip() if result.returncode else None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        dependencies, error = {}, str(exc)
    return {"status": "ok", "python": settings.python, "root": str(settings.root),
            "dependencies": dependencies, "error": error, "local_only": True}


@router.get("/scripts")
def scripts():
    return catalog()


@router.get("/dataset")
def images(request: Request):
    return dataset(request.app.state.settings)


@router.get("/presets")
def presets(request: Request):
    return Results(request.app.state.settings).presets()


@router.get("/jobs")
def jobs(request: Request):
    return request.app.state.jobs.list()


@router.post("/jobs/preview")
def preview(payload: JobRequest, request: Request):
    return build_command(request.app.state.settings, payload, "preview")


@router.post("/jobs", status_code=201)
async def start(payload: JobRequest, request: Request):
    return await request.app.state.jobs.start(payload)


@router.get("/jobs/{job_id}")
def job(job_id: str, request: Request):
    return request.app.state.jobs.get(job_id)


@router.get("/jobs/{job_id}/logs")
def logs(job_id: str, request: Request, source: str = "console", offset: int = Query(0, ge=0)):
    return request.app.state.jobs.logs(job_id, source, offset)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, request: Request):
    return await request.app.state.jobs.cancel(job_id)


@router.get("/results")
def results(request: Request):
    return Results(request.app.state.settings).index()


@router.get("/results/{result_id}")
def result(result_id: str, request: Request):
    return Results(request.app.state.settings).get(result_id)


@router.get("/artifacts")
def artifact(request: Request, path: str, download: bool = False):
    file = Results(request.app.state.settings).artifact(path)
    return FileResponse(file, filename=file.name if download else None,
                        content_disposition_type="attachment" if download else "inline")
