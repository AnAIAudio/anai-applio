"""Release 태그별 git worktree / uv venv / Applio subprocess 수명주기 관리."""

import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

from tabs.release_viewer.config import (
    PROJECT_ROOT,
    READY_TIMEOUT_SEC,
    WORKTREE_DIR,
)

Status = Literal["stopped", "starting", "running", "error"]

_processes: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


class ReleaseError(RuntimeError):
    """Release Viewer 관련 복구 가능한 에러."""


def _run(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(f"명령 시간 초과: {' '.join(cmd)}") from exc
    except FileNotFoundError as exc:
        raise ReleaseError(f"명령을 찾을 수 없음: {cmd[0]}") from exc
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-20:]
        raise ReleaseError("\n".join(tail) or f"명령 실패: {' '.join(cmd)}")
    return result.stdout


def verify_git_repo() -> None:
    _run(["git", "rev-parse", "--git-dir"], cwd=PROJECT_ROOT)


def ensure_worktree(tag: str) -> Path:
    verify_git_repo()
    WORKTREE_DIR.mkdir(parents=True, exist_ok=True)
    worktree_path = WORKTREE_DIR / tag
    if worktree_path.exists() and (worktree_path / ".git").exists():
        return worktree_path
    _run(
        ["git", "worktree", "add", str(worktree_path), tag],
        cwd=PROJECT_ROOT,
        timeout=120,
    )
    return worktree_path


def ensure_venv(worktree: Path) -> None:
    if (worktree / ".venv").exists():
        return
    _run(["uv", "sync"], cwd=worktree, timeout=3600)


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def _popen_alive(popen: subprocess.Popen | None) -> bool:
    return popen is not None and popen.poll() is None


def start_process(release: dict) -> subprocess.Popen:
    tag = release["tag"]
    port = release["port"]
    with _lock:
        existing = _processes.get(tag)
        if _popen_alive(existing):
            return existing
        if _is_port_in_use(port):
            raise ReleaseError(
                f"포트 {port}가 이미 사용 중입니다. (태그 {tag})"
            )
        worktree = WORKTREE_DIR / tag
        if not worktree.exists():
            raise ReleaseError(
                f"worktree가 준비되지 않았습니다: {worktree}"
            )
        env = os.environ.copy()
        popen = subprocess.Popen(
            ["uv", "run", "python", "app.py", "--port", str(port)],
            cwd=str(worktree),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=False,
        )
        _processes[tag] = popen
        return popen


def wait_until_ready(port: int, timeout: int = READY_TIMEOUT_SEC) -> bool:
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1.0)
    return False


def stop_process(tag: str) -> bool:
    with _lock:
        popen = _processes.pop(tag, None)
        if not _popen_alive(popen):
            return False
        popen.terminate()
        try:
            popen.wait(timeout=5)
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.wait(timeout=5)
        return True


def stop_all() -> None:
    with _lock:
        tags = list(_processes.keys())
    for tag in tags:
        try:
            stop_process(tag)
        except Exception:
            pass


def get_status(tag: str, port: int) -> Status:
    with _lock:
        popen = _processes.get(tag)
    if not _popen_alive(popen):
        return "stopped"
    if _is_port_in_use(port):
        return "running"
    return "starting"
