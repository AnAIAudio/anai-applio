# job_index.py
import os
from redis import Redis

r = Redis.from_url(os.environ["JOB_INDEX_REDIS_URL"])  # 예: redis://redis:6379/2

def remember_task(task_id: str, max_items: int = 500):
    r.lpush("jobs:all", task_id)
    r.ltrim("jobs:all", 0, max_items - 1)

def list_tasks(limit: int = 50) -> list[str]:
    return [x.decode("utf-8") for x in r.lrange("jobs:all", 0, limit - 1)]