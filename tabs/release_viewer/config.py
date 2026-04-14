"""Release Viewer 탭 설정.

각 release 태그에 대해 git worktree로 체크아웃하고 고정 포트로
태그 버전 Applio를 기동한다. iframe은 RELEASE_VIEWER_BASE_URL 환경변수의
호스트(기본값 http://localhost)에 태그별 포트를 붙여 렌더한다.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKTREE_DIR = PROJECT_ROOT / ".release_worktrees"

BASE_URL = os.getenv("RELEASE_VIEWER_BASE_URL", "http://localhost").rstrip("/")
_parsed = urlparse(BASE_URL)
IFRAME_SCHEME = _parsed.scheme or "http"
IFRAME_HOST = _parsed.hostname or "localhost"
ALLOWED_HOSTS: set[str] = {IFRAME_HOST, "localhost", "127.0.0.1"}

READY_TIMEOUT_SEC = 300

RELEASES: list[dict] = [
    {"tag": "3.6.2", "label": "3.6.2", "port": 7001},
    {"tag": "3.6.1", "label": "3.6.1", "port": 7002},
    {"tag": "3.6.0", "label": "3.6.0", "port": 7003},
    {"tag": "3.5.1", "label": "3.5.1", "port": 7004},
    {"tag": "3.5.0", "label": "3.5.0", "port": 7005},
    {"tag": "3.4.0", "label": "3.4.0", "port": 7006},
    {"tag": "3.3.1", "label": "3.3.1", "port": 7007},
    {"tag": "3.3.0", "label": "3.3.0", "port": 7008},
    {"tag": "3.2.9", "label": "3.2.9", "port": 7009},
    {"tag": "3.2.8", "label": "3.2.8", "port": 7010},
]


def find_release(tag: str) -> dict | None:
    for release in RELEASES:
        if release["tag"] == tag or release["label"] == tag:
            return release
    return None


def resolve_url(release: dict) -> str:
    return f"{BASE_URL}:{release['port']}/"
