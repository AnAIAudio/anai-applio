import os
import shutil
import tempfile
import zipfile
import wave
from typing import List, Optional, Tuple

import gradio as gr
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()


def _extract_zip_to_temp(zip_path: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix="merge_wav_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)
    return temp_dir


def _is_wav(path: str) -> bool:
    return path.lower().endswith(".wav")


def _wav_params_and_frames(
    path: str,
) -> Optional[Tuple[Tuple[int, int, int, int, str, int], int]]:
    try:
        with wave.open(path, "rb") as wf:
            params = (
                wf.getparams()
            )  # (nchannels, sampwidth, framerate, nframes, comptype, compname)
            return params, params.nframes
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
            params, nframes = info
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
      - skipped_files: skipped due to parameter mismatch
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
        # 생성된 파일이 유효하지 않다면 제거
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        raise ValueError("파라미터 불일치 또는 오류로 병합할 수 있는 WAV가 없습니다.")
    return out_path, used, skipped


def _process_zip(zip_file_obj) -> Tuple[Optional[str], str, Optional[str]]:
    """
    zip_file_obj: gr.File 컴포넌트가 전달하는 파일(딕셔너리 또는 경로 문자열)
    Returns:
      - merged_file_path (for download)
      - message
      - temp_dir (to store in state)
    """
    if zip_file_obj is None:
        return None, "ZIP 파일을 업로드하세요.", None

    # Gradio는 dict 형태 또는 str(경로)로 올 수 있음
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
        temp_dir = _extract_zip_to_temp(zip_path)
        wavs = _find_valid_wavs(temp_dir)
        if not wavs:
            return None, "0초 초과 WAV 파일을 찾지 못했습니다.", temp_dir

        out_path = os.path.join(temp_dir, "merged.wav")
        out_path, used, skipped = _merge_wavs(wavs, out_path)

        msg_lines = [
            f"총 WAV 탐색: {len(wavs)}",
            f"병합 성공: {len(used)}",
            f"스킵: {len(skipped)}",
        ]
        if skipped:
            msg_lines.append("스킵 사유: 포맷 불일치, 0프레임, 또는 손상 파일")
        msg_lines.append("다운로드 후 '임시 폴더 정리' 버튼으로 정리하세요.")
        return out_path, "\n".join(msg_lines), temp_dir
    except zipfile.BadZipFile:
        return None, "손상되었거나 잘못된 ZIP 파일입니다.", None
    except Exception as e:
        return None, f"오류가 발생했습니다: {e}", None


def _cleanup_temp(temp_dir: Optional[str]) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Cleans up the temp directory and clears the file output.
    Returns:
      - file_output -> None
      - message
      - state -> None
    """
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
                label="ZIP 파일 업로드", file_types=[".zip"], type="filepath"
            )

            with gr.Row():
                merge_btn = gr.Button("병합하기", variant="primary")
                cleanup_btn = gr.Button("임시 폴더 정리", variant="secondary")

            merged_file = gr.File(label="병합된 WAV 파일", interactive=False)
            status_box = gr.Textbox(label="상태", lines=6)

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
