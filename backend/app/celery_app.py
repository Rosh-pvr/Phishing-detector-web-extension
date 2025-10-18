from celery import Celery
from .config import REDIS_URL

celery = Celery(
    "app",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery.conf.task_soft_time_limit = 90
celery.conf.task_time_limit = 120
celery.autodiscover_tasks(["app"])
