import os

# jobs:active  → PENDING/STARTED 상태의 작업만 (자동 정리)
# jobs:all     → 전체 이력 보존 (삭제 버튼으로만 제거, 컨테이너 재시작 시 초기화)
ACTIVE_JOBS_ZSET_KEY = "jobs:active"
ALL_JOBS_ZSET_KEY = "jobs:all"
JOB_INDEX_REDIS_URL = "JOB_INDEX_REDIS_URL"


def get_redis_log_key(task_id: str):
    return f"job:{task_id}:log"


def get_redis_meta_key(task_id: str):
    return f"job:{task_id}:meta"


def _get_redis():
    import redis

    url = os.getenv(JOB_INDEX_REDIS_URL)
    if not url:
        raise RuntimeError("JOB_INDEX_REDIS_URL 미설정")
    return redis.Redis.from_url(url, decode_responses=True)


def register_job(task_id: str, model_name: str, enqueued_at: int | None = None):
    """
    Celery 워커가 집어가기 전(PENDING)에도 Queue Monitor에 보이도록
    enqueue 시점에 Redis에 job 메타 / active zset / all zset 을 등록한다.
    jobs:all 은 컨테이너가 살아있는 동안 삭제 버튼 없이는 사라지지 않는다.
    """
    import time

    if not task_id:
        return False
    try:
        r = _get_redis()
    except RuntimeError:
        return False

    ts = int(time.time()) if enqueued_at is None else int(enqueued_at)
    meta_key = get_redis_meta_key(task_id=task_id)

    r.hsetnx(meta_key, "enqueued_at", str(ts))
    r.hset(meta_key, mapping={"model_name": str(model_name), "status": "PENDING"})

    r.zadd(ACTIVE_JOBS_ZSET_KEY, {task_id: ts})
    r.zadd(ALL_JOBS_ZSET_KEY, {task_id: ts})
    return True


def revoke_job(task_id: str) -> tuple[bool, str]:
    """
    실행 중이거나 대기 중인 Celery 작업을 강제 취소한다.
    - Celery에 SIGTERM revoke 전송
    - Redis meta status → REVOKED
    - jobs:active 에서 제거 (jobs:all 은 유지 → 목록에 계속 표시됨)
    """
    from utils.celery_task_util import celery_app

    if not task_id:
        return False, "task_id가 비어있습니다."
    try:
        r = _get_redis()
    except RuntimeError as e:
        return False, str(e)

    try:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        r.hset(get_redis_meta_key(task_id), "status", "REVOKED")
        r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
        return True, f"훈련 취소 완료: {task_id}"
    except Exception as e:
        return False, f"취소 실패: {e}"


def delete_job(task_id: str) -> tuple[bool, str]:
    """
    Queue Monitor 에서 '삭제' 버튼을 눌렀을 때만 호출된다.
    - log/meta 키 완전 삭제
    - jobs:active + jobs:all 양쪽 zset 에서 제거
    → 삭제 전까지는 완료/취소/실패 항목도 목록에 유지된다.
    """
    if not task_id:
        return False, "task_id가 비어있습니다."
    try:
        r = _get_redis()
    except RuntimeError as e:
        return False, str(e)

    try:
        r.delete(get_redis_log_key(task_id), get_redis_meta_key(task_id))
        r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
        r.zrem(ALL_JOBS_ZSET_KEY, task_id)
        return True, f"삭제 완료: {task_id}"
    except Exception as e:
        return False, f"삭제 실패: {e}"


def poll(task_id: str):
    import re
    from celery.result import AsyncResult
    from utils.celery_task_util import celery_app

    if not task_id:
        return "", 0, "ID 없음"

    try:
        r = _get_redis()
    except RuntimeError:
        return "", 0, "Redis 미설정"

    logs = r.lrange(get_redis_log_key(task_id), -200, -1)
    log_text = "\n".join(logs)

    meta = r.hgetall(get_redis_meta_key(task_id)) or {}
    total_epoch = int(meta.get("total_epoch", "0") or 0)
    progress = int(meta.get("progress", "0") or 0)

    if progress <= 0 < total_epoch and logs:
        epoch_re = re.compile(r"\bepoch=(\d+)\b")
        for line in reversed(logs):
            m = epoch_re.search(line)
            if m:
                last_epoch = int(m.group(1))
                progress = int(min(100, max(0, (last_epoch / total_epoch) * 100)))
                break

    ar = AsyncResult(task_id, app=celery_app)
    status = ar.state

    # terminal 상태이면 active zset 에서 제거하고 meta 동기화 (all zset 은 유지)
    if status in ("SUCCESS", "FAILURE", "REVOKED"):
        try:
            r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
            r.hset(get_redis_meta_key(task_id), "status", status)
        except Exception:
            pass

    if status == "FAILURE":
        try:
            err = str(ar.result)
            if err:
                status = f"FAILURE: {err}"
        except Exception:
            pass

    return log_text, progress, status


def get_queue_snapshot(limit: int = 30):
    """
    jobs:all ZSET 기반으로 전체 이력을 반환한다.
    - 완료/취소/실패 항목도 삭제 버튼을 누르기 전까지 유지됨
    - 컨테이너(프로세스) 재시작 → Redis jobs:all 사라짐 → 자동 초기화
    """
    import time
    from celery.result import AsyncResult
    from utils.celery_task_util import celery_app

    def _clip(s, n=120):
        s = "" if s is None else str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    try:
        r = _get_redis()
    except RuntimeError:
        return [], "JOB_INDEX_REDIS_URL 미설정"

    limit = max(1, min(200, int(limit)))
    now_ts = int(time.time())

    # 최신 작업이 위로 오도록 내림차순
    items = r.zrevrange(ALL_JOBS_ZSET_KEY, 0, limit - 1, withscores=True)

    rows = []
    for task_id, score in items:
        meta = r.hgetall(get_redis_meta_key(task_id)) or {}

        ar = AsyncResult(task_id, app=celery_app)
        celery_state = ar.state

        # meta 에 이미 기록된 terminal 상태 우선 (REVOKED 등)
        saved_status = meta.get("status", "")
        if saved_status in ("REVOKED", "SUCCESS", "FAILURE", "OVERTRAINING"):
            state = saved_status
        elif celery_state in ("SUCCESS", "FAILURE", "REVOKED"):
            state = celery_state
            try:
                r.hset(get_redis_meta_key(task_id), "status", state)
                r.zrem(ACTIVE_JOBS_ZSET_KEY, task_id)
            except Exception:
                pass
        else:
            state = celery_state

        progress = int(meta.get("progress", "0") or 0)
        total_epoch = int(meta.get("total_epoch", "0") or 0)
        model_name = _clip(meta.get("model_name", ""), 80)

        enq = int(meta.get("enqueued_at", "0") or 0)
        if enq <= 0:
            enq = int(score) if score else 0
        age_sec = (now_ts - enq) if enq > 0 else 0

        rows.append(
            [
                model_name,
                _clip(task_id, 80),
                _clip(state, 40),
                progress,
                total_epoch,
                age_sec,
            ]
        )

    counts: dict[str, int] = {}
    for row in rows:
        s = row[2]
        counts[s] = counts.get(s, 0) + 1

    summary_parts = [f"{s}={n}" for s, n in sorted(counts.items())]
    summary = (
        f"표시 {len(rows)}개 ({', '.join(summary_parts)})"
        if summary_parts
        else f"표시 {len(rows)}개"
    )

    return rows, summary
