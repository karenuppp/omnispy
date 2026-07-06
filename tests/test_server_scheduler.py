"""Tests for scheduler — focused on job management, not actual execution."""

import pytest
from server.scheduler import SchedulerManager


def test_scheduler_init_and_shutdown():
    mgr = SchedulerManager()
    assert mgr.scheduler is None

    mgr.init()
    assert mgr.scheduler is not None
    assert mgr.scheduler.running

    mgr.shutdown()
    assert mgr.scheduler is None


def test_add_remove_job():
    mgr = SchedulerManager()
    mgr.init()
    job_id = mgr.add_job(
        task_id=1,
        cron="0 9 * * *",
        func=lambda: None,
    )
    assert job_id is not None
    assert mgr.scheduler.get_job(job_id) is not None

    # remove_job takes task_id (int), not job_id (str)
    mgr.remove_job(task_id=1)
    assert mgr.scheduler.get_job(job_id) is None
    mgr.shutdown()


def test_add_job_with_invalid_cron():
    mgr = SchedulerManager()
    mgr.init()
    with pytest.raises(Exception):
        mgr.add_job(task_id=2, cron="not-cron", func=lambda: None)
    mgr.shutdown()
