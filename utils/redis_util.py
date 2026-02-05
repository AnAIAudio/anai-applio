import os

ACTIVE_JOBS_ZSET_KEY = "jobs:active"
JOB_INDEX_REDIS_URL = "JOB_INDEX_REDIS_URL"


def register_job(task_id: str, model_name: str, enqueued_at: int | None = None):
    """
    Celery 워커가 집어가기 전(PENDING)에도 Queue Monitor에 보이도록
    enqueue 시점에 Redis에 job 메타/active zset을 등록한다.
    """
    import time
    import redis

    job_redis_url = os.getenv(JOB_INDEX_REDIS_URL)
    if not job_redis_url or not task_id:
        return False

    r = redis.Redis.from_url(job_redis_url, decode_responses=True)
    ts = int(time.time()) if enqueued_at is None else int(enqueued_at)

    meta_key = f"job:{task_id}:meta"
    # 이미 존재하면 enqueued_at 같은 값은 덮어쓰지 않는 쪽이 안전(선택)
    r.hsetnx(meta_key, "enqueued_at", str(ts))
    r.hset(meta_key, mapping={"model_name": str(model_name), "status": "PENDING"})
    r.zadd(ACTIVE_JOBS_ZSET_KEY, {task_id: ts})
    return True


def delete_job(task_id: str) -> tuple[bool, str]:
    """
    job:{task_id}:log, job:{task_id}:meta 삭제
    jobs:active(ZSET)에서 task_id 제거
    """
    import redis

    if not task_id:
        return False, "task_id가 비어있습니다."

    job_redis_url = os.getenv(JOB_INDEX_REDIS_URL)
    if not job_redis_url:
        return False, "JOB_INDEX_REDIS_URL 미설정"

    r = redis.Redis.from_url(job_redis_url, decode_responses=True)

    log_key = f"job:{task_id}:log"
    meta_key = f"job:{task_id}:meta"

    try:
        r.delete(log_key, meta_key)
        r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
        return True, f"삭제 완료: {task_id}"
    except Exception as e:
        return False, f"삭제 실패: {e}"


def poll(task_id: str):
    import re
    import redis
    from celery.result import AsyncResult
    from utils.celery_task_util import celery_app

    job_redis_url = os.getenv(JOB_INDEX_REDIS_URL)

    if not task_id:
        return "", 0, "ID 없음"

    r = redis.Redis.from_url(job_redis_url, decode_responses=True)

    # 최근 200줄만 표시
    logs = r.lrange(f"job:{task_id}:log", -200, -1)
    log_text = "\n".join(logs)

    meta = r.hgetall(f"job:{task_id}:meta")
    total_epoch = int(meta.get("total_epoch", "0") or 0)

    # progress 우선순위: meta.progress -> 로그 epoch 기반 계산(fallback)
    progress = int(meta.get("progress", "0") or 0)

    if progress <= 0 < total_epoch and logs:
        # 로그에서 마지막 epoch=숫자 찾기
        last_epoch = 0
        epoch_re = re.compile(r"\bepoch=(\d+)\b")
        for line in reversed(logs):
            m = epoch_re.search(line)
            if m:
                last_epoch = int(m.group(1))
                break

        if last_epoch > 0:
            progress = int(min(100, max(0, int((last_epoch / total_epoch) * 100))))

    ar = AsyncResult(task_id, app=celery_app)
    status = ar.state  # PENDING/STARTED/SUCCESS/FAILURE...

    if status in ("SUCCESS", "FAILURE", "REVOKED"):
        try:
            if r and task_id:
                r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
        except Exception:
            pass

    if status == "FAILURE":
        try:
            err = str(ar.result)
            if err:
                status = f"{status}: {err}"
        except Exception:
            pass

    return log_text, progress, status


def get_queue_snapshot(limit: int = 30):
    """
    Redis에 저장된 job:*:meta 기반으로, 아직 끝나지 않은 작업들을 목록으로 반환.
    - PENDING이 많으면 사실상 '대기열'로 볼 수 있음
    - STARTED는 실행 중
    """
    import time
    import redis
    from celery.result import AsyncResult
    from utils.celery_task_util import celery_app

    def _clip(s: object, n: int = 120) -> str:
        s = "" if s is None else str(s)
        return s if len(s) <= n else (s[: n - 1] + "…")

    job_redis_url = os.getenv(JOB_INDEX_REDIS_URL)
    if not job_redis_url:
        return [], "JOB_INDEX_REDIS_URL 미설정"

    r = redis.Redis.from_url(job_redis_url, decode_responses=True)

    limit = max(1, min(50, int(limit)))
    now_ts = int(time.time())

    # score(enqueued_at) 기준 오름차순: 오래 기다린 것부터
    items = r.zrange(ACTIVE_JOBS_ZSET_KEY, 0, limit - 1, withscores=True)

    rows = []
    for task_id, score in items:
        meta = r.hgetall(f"job:{task_id}:meta") or {}
        ar = AsyncResult(task_id, app=celery_app)
        state = ar.state

        # terminal이면 여기서도 청소(Queue Monitor만 켜도 정리됨)
        if state in ("SUCCESS", "FAILURE", "REVOKED"):
            try:
                if r and task_id:
                    r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
            except Exception:
                pass
            continue

        progress = int(meta.get("progress", "0") or 0)
        total_epoch = int(meta.get("total_epoch", "0") or 0)

        model_name = _clip(meta.get("model_name", ""), 80)

        enq = int(meta.get("enqueued_at", "0") or 0)
        if enq <= 0:
            enq = int(score) if score else 0

        age_sec = (now_ts - enq) if enq > 0 else ""

        rows.append(
            [
                _clip(task_id, 80),
                _clip(state, 40),
                progress,
                total_epoch,
                model_name,
                age_sec,
            ]
        )

    pending = sum(1 for row in rows if len(row) > 1 and row[1] == "PENDING")
    started = sum(1 for row in rows if len(row) > 1 and row[1] == "STARTED")
    summary = f"표시 {len(rows)}개 (PENDING={pending}, STARTED={started})"

    return rows, summary
