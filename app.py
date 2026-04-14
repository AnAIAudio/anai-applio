import gradio as gr
import sys
import os
import logging
from typing import Any
from rvc.lib.platform import platform_config
from assets.i18n.i18n import I18nAuto

platform_config()

DEFAULT_SERVER_NAME = "0.0.0.0"
DEFAULT_PORT = 6969
MAX_PORT_ATTEMPTS = 10

# Set up logging
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add current directory to sys.path
now_dir = os.getcwd()
sys.path.append(now_dir)

from tabs.inference.inference import inference_tab
from tabs.train.train import train_tab
from tabs.settings.settings import settings_tab
from tabs.preprocess.preprocessing import preprocessing_tab
from tabs.release_viewer.release_viewer import release_viewer_tab
from tabs.release_viewer.process_manager import stop_all as release_viewer_stop_all

import atexit

atexit.register(release_viewer_stop_all)

# Run prerequisites
from core import run_prerequisites_script

run_prerequisites_script(
    pretraineds_hifigan=True,
    models=True,
    exe=True,
)

i18n = I18nAuto()

client_mode = "--client" in sys.argv

with gr.Blocks(
    theme=gr.themes.Base(),
    title="AnAI-Applio",
) as Applio:
    gr.Markdown("# AnAI Applio")

    with gr.Tabs():
        with gr.TabItem(i18n("Inference")):
            inference_tab()

        with gr.TabItem(i18n("Training")):
            train_tab()

        with gr.Tab(i18n("Settings")):
            settings_tab()

        with gr.Tab(i18n("Preprocessing")):
            preprocessing_tab()

    with gr.Tab(i18n("Release Viewer")):
        release_viewer_tab()


def launch_gradio(server_name: str, server_port: int) -> None:
    Applio.launch(
        favicon_path="assets/anai_favicon.ico",
        share="--share" in sys.argv,
        inbrowser="--open" in sys.argv,
        server_name=server_name,
        server_port=server_port,
        prevent_thread_lock=client_mode,
    )


def get_value_from_args(key: str, default: Any = None) -> Any:
    if key in sys.argv:
        index = sys.argv.index(key) + 1
        if index < len(sys.argv):
            return sys.argv[index]
    return default


if __name__ == "__main__":
    port = int(get_value_from_args("--port", DEFAULT_PORT))
    server = get_value_from_args("--server-name", DEFAULT_SERVER_NAME)

    for _ in range(MAX_PORT_ATTEMPTS):
        try:
            launch_gradio(server, port)
            break
        except OSError:
            print(
                f"Failed to launch on port {port}, trying again on port {port - 1}..."
            )
            port -= 1
        except Exception as error:
            print(f"An error occurred launching Gradio: {error}")
            break
