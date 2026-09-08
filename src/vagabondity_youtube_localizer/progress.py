import copy
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone


class LocalizationProgressTracker:
    """Keep the latest localization run observable by the browser UI."""

    def __init__(self, max_jobs=10):
        self.max_jobs = max_jobs
        self._jobs = {}
        self._active_job_id = None
        self._lock = threading.Lock()

    def start(self, video_count, language_count, provider):
        with self._lock:
            if self._active_job_id:
                active = self._jobs.get(self._active_job_id)
                if active and active["status"] == "running":
                    return None, copy.deepcopy(active)

            job_id = uuid.uuid4().hex
            total = video_count * language_count
            job = {
                "id": job_id,
                "status": "running",
                "cancel_requested": False,
                "provider": provider,
                "video_count": video_count,
                "language_count": language_count,
                "total": total,
                "processed": 0,
                "succeeded": 0,
                "skipped": 0,
                "failed": 0,
                "trimmed": 0,
                "remaining": total,
                "percent": 0,
                "current": None,
                "skip_reasons": {},
                "skip_details": {},
                "failure_reasons": {},
                "failure_details": {},
                "error": "",
                "started_at": self._now(),
                "finished_at": None,
            }
            self._jobs[job_id] = job
            self._active_job_id = job_id
            self._prune_jobs()
            return job_id, copy.deepcopy(job)

    def update(self, job_id, event):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return

            event_type = event.get("type")
            if event_type in {"item_started", "stage"}:
                job["current"] = {
                    "video": event.get("video", ""),
                    "language": event.get("language", ""),
                    "stage": event.get("stage", "preparing"),
                }
                return

            if event_type != "item_finished":
                return

            outcome = event.get("outcome")
            if outcome not in {"succeeded", "skipped", "failed"}:
                return
            job["processed"] += 1
            job[outcome] += 1
            if event.get("trimmed"):
                job["trimmed"] += 1

            reason = event.get("reason")
            if reason and outcome in {"skipped", "failed"}:
                key = "skip_reasons" if outcome == "skipped" else "failure_reasons"
                reasons = Counter(job[key])
                reasons[reason] += 1
                job[key] = dict(reasons)

                details_key = (
                    "skip_details" if outcome == "skipped" else "failure_details"
                )
                details = job[details_key].setdefault(reason, [])
                details.append(
                    {
                        "video": event.get("video", ""),
                        "language": event.get("language", ""),
                    }
                )

            job["remaining"] = max(0, job["total"] - job["processed"])
            job["percent"] = self._percent(job)
            job["current"] = {
                "video": event.get("video", ""),
                "language": event.get("language", ""),
                "stage": outcome,
            }

    def request_cancel(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job["status"] == "running":
                job["cancel_requested"] = True
            return copy.deepcopy(job)

    def is_cancel_requested(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job["cancel_requested"])

    def finish(self, job_id, error=""):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if error:
                job["status"] = "stopped"
            elif job["cancel_requested"]:
                job["status"] = "cancelled"
            else:
                job["status"] = "completed"
            job["error"] = error
            job["finished_at"] = self._now()
            job["percent"] = self._percent(job)
            if self._active_job_id == job_id:
                self._active_job_id = None

    def fail(self, job_id, message):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "error"
            job["error"] = str(message)
            job["finished_at"] = self._now()
            job["percent"] = self._percent(job)
            if self._active_job_id == job_id:
                self._active_job_id = None

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def get_active(self):
        with self._lock:
            if not self._active_job_id:
                return None
            job = self._jobs.get(self._active_job_id)
            return copy.deepcopy(job) if job else None

    def _prune_jobs(self):
        finished_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job_id != self._active_job_id and job["status"] != "running"
        ]
        while len(self._jobs) > self.max_jobs and finished_ids:
            del self._jobs[finished_ids.pop(0)]

    @staticmethod
    def _percent(job):
        if job["total"] == 0:
            return 100
        return round(job["processed"] * 100 / job["total"])

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()
