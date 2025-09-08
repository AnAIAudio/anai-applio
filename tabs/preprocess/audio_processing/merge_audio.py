import os
import shutil
import tempfile
import zipfile
import wave
from typing import List, Optional, Tuple

import gradio as gr
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()


# --- Path utilities ----------------------------------------------------------

_WINDOWS_FORBIDDEN = '<>:"/\\|?*'


def _sanitize_segment(seg: str) -> str:
    # Skip dot-underscore segments
    if seg.startswith("._"):
        return ""
    # Strip trailing spaces/dots which are invalid on Windows
    seg = seg.rstrip(" .")
    # Remove forbidden characters
    for ch in _WINDOWS_FORBIDDEN:
        seg = seg.replace(ch, "_")
    return seg


def _safe_join(root: str, rel_path: str) -> Optional[str]:
    # Normalize path, split, sanitize segments
    parts = []
    for p in rel_path.replace("\\", "/").split("/"):
        if p in ("", ".", ".."):
            # Skip empty/current and reject traversal
            if p == "..":
                return None
            continue
        sp = _sanitize_segment(p)
        if not sp:
            # Entire segment sanitized away (e.g., "._file") -> skip this entry
            return None
        parts.append(sp)
    target = os.path.join(root, *parts) if parts else None
    if not target:
        return None
    # Prevent path traversal
    norm_root = os.path.abspath(root)
    norm_target = os.path.abspath(target)
    if not norm_target.startswith(norm_root + os.sep):
        return None
    return target


# --- ZIP extract (safe) ------------------------------------------------------


def _safe_extract_zip_to_temp(zip_path: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix="merge_wav_")
    with zipfile.ZipFile(zip_path, "r", allowZip64=True) as zf:
        for info in zf.infolist():
            name = info.filename

            # Skip macOS metadata folders and AppleDouble files
            if name.startswith("__MACOSX/") or "/._" in name or name.endswith("/"):
                continue

            out_path = _safe_join(temp_dir, name)
            if not out_path:
                # Skipped due to sanitation or traversal
                continue

            # Ensure parent dirs
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # Extract file
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return temp_dir


# --- WAV helpers -------------------------------------------------------------


def _is_wav(path: str) -> bool:
    # Ignore AppleDouble artifacts explicitly
    base = os.path.basename(path)
    if base.startswith("._"):
        return False
    return path.lower().endswith(".wav")


def _wav_params_and_frames(
    path: str,
) -> Optional[Tuple[Tuple[int, int, int, int, str, int], int]]:
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        with wave.open(path, "rb") as wf:
            params = (
                wf.getparams()
            )  # (nchannels, sampwidth, framerate, nframes, comptype, compname)
            return params, params.nframes
    except (
        wave.Error,
        EOFError,
        FileNotFoundError,
        IsADirectoryError,
        PermissionError,
    ):
        return None
    except Exception:
        return None


def _find_valid_wavs(root_dir: str) -> List[str]:
    valid = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if not _is_wav(fpath):
                continue
            info = _wav_params_and_frames(fpath)
            if not info:
                continue
            _, nframes = info
            if nframes > 0:
                valid.append(fpath)
    return sorted(valid)


def _merge_wavs(
    wav_files: List[str], out_path: str
) -> Tuple[str, List[str], List[str]]:
    """
    Returns:
      - out_path: output wav file path
      - used_files: actually merged files
      - skipped_files: skipped due to parameter mismatch or errors
    """
    if not wav_files:
        raise ValueError("병합할 WAV 파일이 없습니다.")

    first_info = _wav_params_and_frames(wav_files[0])
    if not first_info:
        raise ValueError("첫 WAV 파일을 읽는 중 오류가 발생했습니다.")
    base_params, _ = first_info
    nchannels, sampwidth, framerate, _, comptype, compname = base_params

    used, skipped = [], []
    with wave.open(out_path, "wb") as wout:
        wout.setparams((nchannels, sampwidth, framerate, 0, comptype, compname))
        for wf_path in wav_files:
            info = _wav_params_and_frames(wf_path)
            if not info:
                skipped.append(wf_path)
                continue
            params, nframes = info
            if nframes <= 0:
                skipped.append(wf_path)
                continue
            if (params.nchannels, params.sampwidth, params.framerate) != (
                nchannels,
                sampwidth,
                framerate,
            ):
                skipped.append(wf_path)
                continue
            try:
                with wave.open(wf_path, "rb") as win:
                    frames = win.readframes(params.nframes)
                    wout.writeframes(frames)
                used.append(wf_path)
            except Exception:
                skipped.append(wf_path)

    if not used:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        raise ValueError("파라미터 불일치 또는 오류로 병합할 수 있는 WAV가 없습니다.")
    return out_path, used, skipped


