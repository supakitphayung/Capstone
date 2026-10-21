"""Disk-backed job supervision for the unchanged command-line programs."""
import asyncio
import codecs
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .catalog import build_command
from .config import Settings
from .results import Results, read_optional
from .schemas import JobRequest
from helpers.ocr_common import utc_now, write_json

ACTIVE = {"running", "cancelling"}


class JobConflict(Exception):
    pass


class Jobs:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.items = {}
        self.processes = {}
        self.tasks = {}
        self.lock = asyncio.Lock()

    def restore(self):
        self.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        for path in self.settings.jobs_dir.glob("*/job.json"):
            item = read_optional(path)
            if not isinstance(item, dict) or item.get("id") != path.parent.name:
                continue
            if item.get("status") in ACTIVE:
                item.update(status="interrupted", finished_utc=utc_now(),
                            error="Server เริ่มใหม่ จึงไม่สามารถติดตาม process รอบก่อนต่อได้")
                write_json(path, item)
            self.items[item["id"]] = item

    def _save(self, item):
        write_json(self.settings.jobs_dir / item["id"] / "job.json", item)

    def list(self):
        return sorted(self.items.values(), key=lambda item: item["created_utc"], reverse=True)

    def get(self, job_id):
        if job_id not in self.items:
            raise FileNotFoundError("ไม่พบงานนี้")
        item = dict(self.items[job_id])
        output = item.get("output")
        results = Results(self.settings).index()
        item["result_ids"] = [entry["id"] for entry in results if output and
                              Path(entry["path"]).is_relative_to(output)]
        item["log_sources"] = list(self.log_sources(item))
        item["progress"] = self.progress(item)
        if item["script"] == "create_gt":
            item["draft_report"] = read_optional(self.settings.jobs_dir / job_id / "draft_report.json")
        return item

    async def start(self, request: JobRequest):
        async with self.lock:
            for item in self.items.values():
                if item["status"] not in ACTIVE:
                    continue
                same_editor = item["script"] == request.script == "gt_editor"
                both_ocr = item["script"] != "gt_editor" and request.script != "gt_editor"
                if same_editor or both_ocr:
                    raise JobConflict("มีงานประเภทนี้กำลังทำงานอยู่ กรุณารอหรือยกเลิกงานเดิมก่อน")
            job_id = uuid.uuid4().hex
            prepared = build_command(self.settings, request, job_id, persist=True)
            item = {"id": job_id, "script": request.script, "status": "running", "created_utc": utc_now(),
                    "finished_utc": None, "returncode": None, "command": prepared["command"],
                    "output": prepared["output"], "request": request.model_dump(), "error": None,
                    "started_ns": time.time_ns()}
            self.items[job_id] = item
            self._save(item)
            try:
                environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
                if request.script == "gt_editor":
                    # The desktop session, not the test suite's offscreen Qt backend.
                    if environment.get("QT_QPA_PLATFORM") == "offscreen":
                        environment.pop("QT_QPA_PLATFORM")
                with (self.settings.jobs_dir / job_id / "console.log").open("wb") as log:
                    process = subprocess.Popen(prepared["args"], cwd=self.settings.root,
                                               env=environment, stdout=log, stderr=subprocess.STDOUT,
                                               stdin=subprocess.DEVNULL, start_new_session=True)
                self.processes[job_id] = process
                item["pid"] = process.pid
                self._save(item)
                self.tasks[job_id] = asyncio.create_task(self._watch(job_id))
            except OSError as error:
                item.update(status="failed", finished_utc=utc_now(), error=str(error))
                self._save(item)
            return self.get(job_id)

    async def _watch(self, job_id):
        item, process = self.items[job_id], self.processes[job_id]
        while process.poll() is None:
            await asyncio.sleep(.1)
        if item["status"] == "cancelling":
            return
        code = process.returncode
        status = "completed" if code == 0 else "failed"
        if item.get("output"):
            for path in (self.settings.root / item["output"]).glob("*/comparison.json"):
                report = read_optional(path)
                if report and report.get("status") == "completed_with_errors":
                    status = "completed_with_errors"
        if item["script"] == "create_gt":
            path = self.settings.root / item["output"] / "draft_run.json"
            report = read_optional(path)
            if report and path.stat().st_mtime_ns >= item["started_ns"]:
                write_json(self.settings.jobs_dir / job_id / "draft_report.json", report)
        item.update(status=status, returncode=code, finished_utc=utc_now())
        self._save(item)

    async def cancel(self, job_id, final_status="cancelled"):
        item = self.items.get(job_id)
        if not item:
            raise FileNotFoundError("ไม่พบงานนี้")
        if item["script"] == "gt_editor":
            raise JobConflict("กรุณาปิด GT Editor ผ่านหน้าต่าง GUI เพื่อให้บันทึกงานได้ตามปกติ")
        if item["status"] == "cancelling":
            return self.get(job_id)
        if item["status"] != "running":
            raise JobConflict("งานนี้สิ้นสุดแล้ว")
        item["status"] = "cancelling"
        self._save(item)
        process = self.processes[job_id]
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        # Wait for the whole group, including workers that outlive their parent.
        while time.monotonic() < deadline:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(.05)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await self.tasks[job_id]
        item.update(status=final_status, returncode=process.poll(), finished_utc=utc_now())
        self._save(item)
        return self.get(job_id)

    async def shutdown(self):
        for item in list(self.items.values()):
            if item["status"] in ACTIVE and item["script"] != "gt_editor":
                if item["status"] == "cancelling":
                    await self.tasks[item["id"]]
                else:
                    await self.cancel(item["id"], "interrupted")
        # Popen GUI children remain alive; cancelling a watcher does not kill Qt.
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    def log_sources(self, item):
        sources = {"console": self.settings.jobs_dir / item["id"] / "console.log"}
        if item["script"] == "experiment_ocr" and item.get("output"):
            root = self.settings.root / item["output"]
            for path in sorted(root.glob("*/trials/*/worker.log")):
                if path.resolve().is_relative_to(root):
                    sources[f"trial:{path.parent.name}"] = path
            for path in root.glob("*/holdout/worker.log"):
                if path.resolve().is_relative_to(root):
                    sources["holdout"] = path
        return sources

    def logs(self, job_id, source="console", offset=0):
        if job_id not in self.items:
            raise FileNotFoundError("ไม่พบงานนี้")
        path = self.log_sources(self.items[job_id]).get(source)
        if path is None:
            raise FileNotFoundError("ไม่พบ log stream นี้")
        if not path.is_file():
            return {"text": "", "offset": 0}
        with path.open("rb") as stream:
            stream.seek(offset if offset <= path.stat().st_size else 0)
            start = stream.tell()
            data = stream.read(65536)
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        text = decoder.decode(data, final=False)
        return {"text": text, "offset": start + len(data) - len(decoder.getstate()[0])}

    def progress(self, item):
        if not item.get("output") or item["script"] not in ("evaluate_ocr", "experiment_ocr"):
            return None
        root = self.settings.root / item["output"]
        paths = list(root.glob("*/evaluation/report.json")) if item["script"] == "evaluate_ocr" else (
            list(root.glob("*/trials/*/report.json")) + list(root.glob("*/holdout/report.json")))
        reports = [(path, read_optional(path)) for path in paths if path.resolve().is_relative_to(root)]
        reports = [(path, report) for path, report in reports if isinstance(report, dict)]
        if not reports:
            return None
        path, current = max(reports, key=lambda pair: pair[0].stat().st_mtime)
        return {"stage": "holdout" if path.parent.name == "holdout" else path.parent.name,
                "completed_images": sum(image.get("status") == "completed" for image in current.get("images", [])),
                "expected_images": current.get("expected_images"),
                "completed_trials": sum(report.get("status") in ("completed", "failed") for _, report in reports),
                "model_loaded": current.get("model_load_seconds") is not None}
