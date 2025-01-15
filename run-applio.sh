#!/bin/sh
printf "\033]0;Applio\007"
conda activate anai-applio
#. .venv/bin/activate

export PYTORCH_ENABLE_MPS_FALLBACK=1
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
 
clear
nohup python app.py & tail -f -n 1000 ./nohup.out
