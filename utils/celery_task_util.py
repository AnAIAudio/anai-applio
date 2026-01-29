import os
from celery import Celery

rabbit_url = os.getenv("RABBIT_URL")
redis_url = os.getenv("CELERY_RESULT_BACKEND")

celery_app = Celery(
    "worker",
    broker=rabbit_url,
    backend=redis_url,
    include=[
        "core",
    ],
)

# 3시간 (초 단위)
celery_app.conf.broker_transport_options = {
    "visibility_timeout": 10800,
}
celery_app.conf.timezone = "Asia/Seoul"
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True

# 상태/결과 관련(Gradio에서 조회할 거라면 권장)
celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 10800  # 결과 TTL (필요에 맞게)
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"