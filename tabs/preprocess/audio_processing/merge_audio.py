import gradio as gr
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()


def merge_audio_tab():
    with gr.Row():
        with gr.Column():
            gr.Textbox(label=i18n("Path to Audio"), interactive=True)
