import os
import shutil
import stat
import tempfile
from typing import List, Dict
import gradio as gr
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()


def _on_rm_error(func, path, exc_info):
    """
    shutil.rmtree onerror 콜백:
    - Windows에서 읽기 전용 파일/디렉토리로 인한 PermissionError를 우회
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass  # 마지막 시도 실패는 상위에서 집계


def list_batch_zip_temp_dirs(prefix: str = "batch_zip_") -> List[str]:
    """
    tempfile.gettempdir() 하위에서 prefix로 시작하는 디렉토리 목록 반환
    """
    root = tempfile.gettempdir()
    results: List[str] = []
    try:
        for name in os.listdir(root):
            if not name.startswith(prefix):
                continue
            full = os.path.join(root, name)
            if os.path.isdir(full):
                results.append(full)
    except Exception:
        # tempdir 접근 실패 등은 빈 목록 반환
        pass
    return results


def cleanup_all_batch_zip_temp_dirs(prefix: str = "batch_zip_") -> Dict[str, object]:
    """
    batch_zip_ 접두사로 생성된 모든 임시 디렉토리 삭제
    Returns:
      {
        "total": int,          # 검사한 디렉토리 수
        "removed": int,        # 성공적으로 삭제된 수
        "failed": int,         # 삭제 실패 수
        "failed_paths": list,  # 실패 경로 목록
      }
    """
    dirs = list_batch_zip_temp_dirs(prefix=prefix)
    removed = 0
    failed = 0
    failed_paths: List[str] = []

    for d in dirs:
        try:
            shutil.rmtree(d, onerror=_on_rm_error)
            removed += 1
        except Exception:
            failed += 1
            failed_paths.append(d)

    return {
        "total": len(dirs),
        "removed": removed,
        "failed": failed,
        "failed_paths": failed_paths,
    }


def cleanup_all_batch_zip_temp_dirs_as_text(prefix: str = "batch_zip_") -> str:
    res = cleanup_all_batch_zip_temp_dirs(prefix=prefix)
    msg = [
        f"총 대상: {res['total']}",
        f"삭제 성공: {res['removed']}",
        f"삭제 실패: {res['failed']}",
    ]
    if res["failed_paths"]:
        msg.append("실패 경로:")
        msg.extend(f" - {p}" for p in res["failed_paths"])
    return "\n".join(msg)


def cleanup_logs_dir(keep_names=("mute", "mute_spin", "reference", "zips")):
    """
    logs 디렉토리 바로 아래에서 keep_names에 있는 디렉토리만 제외하고 전부 삭제.
    예) logs/mute, logs/mute_spin, logs/reference, logs/zips 는 남기고 나머지는 삭제.
    """
    now_dir = os.getcwd()
    logs_root = os.path.join(now_dir, "logs")

    if not os.path.isdir(logs_root):
        return []

    keep_set = set(keep_names)
    dir_list = []

    for name in os.listdir(logs_root):
        full = os.path.join(logs_root, name)

        # logs 바로 아래의 "디렉토리" 중 keep_names는 보존
        if os.path.isdir(full) and name in keep_set:
            continue

        try:
            if os.path.isdir(full) and not os.path.islink(full):
                shutil.rmtree(full, onerror=_on_rm_error)
            else:
                os.remove(full)

            dir_list.append(full)
        except IsADirectoryError:
            shutil.rmtree(full, onerror=_on_rm_error)
        except Exception:
            # 필요하면 실패 항목을 모아서 리턴/로그로 남기도록 확장 가능
            pass

    return dir_list


def cleanup_logs_dir_result() -> str:
    remove_dir_list = cleanup_logs_dir()
    message = []
    for dir_text in remove_dir_list:
        message.append(f"삭제 경로: {dir_text}")
    return "\n".join(message)


def cleanup_temp_dir_tab():
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 임시파일 전체 정리 ")
            cleanup_btn = gr.Button(
                i18n("Temp directory Clean up"),
                variant="secondary",
            )
            cleanup_all_status = gr.Textbox(label="정리 상태", lines=6)
            cleanup_btn.click(
                fn=cleanup_all_batch_zip_temp_dirs_as_text,
                inputs=[],
                outputs=[cleanup_all_status],
            )

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Train 디렉토리/파일 정리 ")
            cleanup_logs_btn = gr.Button(
                i18n("Clean up"),
                variant="secondary",
            )
            cleanup_logs_status = gr.Textbox(label="정리 상태", lines=6)
            cleanup_logs_btn.click(
                fn=cleanup_logs_dir_result,
                inputs=[],
                outputs=[cleanup_logs_status],
            )
