import os
import gradio as gr
from assets.i18n.i18n import I18nAuto


i18n = I18nAuto()


def batch_pack_converted(
    temp_dir: str | None, converted_dir: str | None, converted_zip: str | None
):
    """
    Convert가 완료된 후 converted_dir을 ZIP으로 묶어 다운로드 제공.
    """
    import zipfile

    if not temp_dir or not converted_dir:
        return None, i18n("Nothing to package: prepare and convert first.")
    if not os.path.exists(converted_dir):
        return None, i18n("Output folder not found. Make sure conversion is completed.")

    # ZIP 경로 준비
    if not converted_zip:
        converted_zip = os.path.join(temp_dir, "converted.zip")

    # 기존 파일 삭제 후 재생성
    try:
        if os.path.exists(converted_zip):
            os.remove(converted_zip)
        with zipfile.ZipFile(
            converted_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zf:
            for root, _, files in os.walk(converted_dir):
                for f in files:
                    fpath = os.path.join(root, f)
                    # ZIP 내 경로는 converted/ 이하로
                    arcname = os.path.relpath(
                        fpath, start=os.path.dirname(converted_dir)
                    )
                    zf.write(fpath, arcname)
        return converted_zip, i18n(
            "Packaging completed. You can download the ZIP file."
        )
    except Exception as e:
        return None, f"{i18n('Failed to package converted folder')}: {e}"


def batch_cleanup_temp(temp_dir: str | None):
    import shutil

    if not temp_dir:
        return (
            None,
            None,
            None,
            None,
            i18n("No temp directory to clean."),
            None,
            None,
        )
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return (
            None,
            None,
            None,
            None,
            i18n("Temp directory cleaned up."),
            None,
            None,
        )
    except Exception as e:
        return (
            temp_dir,
            None,
            None,
            None,
            f"{i18n('Failed to cleanup temp directory')}: {e}",
            None,
            None,
        )


def _sanitize_segment(seg: str) -> str:
    forbidden = '<>:"/\\|?*'
    seg = seg.rstrip(" .")
    for ch in forbidden:
        seg = seg.replace(ch, "_")
    return seg


def _safe_join(root: str, rel_path: str) -> str | None:
    parts = []
    for p in rel_path.replace("\\", "/").split("/"):
        if p in ("", ".", ".."):
            if p == "..":
                return None
            continue
        # macOS AppleDouble 무시
        if p.startswith("._"):
            return None
        sp = _sanitize_segment(p)
        if not sp:
            return None
        parts.append(sp)
    if not parts:
        return None
    target = os.path.join(root, *parts)
    norm_root = os.path.abspath(root)
    norm_target = os.path.abspath(target)
    if not norm_target.startswith(norm_root + os.sep):
        return None
    return target


def _safe_extract_zip_to_temp(zip_path: str) -> tuple[str, str]:
    """
    zip_path를 temp_dir에 추출.
    반환: (temp_dir, extracted_root)
    """
    import tempfile, zipfile, shutil, unicodedata

    temp_dir = tempfile.mkdtemp(prefix="batch_zip_")
    extracted_root = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_root, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r", allowZip64=True) as zf:
        for info in zf.infolist():
            name = info.filename
            # macOS 메타데이터/디렉토리 항목 건너뛰기
            if name.endswith("/") or name.startswith("__MACOSX/") or "/._" in name:
                continue

            # 파일명 인코딩 복원
            if info.flag_bits & 0x800:
                # UTF-8 플래그가 있는 경우: NFC로 정규화 (macOS는 종종 NFD)
                name = unicodedata.normalize("NFC", name)
            else:
                # UTF-8 플래그 없음: CP437로 잘못 해석된 name을 원시 바이트로 환원
                try:
                    raw = name.encode("cp437", errors="ignore")
                except Exception:
                    raw = None
                if raw:
                    decoded = None
                    for enc in ("cp949", "euc-kr", "mac_roman"):
                        try:
                            decoded = raw.decode(enc, errors="strict")
                            decoded = unicodedata.normalize("NFC", decoded)
                            break
                        except Exception:
                            continue
                    if decoded:
                        name = decoded
                    # 실패 시 원본 name 유지

            out_path = _safe_join(extracted_root, name)
            if not out_path:
                continue
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return temp_dir, extracted_root


def prepare_batch_from_zip(zip_path: str | None):
    """
    - ZIP을 임시 디렉토리에 추출
    - input/output Textbox 값 업데이트
    - 상태값 업데이트
    """
    if not zip_path or not os.path.exists(zip_path):
        return (
            gr.update(),  # input_folder_batch
            gr.update(),  # output_folder_batch
            None,
            None,
            None,
            None,
            i18n("Please upload a valid ZIP file."),
        )
    if not zip_path.lower().endswith(".zip"):
        return (
            gr.update(),
            gr.update(),
            None,
            None,
            None,
            None,
            i18n("Only ZIP files are supported."),
        )

    try:
        temp_dir, extracted_root = _safe_extract_zip_to_temp(zip_path)
        converted_dir = os.path.join(temp_dir, "converted")
        os.makedirs(converted_dir, exist_ok=True)
        converted_zip = os.path.join(temp_dir, "converted.zip")

        msg = [
            i18n("Prepared working directory."),
            f"temp_dir: {temp_dir}",
            f"input: {extracted_root}",
            f"output: {converted_dir}",
        ]
        return (
            extracted_root,  # input_folder_batch
            converted_dir,  # output_folder_batch
            temp_dir,
            extracted_root,
            converted_dir,
            converted_zip,
            "\n".join(msg),
        )
    except Exception as e:
        return (
            gr.update(),
            gr.update(),
            None,
            None,
            None,
            None,
            f"{i18n('An error occurred while preparing from ZIP')}: {e}",
        )
