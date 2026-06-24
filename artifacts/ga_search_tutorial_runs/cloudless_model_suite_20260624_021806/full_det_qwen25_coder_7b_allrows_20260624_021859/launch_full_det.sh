#!/usr/bin/env bash
set -euo pipefail
cd /home/mgjeong/Desktop/llm/JOILang-Server
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0
export LD_LIBRARY_PATH=
echo "[START] $(date)"
echo "[CMD] /home/mgjeong/miniconda3/envs/joi/bin/python3.10 -m utils.ga_search.model_suite_benchmark --model gpt_mg.version0_13 --model-key qwen25_coder_7b --llm-mode worker --local-model-base-dir /home/mgjeong/Desktop/llm/local_models --worker-python /home/mgjeong/miniconda3/envs/joi/bin/python3.10 --local-device cuda:0 --local-files-only true --local-trust-remote-code true --local-max-new-tokens 512 --timeout-sec 43200 --output-dir /home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859"
/home/mgjeong/miniconda3/envs/joi/bin/python3.10 -m utils.ga_search.model_suite_benchmark --model gpt_mg.version0_13 --model-key qwen25_coder_7b --llm-mode worker --local-model-base-dir /home/mgjeong/Desktop/llm/local_models --worker-python /home/mgjeong/miniconda3/envs/joi/bin/python3.10 --local-device cuda:0 --local-files-only true --local-trust-remote-code true --local-max-new-tokens 512 --timeout-sec 43200 --output-dir /home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859 2>&1 | tee /home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/nohup.log
echo "[END] $(date)"
