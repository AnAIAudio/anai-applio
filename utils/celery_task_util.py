import os
from celery import Celery

rabbit_url = os.getenv("RABBIT_URL")

celery_app = Celery(
    "worker",
    broker=rabbit_url,
    include=[
        "services.translate.video_translate_service",
        "services.translate.srt_translate_service",
        "services.align.mfa_service",
    ],
)

# 3시간 (초 단위)
celery_app.conf.broker_transport_options = {
    "visibility_timeout": 10800,
}
celery_app.conf.timezone = "Asia/Seoul"
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
