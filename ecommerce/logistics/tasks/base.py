import logging

from celery import shared_task

logger = logging.getLogger("logistics.tasks")

LOGISTICS_TASK_OPTIONS = {
    "acks_late": True,
    "bind": True,
}
