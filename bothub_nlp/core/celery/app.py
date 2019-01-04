from celery import Celery
from kombu import Queue

from .actions import ACTION_PARSE
from .actions import ACTION_TRAIN
from .actions import queue_name
from ... import settings


celery_app = Celery(
    'bothub.core.celery.tasks',
    backend=settings.CELERY_BACKEND_URL,
    broker=settings.CELERY_BROKER_URL)

queues_name = set([
    queue_name(ACTION_PARSE, lang)
    for lang in settings.SUPPORTED_LANGUAGES.keys()
] + [
    queue_name(ACTION_TRAIN, lang)
    for lang in settings.SUPPORTED_LANGUAGES.keys()
])
celery_app.conf.task_queues = [
    Queue(queue)
    for queue in queues_name
]