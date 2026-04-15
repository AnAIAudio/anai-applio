"""Release 태그별 git worktree / uv venv / Applio subprocess 수명주기 관리."""

import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Literal

from tabs.release_viewer.config import (
    PROJECT_ROOT,
    READY_TIMEOUT_SEC,
    WORKTREE_DIR,
    gradio_root_path,
)

LOG_DIR = WORKTREE_DIR / "_logs"


def _shared_links() -> list[tuple[str, str]]:
    """(worktree 내부 상대경로, 부모 절대경로) 쌍 목록."""
    mapping = [
        ("logs", os.getenv("RELEASE_VIEWER_SHARED_LOGS", "")),
        ("rvc/models", os.getenv("RELEASE_VIEWER_SHARED_MODELS", "")),
        ("assets/datasets", os.getenv("RELEASE_VIEWER_SHARED_DATASETS", "")),
        ("assets/audios", os.getenv("RELEASE_VIEWER_SHARED_AUDIOS", "")),
    ]
    return [(sub, target) for sub, target in mapping if target]

Status = Literal["stopped", "starting", "running", "error"]

_processes: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


class ReleaseError(RuntimeError):
    """Release Viewer 관련 복구 가능한 에러."""


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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


def _tag_exists_locally(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
    )
    return result.returncode == 0


def fetch_tag(tag: str) -> None:
    _run(
        ["git", "fetch", "origin", "--no-tags", f"refs/tags/{tag}:refs/tags/{tag}"],
        cwd=PROJECT_ROOT,
        timeout=600,
    )


def ensure_worktree(tag: str) -> Path:
    verify_git_repo()
    WORKTREE_DIR.mkdir(parents=True, exist_ok=True)
    worktree_path = WORKTREE_DIR / tag
    if not (worktree_path.exists() and (worktree_path / ".git").exists()):
        if not _tag_exists_locally(tag):
            fetch_tag(tag)
        _run(
            ["git", "worktree", "add", str(worktree_path), tag],
            cwd=PROJECT_ROOT,
            timeout=120,
        )
    setup_shared_links(worktree_path)
    return worktree_path


def setup_shared_links(worktree: Path) -> None:
    """worktree 내부 경로를 부모의 공유 데이터 경로로 심볼릭 링크한다.

    - 대상이 없는(env 미설정) 항목은 스킵 → 로컬 개발 호환
    - 이미 올바른 symlink면 스킵
    - 실존 디렉토리/파일이 있으면 `.bak_<timestamp>`로 이름 변경 후 교체
    """
    for sub_path, target in _shared_links():
        link = worktree / sub_path
        target_path = Path(target)
        if not target_path.exists():
            continue
        if link.is_symlink():
            try:
                if link.resolve() == target_path.resolve():
                    continue
            except OSError:
                pass
            link.unlink()
        elif link.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = link.with_name(f"{link.name}.bak_{timestamp}")
            link.rename(backup)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target_path, target_is_directory=True)


def _venv_python(worktree: Path) -> Path:
    return worktree / ".venv" / "bin" / "python"


def _venv_ready_marker(worktree: Path) -> Path:
    return worktree / ".venv" / ".release_viewer_ready"


def _parse_install_script(worktree: Path) -> tuple[str, list[str]]:
    """run-install.sh에서 Python 버전과 pip 플래그를 파싱한다.

    기본값: Python 3.12, 추가 플래그 없음.
    Python 버전 우선순위:
      1. `uv venv ... --python X.Y`
      2. `find_python` 스타일: `for py in python3.X python3 python`
      3. `python@X.Y` (homebrew 스타일)
    """
    script = worktree / "run-install.sh"
    python_version = "3.12"
    extra_args: list[str] = []
    if not script.exists():
        return python_version, extra_args
    try:
        content = script.read_text(errors="replace")
    except OSError:
        return python_version, extra_args

    m = re.search(r"uv\s+venv[^\n]*--python\s+(\d+\.\d+)", content)
    if m:
        python_version = m.group(1)
    else:
        m = re.search(r"for\s+py\s+in\s+python(\d+\.\d+)", content)
        if m:
            python_version = m.group(1)
        else:
            m = re.search(r"python@(\d+\.\d+)", content)
            if m:
                python_version = m.group(1)

    m = re.search(r"--extra-index-url\s+(\S+)", content)
    if m:
        extra_args += ["--extra-index-url", m.group(1)]
    m = re.search(r"--index-strategy\s+(\S+)", content)
    if m:
        extra_args += ["--index-strategy", m.group(1)]
    return python_version, extra_args


