import gradio as gr
import os
import sys
import json

now_dir = os.getcwd()


def stop_train(model_name: str):
    pid_file_path = os.path.join(now_dir, "logs", model_name, "config.json")
    try:
        with open(pid_file_path, "r") as pid_file:
            pid_data = json.load(pid_file)
            pids = pid_data.get("process_pids", [])
        with open(pid_file_path, "w") as pid_file:
            pid_data.pop("process_pids", None)
            json.dump(pid_data, pid_file, indent=4)
        for pid in pids:
            os.kill(pid, 9)
    except:
        pass


def stop_infer():
    pid_file_path = os.path.join(now_dir, "assets", "infer_pid.txt")
    try:
        with open(pid_file_path, "r") as pid_file:
            pids = [int(pid) for pid in pid_file.readlines()]
        for pid in pids:
            os.kill(pid, 9)
        os.remove(pid_file_path)
    except:
        pass


def restart_applio():
    restart_applio_swarm()

    # 아래는 Original 재시작 프로세스
    # if os.name != "nt":
    #     os.system("clear")
    # else:
    #     os.system("cls")
    # python = sys.executable
    # os.execl(python, python, *sys.argv)


def restart_applio_swarm(model_name: str | None = None):
    import os
    import signal
    import threading
    import time

    try:
        if model_name:
            stop_train(model_name)
    except Exception:
        pass

    try:
        stop_infer()
    except Exception:
        pass

    def _shutdown():
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            pass

        time.sleep(2)
        os._exit(1)  # Swarm restart_policy: on-failure에서 재기동

    threading.Thread(target=_shutdown, daemon=True).start()


from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()


def restart_tab():
    with gr.Row():
        with gr.Column():
            restart_button = gr.Button(i18n("Restart Applio"))
            restart_button.click(
                fn=restart_applio,
                inputs=[],
                outputs=[],
            )