# --- Gradio callbacks --------------------------------------------------------


def _process_zip(zip_file_obj) -> Tuple[Optional[str], str, Optional[str]]:
    """
    zip_file_obj: gr.File 컴포넌트가 전달하는 파일(경로 문자열 또는 dict)
    Returns:
      - merged_file_path (for download)
      - message
      - temp_dir (to store in state)
    """
    if zip_file_obj is None:
        return None, "ZIP 파일을 업로드하세요.", None

    zip_path = (
        zip_file_obj
        if isinstance(zip_file_obj, str)
        else zip_file_obj.get("name") or zip_file_obj.get("orig_name")
    )
    if not zip_path or not os.path.exists(zip_path):
        return None, "유효한 ZIP 파일 경로를 찾을 수 없습니다.", None

    if not zip_path.lower().endswith(".zip"):
        return None, "ZIP 형식의 파일만 업로드하세요.", None

    try:
        temp_dir = _safe_extract_zip_to_temp(zip_path)
        wavs = _find_valid_wavs(temp_dir)
        if not wavs:
            return None, "0초 초과 WAV 파일을 찾지 못했습니다.", temp_dir

        out_path = os.path.join(temp_dir, "merged.wav")
        out_path, used, skipped = _merge_wavs(wavs, out_path)

        msg_lines = [
            f"총 WAV 후보: {len(wavs)}",
            f"병합 성공: {len(used)}",
            f"스킵: {len(skipped)}",
        ]
        if skipped:
            msg_lines.append(
                "스킵 사유: 포맷 불일치, 0프레임, 손상/메타데이터 파일(예: ._ 파일)"
            )
        msg_lines.append("다운로드 후 '임시 폴더 정리' 버튼으로 정리하세요.")
        return out_path, "\n".join(msg_lines), temp_dir
    except zipfile.BadZipFile:
        return None, "손상되었거나 잘못된 ZIP 파일입니다.", None
    except Exception as e:
        return None, f"오류가 발생했습니다: {e}", None


def _cleanup_temp(temp_dir: Optional[str]) -> Tuple[Optional[str], str, Optional[str]]:
    if not temp_dir:
        return None, "정리할 임시 폴더가 없습니다.", None
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, "임시 폴더를 정리했습니다.", None
    except Exception as e:
        return None, f"임시 폴더 정리 중 오류: {e}", temp_dir


def merge_audio_tab():
    with gr.Row():
        with gr.Column():
            gr.Markdown(
                "### ZIP 업로드 → 임시 추출 → WAV 선별/병합 → 파일 다운로드 → 임시 폴더 정리"
            )

            zip_input = gr.File(
                label="ZIP 파일 업로드",
                file_types=[".zip"],
                type="filepath",
            )

            with gr.Row():
                merge_btn = gr.Button(
                    i18n("Merge Audio"),
                    variant="primary",
                )
                cleanup_btn = gr.Button(
                    i18n("Temp directory Clean up"),
                    variant="secondary",
                )

            merged_file = gr.File(label=i18n("Merged audio file"), interactive=False)
            status_box = gr.Textbox(label=i18n("Status"), lines=6)

            # temp_dir 상태 저장
            temp_state = gr.State(value=None)

            merge_btn.click(
                fn=_process_zip,
                inputs=[zip_input],
                outputs=[merged_file, status_box, temp_state],
            )

            cleanup_btn.click(
                fn=_cleanup_temp,
                inputs=[temp_state],
                outputs=[merged_file, status_box, temp_state],
            )
