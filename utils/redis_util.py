import os


def poll(task_id: str):
    import re
    import redis
    from celery.result import AsyncResult
    from utils.celery_task_util import celery_app

    job_redis_url = os.getenv("JOB_INDEX_REDIS_URL")

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

    job_redis_url = os.getenv("JOB_INDEX_REDIS_URL")
    if not job_redis_url:
        return [], "JOB_INDEX_REDIS_URL 미설정"

    r = redis.Redis.from_url(job_redis_url, decode_responses=True)

    rows = []
    now_ts = int(time.time())

    # 주의: KEYS는 위험하니 scan_iter 사용
    for key in r.scan_iter(match="job:*:meta", count=500):
        # key: job:{task_id}:meta
        parts = key.split(":")
        if len(parts) < 3:
            continue
        task_id = parts[1]

        meta = r.hgetall(key) or {}
        # 메타가 너무 비어있으면 스킵
        if not meta:
            continue

        ar = AsyncResult(task_id, app=celery_app)
        state = ar.state

        # 완료된 작업은 목록에서 제외(원하면 포함하도록 바꿔도 됨)
        if state in ("SUCCESS", "FAILURE", "REVOKED"):
            continue

        progress = int(meta.get("progress", "0") or 0)
        total_epoch = int(meta.get("total_epoch", "0") or 0)
        model_name = meta.get("model_name", "") or ""
        enq = int(meta.get("enqueued_at", "0") or 0)
        age_sec = (now_ts - enq) if enq > 0 else None

        rows.append(
            {
                "task_id": task_id,
                "state": state,
                "progress(%)": progress,
                "total_epoch": total_epoch,
                "model_name": model_name,
                "age_sec": age_sec if age_sec is not None else "",
            }
        )

    # 최신(최근 enqueue) 우선으로 정렬: age_sec가 작은 것 우선
    def _sort_key(x):
        a = x.get("age_sec")
        return a if isinstance(a, int) else 10**12

    rows.sort(key=_sort_key)

    # limit 적용
    rows = rows[: max(1, int(limit))]

    # 요약 텍스트
    pending = sum(1 for x in rows if x.get("state") == "PENDING")
    started = sum(1 for x in rows if x.get("state") == "STARTED")
    summary = f"표시 {len(rows)}개 (PENDING={pending}, STARTED={started})"

    return rows, summary
