import os
import sys
import gradio as gr
from tabs.preprocess.audio_processing.cleanup_temp_dir import cleanup_temp_dir_tab
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()
now_dir = os.getcwd()
sys.path.append(now_dir)


def preprocessing_tab():
    with gr.TabItem(i18n("Temp directory Clean up")):
        cleanup_temp_dir_tab()