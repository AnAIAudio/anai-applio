"""
tabs/inference/infer_utils/multi_infer.py

ZIP → 압축 해제 → 파일별 단건 추론 → 결과 ZIP 반환
run_batch_infer_script 를 사용하지 않고 run_infer_script 를 직접 반복 호출하여
- 파일별 진행률 실시간 스트리밍 (Gradio generator)
- 실패 파일 스킵 + 실패 목록 최종 알림
- 출력 파일명 원본명 유지 (확장자만 export_format으로 변경)
을 지원합니다.
"""

import os
from typing import Generator

from assets.i18n.i18n import I18nAuto
from core import run_infer_script
from tabs.inference.infer_utils.batch_control import (
    _safe_extract_zip_to_temp,
    batch_pack_converted,
)

i18n = I18nAuto()

SUPPORTED_AUDIO_EXTS = {
    "wav",
    "mp3",
    "flac",
    "ogg",
    "opus",
    "m4a",
    "mp4",
    "aac",
    "alac",
    "wma",
    "aiff",
    "webm",
    "ac3",
}


def collect_audio_files(root_dir: str) -> list:
    """root_dir 하위의 지원 오디오 파일 경로 목록 반환 (재귀)."""
    result = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in sorted(filenames):
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext in SUPPORTED_AUDIO_EXTS:
                result.append(os.path.join(dirpath, fname))
    return result


