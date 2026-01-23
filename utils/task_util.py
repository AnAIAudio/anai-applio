import threading
import queue
from collections import deque
from datetime import datetime
from typing import Any, Callable, Deque, Dict, List, Tuple

task_queue = queue.Queue()
_task_lock = threading.Lock()
_pending: Deque[Dict[str, Any]] = deque()  # 아직 실행 전(대기)
_running: Dict[str, Dict[str, Any]] = {}  # 현재 실행 중
_finished: Deque[Dict[str, Any]] = deque()  # 최근 완료/실패 로그(옵션)
_finished_maxlen = 200


def worker():
    """백그라운드에서 큐에 쌓인 작업을 하나씩 꺼내 실행하는 워커"""
    while True:
        # 큐에서 작업을 꺼냄 (작업이 없으면 생길 때까지 대기)
        task_func, task_args, task_kwargs = task_queue.get()
        try:
            print(f"Starting task: {task_args[0] if task_args else 'Unknown Task'}")
            task_func(*task_args, **task_kwargs)
            print("Task completed.")
        except Exception as e:
            print(f"Error in task: {e}")
        finally:
            # 작업 완료 표시
            task_queue.task_done()


def enqueue_task(
    task_func: Callable[..., Any],
    *task_args: Any,
    task_name: str | None = None,
    **task_kwargs: Any,
) -> str:
    """
    작업을 큐에 넣고, UI 표시를 위해 메타데이터를 별도 추적합니다.
    반환값: task_id
    """
    task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    display = task_name or (
        task_args[0] if task_args else getattr(task_func, "__name__", "Unknown Task")
    )

    meta = {
        "id": task_id,
        "name": str(display),
        "enqueued_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
    }

    with _task_lock:
        _pending.append(meta)

    task_queue.put((task_id, task_func, task_args, task_kwargs))
    return task_id


def get_queue_snapshot() -> Dict[str, Any]:
    """Gradio에서 읽기 좋은 형태로 현재 상태 스냅샷을 반환합니다."""
    with _task_lock:
        pending_list = list(_pending)
        running_list = list(_running.values())
        finished_list = list(_finished)

    return {
        "counts": {
            "pending": len(pending_list),
            "running": len(running_list),
            "finished": len(finished_list),
        },
        "pending": pending_list,
        "running": running_list,
        "finished_recent": finished_list[-20:],  # UI에는 최근만
    }


# 워커 쓰레드를 데몬 모드로 시작 (프로그램 종료 시 함께 종료됨)
threading.Thread(target=worker, daemon=True).start()
