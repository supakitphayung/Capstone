"""Append-only log of API responses, one JSON line each, in a file per day.

Polling repeats the same GET many times a minute, so a GET whose response is
identical to the previous one for that URL is stored once.
"""
import hashlib
import json
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

BODY_LIMIT = 16_000
REMEMBERED_URLS = 2_000


def _payload(raw: bytes):
    """Return (value, truncated): parsed JSON when small enough, otherwise text."""
    if not raw:
        return None, False
    text = raw.decode("utf-8", errors="replace")
    if len(text) > BODY_LIMIT:
        return text[:BODY_LIMIT], True
    try:
        return json.loads(text), False
    except ValueError:
        return text, False


class ResponseLog:
    def __init__(self, folder: Path):
        self.folder = folder
        self.lock = threading.Lock()
        self.last_seen: OrderedDict[str, str] = OrderedDict()
        self.sequence = 0

    def record(self, *, method, path, query, status, duration_ms, content_type,
               request_body=b"", response_body=None):
        """Store one response; response_body is None when the body was not captured (files)."""
        with self.lock:
            if method == "GET":
                url = f"{path}?{query}"
                digest = hashlib.sha1(str(status).encode() + (response_body or b"")).hexdigest()
                if self.last_seen.get(url) == digest:
                    return None
                self.last_seen[url] = digest
                self.last_seen.move_to_end(url)
                while len(self.last_seen) > REMEMBERED_URLS:
                    self.last_seen.popitem(last=False)
            now = datetime.now(timezone.utc)
            self.sequence += 1
            request, _ = _payload(request_body)
            response, truncated = _payload(response_body or b"")
            entry = {"id": f"{now:%Y%m%dT%H%M%S%f}-{self.sequence}", "time": now.isoformat(),
                     "method": method, "path": path, "query": query, "status": status,
                     "duration_ms": round(duration_ms, 1), "content_type": content_type,
                     "size": len(response_body) if response_body is not None else None,
                     "request": request, "response": response, "truncated": truncated}
            try:
                self.folder.mkdir(parents=True, exist_ok=True)
                with (self.folder / f"responses-{now:%Y%m%d}.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                return None  # Logging must never break the request it describes.
            return entry

    def entries(self, limit=200, errors_only=False, method="", search=""):
        """Newest first, filtered; unreadable lines are skipped."""
        found, needle, method = [], search.strip().lower(), method.upper()
        files = sorted(self.folder.glob("responses-*.jsonl"), reverse=True) if self.folder.is_dir() else []
        for file in files:
            try:
                lines = file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                if needle and needle not in line.lower():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if (errors_only and entry.get("status", 0) < 400) or (method and entry.get("method") != method):
                    continue
                found.append(entry)
                if len(found) >= limit:
                    return found
        return found
