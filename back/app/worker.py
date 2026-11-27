"""Celery application (broker: Valkey) and the beat schedule of periodic jobs.

Run by the `worker` service: celery -A app.worker:celery_app worker --beat
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("hypertube", broker=settings.broker_url, include=["app.jobs.cleanup"])
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    timezone="UTC",
    beat_schedule={
        "delete-expired-auth-rows": {
            "task": "cleanup.expired_auth_rows",
            "schedule": settings.cleanup_interval_minutes * 60,
        },
        "delete-unwatched-movies": {
            "task": "cleanup.unwatched_movies",
            "schedule": settings.cleanup_interval_minutes * 60,
        },
    },
)