def ensure_venv(worktree: Path) -> None:
    marker = _venv_ready_marker(worktree)
    if marker.exists():
        return
    venv_dir = worktree / ".venv"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    has_uv_lock = (worktree / "uv.lock").exists()
    has_pyproject = (worktree / "pyproject.toml").exists()
    has_requirements = (worktree / "requirements.txt").exists()

    if has_uv_lock and has_pyproject:
        _run(["uv", "sync"], cwd=worktree, timeout=3600)
        marker.touch()
        return

    python_version, extra_pip_args = _parse_install_script(worktree)
    uv_env = os.environ.copy()
    uv_env["UV_PYTHON_DOWNLOADS"] = "automatic"
    _run(
        ["uv", "venv", ".venv", "--python", python_version],
        cwd=worktree,
        timeout=600,
        env=uv_env,
    )
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(_venv_python(worktree)),
            "setuptools<77",
            "wheel",
        ],
        cwd=worktree,
        timeout=300,
    )
    if has_requirements:
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(_venv_python(worktree)),
                "-r",
                "requirements.txt",
                *extra_pip_args,
            ],
            cwd=worktree,
            timeout=3600,
        )
    elif has_pyproject:
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(_venv_python(worktree)),
                "-e",
                ".",
            ],
            cwd=worktree,
            timeout=3600,
        )
    else:
        raise ReleaseError(
            f"의존성 정의 파일을 찾을 수 없습니다 (uv.lock / pyproject.toml / requirements.txt): {worktree}"
        )
    marker.touch()


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


def _tee_output(tag: str, popen: subprocess.Popen, log_file) -> None:
    """자식 stdout을 파일(원문)과 부모 stdout(프리픽스)에 동시에 기록."""
    prefix = f"[release-viewer:{tag}] "
    try:
        assert popen.stdout is not None
        for raw in iter(popen.stdout.readline, b""):
            try:
                log_file.write(raw)
            except OSError:
                pass
            try:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                sys.stdout.write(prefix + line + "\n")
                sys.stdout.flush()
            except Exception:
                pass
    finally:
        try:
            log_file.close()
        except OSError:
            pass
        try:
            if popen.stdout is not None:
                popen.stdout.close()
        except OSError:
            pass


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
        python_bin = _venv_python(worktree)
        if not python_bin.exists():
            raise ReleaseError(
                f"venv의 python을 찾을 수 없습니다: {python_bin}"
            )
        env = os.environ.copy()
        env.pop("GRADIO_ROOT_PATH", None)
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONPATH", None)
        env["PATH"] = f"{worktree / '.venv' / 'bin'}:{env.get('PATH', '')}"
        root_path = gradio_root_path(release)
        if root_path:
            env["GRADIO_ROOT_PATH"] = root_path
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{tag}.log"
        log_file = open(log_path, "ab", buffering=0)
        popen = subprocess.Popen(
            [
                str(python_bin),
                "app.py",
                "--port",
                str(port),
                "--server-name",
                "0.0.0.0",
            ],
            cwd=str(worktree),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            start_new_session=False,
        )
        tee_thread = threading.Thread(
            target=_tee_output,
            args=(tag, popen, log_file),
            name=f"release-viewer-tee-{tag}",
            daemon=True,
        )
        tee_thread.start()
        _processes[tag] = popen
        return popen


def read_log_tail(tag: str, lines: int = 30) -> str:
    log_path = LOG_DIR / f"{tag}.log"
    if not log_path.exists():
        return "(로그 파일이 없습니다)"
    try:
        content = log_path.read_text(errors="replace").splitlines()
    except OSError as exc:
        return f"(로그 읽기 실패: {exc})"
    return "\n".join(content[-lines:]) or "(로그가 비어 있습니다)"


def wait_until_ready(
    tag: str,
    port: int,
    timeout: int = READY_TIMEOUT_SEC,
) -> tuple[bool, str]:
    """포트가 준비되면 (True, ""), 실패하면 (False, 사유)를 반환."""
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        popen = _processes.get(tag)
        if popen is None:
            return False, "프로세스가 등록되어 있지 않습니다"
        rc = popen.poll()
        if rc is not None:
            return False, f"자식 프로세스가 종료되었습니다 (exit={rc})"
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True, ""
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return True, ""
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1.0)
    return False, f"타임아웃 ({timeout}초)"


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
