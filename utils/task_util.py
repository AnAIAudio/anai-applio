import threading
import queue

task_queue = queue.Queue()


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


# 워커 쓰레드를 데몬 모드로 시작 (프로그램 종료 시 함께 종료됨)
threading.Thread(target=worker, daemon=True).start()
