"""Exercise real subprocess supervision with tiny fixtures, without OCR inference."""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from web.backend.app.catalog import build_command
from web.backend.app.config import Settings
from web.backend.app.main import create_app
from web.backend.app.schemas import JobRequest
from helpers.ocr_common import BASELINE, write_json

SHORT_SCRIPT = "import time; print('ทดสอบภาษาไทย', flush=True); time.sleep(.2)\n"
LONG_SCRIPT = "import time; print('READY', flush=True); time.sleep(60)\n"


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ocr-web-test-")
        self.root = Path(self.temporary.name).resolve()
        self.settings = Settings(self.root, sys.executable)
        (self.root / "images").mkdir()
        for name in ("1.png", "2.png"):
            (self.root / "images" / name).write_bytes(b"fixture; real OCR is not invoked")
            write_json(self.root / "GroundTruth" / f"{Path(name).stem}_gt.json", {
                "pos1": {"text": "ยา", "bbox": [0, 0, 20, 10], "ignore": False}})
        for script in ("create_gt", "gt_editor", "evaluate_ocr", "experiment_ocr"):
            (self.root / f"{script}.py").write_text(SHORT_SCRIPT)
        write_json(self.root / "experiments/dataset_split.json", {"samples": [
            {"id": "1", "file": "1.png", "group": "a", "split": "tune"},
            {"id": "2", "file": "2.png", "group": "b", "split": "holdout"}]})
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        # Tests may intentionally leave an editor alive across server shutdown.
        for process in self.app.state.jobs.processes.values():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        self.temporary.cleanup()

    def start(self, **options):
        response = self.client.post("/api/jobs", json={"script": "create_gt", **options})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def wait(self, job_id, status="completed"):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == status:
                return job
            time.sleep(.03)
        self.fail(f"Expected {status}; got {job}")

    def test_defaults_match_baseline_and_preview_does_not_write_files(self):
        response = self.client.post("/api/jobs/preview", json={"script": "create_gt"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["config"], BASELINE)
        self.assertFalse((self.settings.jobs_dir / "preview").exists())
        self.assertEqual(self.client.get("/api/scripts").json()["baseline"], BASELINE)

    def test_custom_output_parent_is_still_isolated_per_job(self):
        request = JobRequest(script="evaluate_ocr", output="evaluation_output/custom")
        first = build_command(self.settings, request, "one")
        second = build_command(self.settings, request, "two")
        self.assertEqual(first["output"], "evaluation_output/custom/web-one")
        self.assertNotEqual(first["output"], second["output"])

    def test_skipped_drafts_do_not_claim_previous_run_as_new_work(self):
        path = self.root / "GroundTruthDraft/draft_run.json"
        write_json(path, {"status": "completed", "processed": 9, "failures": []})
        os.utime(path, (1, 1))
        job = self.start()
        finished = self.wait(job["id"])
        self.assertIsNone(finished["draft_report"])

    def test_start_capture_unicode_logs_and_restore_history(self):
        job = self.start(config={"text_det_thresh": .2})
        finished = self.wait(job["id"])
        self.assertEqual(finished["returncode"], 0)
        log = self.client.get(f"/api/jobs/{job['id']}/logs").json()
        self.assertIn("ทดสอบภาษาไทย", log["text"])
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/logs", params={"offset": log["offset"]}).json()["text"], "")
        config = json.loads((self.settings.jobs_dir / job["id"] / "config.json").read_text())
        self.assertEqual(config["text_det_thresh"], .2)
        with TestClient(create_app(self.settings)) as second:
            self.assertEqual(second.get(f"/api/jobs/{job['id']}").json()["status"], "completed")

    def test_busy_ocr_rejected_but_editor_allowed_and_editor_duplicate_rejected(self):
        (self.root / "create_gt.py").write_text(LONG_SCRIPT)
        (self.root / "gt_editor.py").write_text(LONG_SCRIPT)
        job = self.start()
        self.assertEqual(self.client.post("/api/jobs", json={"script": "evaluate_ocr"}).status_code, 409)
        editor = self.start(script="gt_editor")
        self.assertEqual(self.client.post("/api/jobs", json={"script": "gt_editor"}).status_code, 409)
        self.assertEqual(self.client.post(f"/api/jobs/{editor['id']}/cancel").status_code, 409)
        self.assertEqual(self.client.post(f"/api/jobs/{job['id']}/cancel").json()["status"], "cancelled")

    def test_cancel_kills_descendant_that_ignores_sigterm(self):
        heartbeat = self.root / "heartbeat.txt"
        child = f"import signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);p=Path({str(heartbeat)!r});\nwhile True:p.write_text(str(time.time()));time.sleep(.03)"
        script = "import subprocess,sys,time\n" + f"subprocess.Popen([sys.executable,'-c',{child!r}])\n" + "print('READY',flush=True)\ntime.sleep(60)\n"
        (self.root / "experiment_ocr.py").write_text(script)
        job = self.start(script="experiment_ocr", dry_run=True)
        deadline = time.monotonic() + 5
        while not heartbeat.exists() and time.monotonic() < deadline:
            time.sleep(.03)
        self.assertTrue(heartbeat.exists())
        response = self.client.post(f"/api/jobs/{job['id']}/cancel")
        self.assertEqual(response.json()["status"], "cancelled")
        stamp = heartbeat.read_text()
        time.sleep(.15)
        self.assertEqual(heartbeat.read_text(), stamp)

    def test_shutdown_interrupts_ocr_and_preserves_editor_process(self):
        for name in ("create_gt", "gt_editor"):
            (self.root / f"{name}.py").write_text(LONG_SCRIPT)
        job = self.start()
        editor = self.start(script="gt_editor")
        self.client.__exit__(None, None, None)
        self.assertIsNotNone(self.app.state.jobs.processes[job["id"]].poll())
        self.assertIsNone(self.app.state.jobs.processes[editor["id"]].poll())
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}").json()["status"], "interrupted")
        self.assertEqual(self.client.get(f"/api/jobs/{editor['id']}").json()["status"], "interrupted")

    def test_command_builder_maps_single_image_ids_flags_and_custom_trials(self):
        create = build_command(self.settings, JobRequest(script="create_gt", input="images/1.png", overwrite=True), "test")
        self.assertIn(str(self.root / "images/1.png"), create["args"])
        self.assertIn("--overwrite", create["args"])
        evaluation = build_command(self.settings, JobRequest(script="evaluate_ocr", ids=["1"]), "test")
        self.assertEqual(evaluation["args"][-2:], ["--ids", "1"])
        response = self.client.post("/api/jobs", json={"script": "experiment_ocr", "tune_only": True, "combine": False,
                "experiment_mode": "custom", "experiments": [{"name": "mine", "parameters": {"text_det_limit_side_len": 1600}}]})
        self.assertEqual(response.status_code, 201, response.text)
        item = response.json()
        self.assertIn("--tune-only", item["command"])
        self.assertIn("--no-combine", item["command"])
        stored = json.loads((self.settings.jobs_dir / item["id"] / "experiments.json").read_text())
        self.assertEqual(stored["experiments"][0]["parameters"]["text_det_limit_side_len"], 1600)
        self.wait(item["id"])

    def test_invalid_config_missing_gt_duplicate_names_and_unknown_scripts(self):
        for payload in ({"script": "unknown"}, {"script": "create_gt", "config": {"device": "gpu:0"}},
                        {"script": "create_gt", "config": {"text_det_thresh": 2}},
                        {"script": "experiment_ocr", "experiment_mode": "custom", "experiments": [
                            {"name": "same", "parameters": {}}, {"name": "same", "parameters": {}}]}):
            self.assertEqual(self.client.post("/api/jobs", json=payload).status_code, 422)
        (self.root / "GroundTruth/1_gt.json").unlink()
        self.assertEqual(self.client.post("/api/jobs", json={"script": "evaluate_ocr", "ids": ["1"]}).status_code, 422)
        self.assertEqual(self.client.post("/api/jobs/preview", json={"script": "experiment_ocr", "dry_run": True}).status_code, 200)
        write_json(self.root / "experiments/broken.json", {"samples": [{"id": "1"}]})
        response = self.client.post("/api/jobs/preview", json={"script": "experiment_ocr", "split_file": "experiments/broken.json", "dry_run": True})
        self.assertEqual(response.status_code, 422)
        self.assertIn("split", response.json()["detail"])

    def test_origin_host_and_artifact_path_guards(self):
        self.assertEqual(self.client.post("/api/jobs", headers={"origin": "https://example.com"}, json={"script": "create_gt"}).status_code, 403)
        self.assertEqual(self.client.get("/api/scripts", headers={"host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/jobs/preview", headers={"host": "localhost:8123", "origin": "http://localhost:8123"}, json={"script": "create_gt"}).status_code, 200)
        self.assertEqual(self.client.get("/api/artifacts", params={"path": "images/1.png"}).status_code, 200)
        for path in ("../secret.json", "requirements.txt", ".git/config"):
            self.assertEqual(self.client.get("/api/artifacts", params={"path": path}).status_code, 422)
        outside = self.root / "outside.json"
        outside.write_text('{"secret":true}')
        (self.root / "images/link.json").symlink_to(outside)
        self.assertEqual(self.client.get("/api/artifacts", params={"path": "images/link.json"}).status_code, 422)
        self.assertEqual(self.client.get("/api/unknown").status_code, 404)

    def test_reports_existing_partial_missing_images_and_presets(self):
        directory = self.root / "experiment_output/old"
        summary = {"status": "completed_with_errors", "dataset_id": "dataset", "created_utc": "2026-10-21T00:00:00Z",
                   "best_trial": "baseline", "trials": [{"name": "baseline", "status": "completed", "images": [
                       {"filename": "1.png", "status": "completed", "framed_image": "framed/missing.png"}]},
                       {"name": "failed", "status": "failed"}], "holdout": None}
        write_json(directory / "comparison.json", summary)
        write_json(directory / "selected_config.json", BASELINE)
        bad = self.root / "experiment_output/writing/comparison.json"
        bad.parent.mkdir(parents=True)
        bad.write_text('{"status":')
        entries = self.client.get("/api/results").json()
        self.assertEqual(len(entries), 1)
        result = self.client.get(f"/api/results/{entries[0]['id']}").json()
        self.assertEqual(result["report"]["trials"][0]["images"][0]["framed_path"], None)
        self.assertEqual(result["report"]["trials"][1]["status"], "failed")
        self.assertEqual(self.client.get("/api/presets").json()[0]["config"], BASELINE)

    def test_worker_log_streams_progress_and_utf8_chunk_boundaries(self):
        (self.root / "experiment_ocr.py").write_text(LONG_SCRIPT)
        job = self.start(script="experiment_ocr", dry_run=True)
        directory = self.root / job["output"] / "round/trials/baseline"
        directory.mkdir(parents=True)
        content = 'a' * 65535 + 'ยา\n'
        (directory / "worker.log").write_text(content)
        write_json(directory / "report.json", {"status": "running", "expected_images": 2,
            "images": [{"status": "completed"}], "model_load_seconds": .1})
        detail = self.client.get(f"/api/jobs/{job['id']}").json()
        self.assertIn("trial:baseline", detail["log_sources"])
        self.assertEqual(detail["progress"]["completed_images"], 1)
        first = self.client.get(f"/api/jobs/{job['id']}/logs", params={"source": "trial:baseline"}).json()
        second = self.client.get(f"/api/jobs/{job['id']}/logs", params={"source": "trial:baseline", "offset": first["offset"]}).json()
        self.assertEqual(first["text"] + second["text"], content)
        self.client.post(f"/api/jobs/{job['id']}/cancel")

    def test_failed_launch_is_reported_in_history(self):
        self.settings.python = str(self.root / "missing-python")
        item = self.start()
        self.assertEqual(item["status"], "failed")
        self.assertTrue(item["error"])
        self.assertEqual(self.client.get("/api/jobs").json()[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
