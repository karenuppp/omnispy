"""APScheduler manager. Handles adding/removing scheduled jobs for tasks."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class SchedulerManager:
    """Manages APScheduler lifecycle and task-job mapping."""

    def __init__(self):
        self.scheduler: BackgroundScheduler | None = None
        self._job_map: dict[int, str] = {}  # task_id -> job_id

    def init(self):
        """Initialize and start the scheduler (in-memory job store).

        Jobs are reloaded from the DB on every startup via ``reload_all()``,
        so we don't need a persistent SQLAlchemy job store.
        """
        self.scheduler = BackgroundScheduler(daemon=True)
        self.scheduler.start()

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

    def add_job(self, task_id: int, cron: str, func) -> str | None:
        """Add a scheduled job for a task. Returns job_id or None."""
        if not self.scheduler:
            return None
        trigger = CronTrigger.from_crontab(cron)

        def wrapper():
            func(task_id)

        job = self.scheduler.add_job(
            wrapper,
            trigger=trigger,
            id=f"task_{task_id}",
            replace_existing=True,
            name=f"Task #{task_id}",
        )
        self._job_map[task_id] = job.id
        return job.id

    def remove_job(self, task_id: int):
        """Remove the scheduled job for a task."""
        if not self.scheduler:
            return
        job_id = self._job_map.pop(task_id, None)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass  # job may already be gone

    def reload_all(self, tasks: list[dict], func):
        """Reload all jobs from a list of task dicts."""
        if not self.scheduler:
            return
        for task_id in list(self._job_map.keys()):
            self.remove_job(task_id)

        for task in tasks:
            if task.get("enabled") and task.get("schedule"):
                self.add_job(task["id"], task["schedule"], func)


# Global singleton
_scheduler_mgr = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    return _scheduler_mgr
