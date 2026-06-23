# JOILang GA Feedback Notebooks

Recommended order:

1. `01_cloudless_det_feedback_ga_search.ipynb`
   - Strict DET / cloudless feedback only.
   - Start with row 1, then category sweeps, then full 280 × 10 generation.

2. `02_cloud_only_feedback_ga_search.ipynb`
   - Cloud advisor / cloud semantic judge oriented experiment.
   - Current repository still uses Strict DET for GA fitness; the notebook isolates cloud advisor transport/effectiveness.

3. `03_merged_feedback_ga_search.ipynb`
   - Runs/uses strict+cloud merge artifacts and analyzes advisor-rich feedback with GA/advisor results.

Before running:
```bash
export JOILANG_BASE_DIR=/root/llm/JOILang-Server
export MODEL_KEY=qwen25_coder_14b
export JOI_V15_LOCAL_DEVICE=cuda:0
export JOI_V15_OPENAI_API_KEY=...
# or OPENAI_API_KEY / JOI_EVAL_OPENAI_API_KEY
```
