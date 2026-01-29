#!/usr/bin/env bash
set -euo pipefail

: "${RABBIT_URL:?RABBIT_URL is required (amqp://...)}"
: "${CELERY_RESULT_BACKEND:?CELERY_RESULT_BACKEND is required (redis://...)}"

# Celery worker 실행 (GPU 1개 컨테이너이므로 concurrency=1 권장)
celery -A utils.celery_task_util:celery_app worker \
  --loglevel=INFO \
  --concurrency=1 \
  --hostname="worker@%h" &

WORKER_PID="$!"

# Gradio(웹) 실행 (기존과 동일하게 app.py 실행)
python3 app.py &

WEB_PID="$!"

# 둘 중 하나라도 죽으면 컨테이너 종료 (Swarm가 재시작 정책으로 복구)
wait -n "$WORKER_PID" "$WEB_PID"
exit 1