def run_multi_infer(
    zip_path,
    pth_path,
    index_path,
    pitch,
    index_rate,
    volume_envelope,
    protect,
    f0_method,
    split_audio,
    f0_autotune,
    f0_autotune_strength,
    proposed_pitch,
    proposed_pitch_threshold,
    clean_audio,
    clean_strength,
    export_format,
    embedder_model,
    embedder_model_custom,
    formant_shifting,
    formant_qfrency,
    formant_timbre,
    post_process,
    db_compensation,
    reverb,
    pitch_shift,
    limiter,
    gain,
    distortion,
    chorus,
    bitcrush,
    clipping,
    compressor,
    delay,
    reverb_room_size,
    reverb_damping,
    reverb_wet_gain,
    reverb_dry_gain,
    reverb_width,
    reverb_freeze_mode,
    pitch_shift_semitones,
    limiter_threshold,
    limiter_release_time,
    gain_db,
    distortion_gain,
    chorus_rate,
    chorus_depth,
    chorus_center_delay,
    chorus_feedback,
    chorus_mix,
    bitcrush_bit_depth,
    clipping_threshold,
    compressor_threshold,
    compressor_ratio,
    compressor_attack,
    compressor_release,
    delay_seconds,
    delay_feedback,
    delay_mix,
    sid,
):
    """
    Gradio generator.
    Yields: (progress_text, temp_dir, extracted_root, converted_dir, converted_zip_path_or_None)
    마지막 yield에서 converted_zip이 채워지면 다운로드 가능.
    """
    # ── 유효성 검사 ──────────────────────────────────────────────
    if not zip_path or not os.path.exists(zip_path):
        yield i18n("Please upload a valid ZIP file."), None, None, None, None
        return
    if not zip_path.lower().endswith(".zip"):
        yield i18n("Only ZIP files are supported."), None, None, None, None
        return
    if not pth_path:
        yield i18n("Please select a voice model (PTH file)."), None, None, None, None
        return

    # ── ZIP 해제 ─────────────────────────────────────────────────
    try:
        temp_dir, extracted_root = _safe_extract_zip_to_temp(zip_path)
    except Exception as e:
        yield "{}:  {}".format(i18n("Failed to extract ZIP"), e), None, None, None, None
        return

    converted_dir = os.path.join(temp_dir, "converted")
    os.makedirs(converted_dir, exist_ok=True)
    converted_zip = os.path.join(temp_dir, "converted.zip")

    # ── 오디오 파일 수집 ──────────────────────────────────────────
    audio_files = collect_audio_files(extracted_root)
    total = len(audio_files)

    if total == 0:
        yield (
            i18n("No supported audio files found in the ZIP."),
            temp_dir,
            extracted_root,
            converted_dir,
            None,
        )
        return

    yield (
        "{} {} {}".format(
            i18n("Found"), total, i18n("audio files. Starting conversion...")
        ),
        temp_dir,
        extracted_root,
        converted_dir,
        None,
    )

    # ── 파일별 추론 ───────────────────────────────────────────────
    failed = []
    fmt = export_format.lower()

    for idx, input_path in enumerate(audio_files, start=1):
        stem = os.path.splitext(os.path.basename(input_path))[0]
        output_filename = "{}_converted.{}".format(stem, fmt)
        output_path = os.path.join(converted_dir, output_filename)

        yield (
            "[{}/{}] {}: {}".format(
                idx, total, i18n("Converting"), os.path.basename(input_path)
            ),
            temp_dir,
            extracted_root,
            converted_dir,
            None,
        )

        try:
            run_infer_script(
                pitch=pitch,
                index_rate=index_rate,
                volume_envelope=volume_envelope,
                protect=protect,
                f0_method=f0_method,
                input_path=input_path,
                output_path=output_path,
                pth_path=pth_path,
                index_path=index_path,
                split_audio=split_audio,
                f0_autotune=f0_autotune,
                f0_autotune_strength=f0_autotune_strength,
                proposed_pitch=proposed_pitch,
                proposed_pitch_threshold=proposed_pitch_threshold,
                clean_audio=clean_audio,
                clean_strength=clean_strength,
                export_format=export_format,
                embedder_model=embedder_model,
                embedder_model_custom=embedder_model_custom,
                formant_shifting=formant_shifting,
                formant_qfrency=formant_qfrency,
                formant_timbre=formant_timbre,
                post_process=post_process,
                db_compensation=db_compensation,
                reverb=reverb,
                pitch_shift=pitch_shift,
                limiter=limiter,
                gain=gain,
                distortion=distortion,
                chorus=chorus,
                bitcrush=bitcrush,
                clipping=clipping,
                compressor=compressor,
                delay=delay,
                reverb_room_size=reverb_room_size,
                reverb_damping=reverb_damping,
                reverb_wet_gain=reverb_wet_gain,
                reverb_dry_gain=reverb_dry_gain,
                reverb_width=reverb_width,
                reverb_freeze_mode=reverb_freeze_mode,
                pitch_shift_semitones=pitch_shift_semitones,
                limiter_threshold=limiter_threshold,
                limiter_release_time=limiter_release_time,
                gain_db=gain_db,
                distortion_gain=distortion_gain,
                chorus_rate=chorus_rate,
                chorus_depth=chorus_depth,
                chorus_center_delay=chorus_center_delay,
                chorus_feedback=chorus_feedback,
                chorus_mix=chorus_mix,
                bitcrush_bit_depth=bitcrush_bit_depth,
                clipping_threshold=clipping_threshold,
                compressor_threshold=compressor_threshold,
                compressor_ratio=compressor_ratio,
                compressor_attack=compressor_attack,
                compressor_release=compressor_release,
                delay_seconds=delay_seconds,
                delay_feedback=delay_feedback,
                delay_mix=delay_mix,
                sid=sid,
            )
            yield (
                "[{}/{}] OK {}".format(idx, total, os.path.basename(input_path)),
                temp_dir,
                extracted_root,
                converted_dir,
                None,
            )
        except Exception as e:
            failed.append(os.path.basename(input_path))
            yield (
                "[{}/{}] FAIL {}: {}".format(
                    idx, total, os.path.basename(input_path), e
                ),
                temp_dir,
                extracted_root,
                converted_dir,
                None,
            )

    # ── 결과 ZIP 생성 ─────────────────────────────────────────────
    zip_result, pack_msg = batch_pack_converted(temp_dir, converted_dir, converted_zip)

    summary_lines = [
        i18n("Conversion complete."),
        "{}: {}/{}".format(i18n("Success"), total - len(failed), total),
    ]
    if failed:
        summary_lines.append("{}: {}".format(i18n("Failed files"), ", ".join(failed)))
    summary_lines.append(pack_msg)

    yield (
        "\n".join(summary_lines),
        temp_dir,
        extracted_root,
        converted_dir,
        zip_result,
    )
