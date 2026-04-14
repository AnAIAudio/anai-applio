from urllib.parse import urlparse

import gradio as gr

from assets.i18n.i18n import I18nAuto
from tabs.release_viewer.config import (
    ALLOWED_HOSTS,
    RELEASES,
    find_release,
    resolve_url,
)
from tabs.release_viewer.process_manager import (
    ReleaseError,
    ensure_venv,
    ensure_worktree,
    get_status,
    read_log_tail,
    start_process,
    stop_process,
    wait_until_ready,
)

i18n = I18nAuto()


EMPTY_IFRAME = (
    '<div style="padding:24px;color:#888;border:1px dashed #888;">'
    "실행 중인 인스턴스가 없습니다. 태그를 선택하고 Start를 눌러주세요."
    "</div>"
)


def _iframe_html(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_HOSTS:
        return (
            '<div style="padding:16px;border:1px solid #c00;color:#c00;">'
            f"허용되지 않은 URL입니다: {url}"
            "</div>"
        )
    return (
        f'<iframe src="{url}" width="100%" height="900" '
        'style="border:0;"></iframe>'
    )


def _start_flow(label: str):
    release = find_release(label)
    if release is None:
        yield "❌ 알 수 없는 태그입니다.", EMPTY_IFRAME
        return
    tag = release["tag"]
    port = release["port"]

    status = get_status(tag, port)
    if status == "running":
        yield f"✅ 이미 실행 중입니다 (포트 {port})", _iframe_html(resolve_url(release))
        return

    try:
        yield f"⏳ worktree 준비 중… ({tag})", EMPTY_IFRAME
        worktree = ensure_worktree(tag)

        yield "🔄 의존성 설치 중… (uv sync, 최초 1회는 수 분 소요)", EMPTY_IFRAME
        ensure_venv(worktree)

        yield f"🚀 Applio 기동 중… (포트 {port})", EMPTY_IFRAME
        start_process(release)

        yield "⌛ 기동 완료 대기 중… (최대 300초)", EMPTY_IFRAME
        ready, reason = wait_until_ready(tag, port)
        if not ready:
            tail = read_log_tail(tag, lines=30)
            yield (
                f"❌ 기동 실패: {reason}\n\n```\n{tail}\n```",
                EMPTY_IFRAME,
            )
            return

        yield f"✅ 실행 중 (포트 {port})", _iframe_html(resolve_url(release))
    except ReleaseError as exc:
        yield f"❌ 실패: {exc}", EMPTY_IFRAME
    except Exception as exc:  # noqa: BLE001
        yield f"❌ 예기치 못한 에러: {exc}", EMPTY_IFRAME


def _stop_flow(label: str):
    release = find_release(label)
    if release is None:
        return "❌ 알 수 없는 태그입니다.", EMPTY_IFRAME
    stopped = stop_process(release["tag"])
    if stopped:
        return f"🛑 정지됨 ({release['tag']})", EMPTY_IFRAME
    return f"ℹ️ 실행 중인 프로세스가 없습니다 ({release['tag']})", EMPTY_IFRAME


def release_viewer_tab():
    choices = [r["label"] for r in RELEASES]
    default_label = choices[0] if choices else None

    gr.Markdown(
        i18n(
            "선택한 태그 버전의 Applio를 로컬 포트에 기동하고 아래 iframe으로 임베드합니다."
        )
    )

    with gr.Row():
        tag_dropdown = gr.Dropdown(
            label=i18n("Release Tag"),
            choices=choices,
            value=default_label,
            interactive=True,
            scale=3,
        )
        start_btn = gr.Button(i18n("▶ Start"), variant="primary", scale=1)
        stop_btn = gr.Button(i18n("■ Stop"), variant="stop", scale=1)

    status_md = gr.Markdown(i18n("대기 중"))
    iframe_html = gr.HTML(value=EMPTY_IFRAME)

    start_btn.click(
        fn=_start_flow,
        inputs=tag_dropdown,
        outputs=[status_md, iframe_html],
    )
    stop_btn.click(
        fn=_stop_flow,
        inputs=tag_dropdown,
        outputs=[status_md, iframe_html],
    )
