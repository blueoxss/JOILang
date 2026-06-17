# /joi_lang_evaluation/main_evaluator.py
"""
JOI Lang 하이브리드 평가 파이프라인 (다중 모드 지원)

실행 모드:
1) 기본 (배치 하이브리드): `python main_evaluator.py`
   - CSV 모든 라인에 대해 hybrid(DET+LANG+GPT) 수행
   - 환경변수 EVAL_LIMIT 로 상위 N개만 제한 가능(예: EVAL_LIMIT=50)

2) 로컬 단일 행:
   `python main_evaluator.py [모드들] {row_index} [model_version_path]`
   - [모드들]: det | lang | gpt | hybrid | det lang | det gpt | lang gpt | det lang gpt
   - {row_index}: 0-based 행 번호
   - [model_version_path]: (옵션) config.DEFAULT_MODEL_PATH 하위 버전 (예: 'version0_6')
"""

# /joi_lang_evaluation/main_evaluator.py
"""
JOI Lang 하이브리드 평가 파이프라인 (다중 모드 + 모델 선택 지원)

실행 예시:
  # 전체 하이브리드 배치 (기본 joi)
  python main_evaluator.py

  # 로컬 단일 행 (모드/모델/인덱스/옵션버전)
  python main_evaluator.py hybrid 20
  python main_evaluator.py hybrid cap 20
  python main_evaluator.py det lang joi 5
  python main_evaluator.py det gpt cap 12 version0_8
"""
import config
import pandas as pd
import numpy as np
import json
import sys
import os
import ast
from datetime import datetime
from tqdm import tqdm
import importlib
import time
import re
from typing import Any, Dict, Optional, List, Union
import traceback
from pathlib import Path

# ---------- 유틸 ----------
def _extract_json_from_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 1)[1]
        if "\n" in s:
            s = s.split("\n", 1)[1]
        if "```" in s:
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    return s

def _safe_load_json(raw):
    import json as _json
    import ast as _ast
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, ""
    s = str(raw)
    s = _extract_json_from_text(s).strip()
    if not s:
        return None, ""
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    try:
        obj = _json.loads(s)
        return obj, s
    except Exception:
        pass
    try:
        obj = _ast.literal_eval(s)
        if isinstance(obj, (dict, list)):
            return obj, _json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass
    return None, s[:200]

def _safe_float(x):
    try:
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            return float(x.strip())
    except Exception:
        return None
    return None

def _extract_usage_from_resp(resp):
    usage = {}
    if isinstance(resp, dict):
        raw_usage = resp.get("usage")
        try:
            if raw_usage:
                getter = (lambda k: raw_usage.get(k)) if isinstance(raw_usage, dict) else (lambda k: getattr(raw_usage, k, None))
                usage["llm_prompt_tokens"] = getter("prompt_tokens") or getter("input_tokens")
                usage["llm_completion_tokens"] = getter("completion_tokens") or getter("output_tokens")
                usage["llm_total_tokens"] = getter("total_tokens")
        except Exception:
            pass
        rt = resp.get("response_time")
        rt_f = _safe_float(rt)
        if rt_f is not None:
            usage["gpt_reported_sec"] = rt_f
    return usage

# ---------- 모델 라우팅 (CAP/JOI) ----------
def resolve_generator(model_selector: str):
    """
    model_selector: 'joi' | 'cap' | 기타(None/공백) -> config.DEFAULT_MODEL_SELECTOR 사용
    return: (generate_func, model_name_str, resolved_selector)
    """
    sel = (model_selector or "").strip().lower()
    if sel not in config.MODEL_SELECT:
        sel = config.DEFAULT_MODEL_SELECTOR

    spec = config.MODEL_SELECT[sel]
    module = importlib.import_module(spec["module"])
    func = getattr(module, spec["function"])
    return func, spec["model_name"], sel

# ---------- 결정론적 평가 ----------
def run_deterministic_evaluation(candidate_json: dict, gt_json_list: List[dict], policy_hints: dict) -> dict:
    try:
        from eval_tools import syntax_checker, policy_checker, similarity_checker
    except Exception as e:
        print(f"❌ DET Error: eval_tools init failed ({e}).")
        return {"scores": {}, "evidence": {"error": f"Init Error: {e}"}}

    scores = {}
    evidence = {}
    candidate_code = candidate_json.get("code", "")

    # 1) Syntax & Logic
    try:
        pv_result = syntax_checker.parse_validate(candidate_code)
        pv_errors = pv_result.get("errors", []) if isinstance(pv_result.get("errors"), list) else []
        evidence["syntax_errors"] = str(pv_errors) if pv_errors else "[]"
    except Exception as e:
        pv_result = {"ok": False, "errors": [f"PV_ERR:{e}"], "ast": None}
        evidence["syntax_errors"] = str(pv_result["errors"])

    if not pv_result.get("ok"):
        scores["syntax_schema"] = 0.0
        scores["logic_rules"] = 0.0
        ast_node = None
    else:
        scores["syntax_schema"] = 1.0
        ast_node = pv_result.get("ast")
        try:
            sr_result = syntax_checker.check_static_rules(candidate_json)
            sr_violations = sr_result.get("violations", []) if isinstance(sr_result.get("violations"), list) else []
            evidence["rule_violations"] = str(sr_violations) if sr_violations else "[]"
            score = 1.0
            if any("spinning_misuse" in v for v in sr_violations):
                score -= 0.2
            if any("potential_init_misuse" in v for v in sr_violations):
                score -= 0.1
            if ("for " in candidate_code or "while " in candidate_code) or any("forbidden_loop" in e for e in pv_errors):
                score -= 0.4
                try:
                    current_violations = ast.literal_eval(evidence.get("rule_violations", "[]"))
                except Exception:
                    current_violations = []
                if not any("forbidden_loop" in v for v in current_violations):
                    evidence["rule_violations"] = str(current_violations + ["forbidden_loop_keyword_detected"])
            scores["logic_rules"] = max(0.0, score)
        except Exception as e:
            scores["logic_rules"] = 0.0
            evidence["rule_violations"] = f"Error: {e}"

    # 2) Function Calls
    if ast_node is not None:
        try:
            pc_result = policy_checker.check_function_calls(ast_node, policy_hints)
            pc_issues = pc_result.get("issues", []) if isinstance(pc_result.get("issues"), list) else []
            evidence["function_call_issues"] = str(pc_issues) if pc_issues else "[]"
            score = 1.0
            num_issues = len(pc_issues)
            num_hallucinated = sum(1 for i in pc_issues if "hallucinated" in i)
            score -= 0.25 * (num_issues - num_hallucinated)
            score -= 0.6 * num_hallucinated
            scores["function_calls"] = max(0.0, score)
        except Exception as e:
            scores["function_calls"] = 0.0
            evidence["function_call_issues"] = f"Error: {e}"
    else:
        scores["function_calls"] = 0.0
        evidence["function_call_issues"] = "Parse failed"

    # 3) Semantic(Z3)
    best_semantic_score = 0.0
    best_sim_details = {}
    equivalent_overall: Union[bool, str] = True
    if not gt_json_list:
        scores["semantic_intent_z3"] = 0.0
        evidence["similarity_diff"] = "No GTs provided"
        equivalent_overall = False
    else:
        for gt_json in gt_json_list:
            try:
                sim_result = similarity_checker.calculate_similarity(candidate_json, gt_json)
                current_score = sim_result.get("similarity", {}).get("code", 0.0)
                if current_score >= best_semantic_score:
                    best_semantic_score = current_score
                    best_sim_details = sim_result
                current_equiv = sim_result.get("equivalent")
                if current_equiv is False and equivalent_overall is True:
                    equivalent_overall = False
                elif isinstance(current_equiv, str):
                    equivalent_overall = current_equiv
            except ImportError:
                best_semantic_score = 0.0
                equivalent_overall = "skipped (z3-solver not installed)"
                break
            except Exception as e:
                best_semantic_score = 0.0
                equivalent_overall = f"SIM_ERR ({e})"
                break
        scores["semantic_intent_z3"] = best_semantic_score
        evidence["similarity_diff"] = best_sim_details.get("diff", "")
        evidence["equivalent_z3"] = best_sim_details.get("equivalent", equivalent_overall) if best_sim_details else equivalent_overall

    # 4) DET 종합
    overall_det_score = 0.0
    for k in config.WEIGHTS:
        score_key = "semantic_intent_z3" if k == "semantic_intent" else k
        overall_det_score += scores.get(score_key, 0.0) * config.WEIGHTS[k]
    scores["overall_deterministic"] = max(0.0, min(1.0, overall_det_score))
    return {"scores": scores, "evidence": evidence}

# ---------- LangSmith Judges ----------
def build_llm_semantic_judge(criteria_prompt):
    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:
        print(f"⚠️ LLM Judge 초기화 실패: {e}")
        return None
    if isinstance(criteria_prompt, dict):
        crit_text = "\n".join([f"- {k}: {v}" for k, v in criteria_prompt.items()])
    elif isinstance(criteria_prompt, str) and criteria_prompt.strip():
        crit_text = criteria_prompt.strip()
    else:
        crit_text = "Judge whether the PREDICTION's code fulfills the INPUT instruction."

    llm = ChatOpenAI(model=config.LS_JUDGE_MODEL, temperature=0)

    class _Judge:
        def __init__(self, llm, crit_text):
            self.llm = llm
            self.crit_text = crit_text

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json
            sys_prompt = "You are a strict evaluator for a DSL (JoI-Lang). Return pure JSON."
            user_prompt = f"""
## CRITERIA
{self.crit_text}

## INPUT
{input}

## REFERENCE
{reference}

## PREDICTION
{prediction}

Respond ONLY with JSON:
{{"score": 0.0, "reasoning": "..."}}"""
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res))
            except Exception as e:
                return {"score": 0.0, "reasoning": f"invoke_error: {e}", "raw": ""}

            try:
                start = text.find("{"); end = text.rfind("}")
                js = text[start:end+1] if start != -1 and end != -1 else "{}"
                obj = _json.loads(js)
            except Exception:
                obj = {}
            score = obj.get("score", 0.0)
            try: score = float(score)
            except: score = 0.0
            score = max(0.0, min(1.0, score))
            return {"score": score, "reasoning": obj.get("reasoning", ""), "raw": text}

    return _Judge(llm, crit_text)

def build_llm_multi_criteria_judge(criteria: Dict[str, str]):
    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:
        print(f"⚠️ LLM Multi Judge 초기화 실패: {e}")
        return None
    if not isinstance(criteria, dict) or not criteria:
        return None
    llm = ChatOpenAI(model=config.LS_JUDGE_MODEL, temperature=0)

    class _MultiJudge:
        def __init__(self, llm, criteria):
            self.llm = llm
            self.criteria = criteria

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json
            crit_text = "\n".join([f"- {k}: {v}" for k, v in self.criteria.items()])
            sys_prompt = "You are a strict evaluator for a DSL (JoI-Lang). Return pure JSON with per-criterion scores."
            user_prompt = f"""
## CRITERIA
{crit_text}

## INPUT
{input}

## REFERENCE
{reference}

## PREDICTION
{prediction}

Respond ONLY with JSON:
{{"scores": {{}}, "rationales": {{}}}}"""
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res)).strip()
            except Exception as e:
                return {"scores": {}, "rationales": {"_error": f"invoke_error: {e}"}}

            try:
                start = text.find("{"); end = text.rfind("}")
                js = text[start:end+1] if start != -1 and end != -1 else "{}"
                obj = _json.loads(js)
            except Exception:
                obj = {}
            scores = obj.get("scores", {})
            rats = obj.get("rationales", {})
            clean_scores = {}
            for k in self.criteria.keys():
                v = scores.get(k, 0.0)
                try: v = float(v)
                except: v = 0.0
                clean_scores[k] = max(0.0, min(1.0, v))
            return {"scores": clean_scores, "rationales": rats}

    return _MultiJudge(llm, criteria)

# ---------- 로컬 테스트 (모드+모델 선택) ----------
def run_local_test(modes: List[str], row_index: int, model_version_path: str, model_selector: str):
    valid_modes = {"det", "lang", "gpt", "hybrid"}
    requested_modes = [m for m in modes if m in valid_modes]
    if not requested_modes:
        print("Error: No valid mode specified.")
        return
    if any(m == "hybrid" for m in requested_modes):
        requested_modes = ["det", "lang", "gpt"]
    requested_modes = sorted(set(requested_modes), key=lambda x: ["det","lang","gpt"].index(x))

    run_det = "det" in requested_modes
    run_lang = "lang" in requested_modes
    run_gpt_j = "gpt" in requested_modes
    mode_str = "+".join(m.upper() for m in requested_modes)

    # 모델 생성기/모델명 결정 (핵심 변경점)
    generate_func, model_name, resolved_selector = resolve_generator(model_selector)

    # 표시용 모델명 (JOI는 버전 문자열 그대로, CAP은 gpt4.1-mini)
    full_model_name = model_name
    print(f"--- 🚀 Running {mode_str} Local Test for Row Index: {row_index} using Model[{resolved_selector}]: {full_model_name} ---")
    safe_model_path_name_for_file = re.sub(r"[^\w\-]+", "_", f"{resolved_selector}:{full_model_name}")
    output_filename = f"result_{safe_model_path_name_for_file}.csv"
    print(f"   (Results will be appended/updated in: {output_filename})")

    # 데이터 로드
    try:
        df = pd.read_csv(config.DATA_FILE_PATH, encoding="utf-8-sig")
        if not (0 <= row_index < len(df)):
            print(f"Error: Row index {row_index} out of bounds.")
            return
        row = df.iloc[row_index]
    except Exception as e:
        print(f"데이터 파일 로드 실패: {e}")
        return

    original_index = row.get("index", row_index)
    command = row.get(config.COMMAND_COLUMN, "Command not found")
    print(f"[1/N] 명령어 로드 (Original Index: {original_index}): {command}")

    # GPT 생성 호출
    connected_devices_str = row.get("connected_devices")
    other_params_str = row.get("options")
    try:
        connected_devices = ast.literal_eval(connected_devices_str) if pd.notna(connected_devices_str) and isinstance(connected_devices_str, str) and connected_devices_str.strip() else []
    except Exception:
        connected_devices = []
    try:
        other_params = ast.literal_eval(other_params_str) if pd.notna(other_params_str) and isinstance(other_params_str, str) and other_params_str.strip() else []
    except Exception:
        other_params = []

    print(f"   Calling {resolved_selector}.generate_joi_code(model='{full_model_name}')")
    t0_gen = time.perf_counter()
    gen_started_at_iso = datetime.now().isoformat(timespec="seconds")

    try:
        resp = generate_func(
            sentence=command,
            model=full_model_name,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            connected_devices=connected_devices,
            other_params=other_params,
        )
        if not isinstance(resp, dict):
            print(f"❌ GPT 모델 함수 반환 타입 오류: {type(resp)}")
            return
    except Exception as e:
        print(f"❌ GPT 모델 호출 오류: {e}")
        return

    t1_gen = time.perf_counter()
    gpt_elapsed_sec = round(t1_gen - t0_gen, 6)

    usage_info = _extract_usage_from_resp(resp)
    gpt_reported_sec = usage_info.get("gpt_reported_sec", None)
    llm_prompt_tokens = usage_info.get("llm_prompt_tokens", None)
    llm_completion_tokens = usage_info.get("llm_completion_tokens", None)
    llm_total_tokens = usage_info.get("llm_total_tokens", None)
    response_time = usage_info.get("gpt_reported_sec", gpt_elapsed_sec)

    generated_code_output = resp.get("code") if isinstance(resp, dict) else None
    if isinstance(generated_code_output, list):
        generated_code_json_str = generated_code_output[0] if generated_code_output and isinstance(generated_code_output[0], str) else "{}"
    elif isinstance(generated_code_output, str):
        generated_code_json_str = generated_code_output
    else:
        generated_code_json_str = "{}"
    generated_code_json_str = _extract_json_from_text(generated_code_json_str)

    print(f"[2/N] 후보 JSON 생성 ({response_time:.3f}s):\n{generated_code_json_str}")
    try:
        candidate_json = json.loads(generated_code_json_str) if generated_code_json_str and generated_code_json_str.strip() else {"code": ""}
    except json.JSONDecodeError as e:
        print(f"Error: GPT 반환 JSON 파싱 실패: {e}")
        candidate_json = {"code": f"INVALID JSON: {generated_code_json_str}"}

    # GT 로드
    gt_columns = [c for c in df.columns if c.startswith("gt")]
    gt_json_list, gt_str_list = [], []
    for gt_col in gt_columns:
        raw = row.get(gt_col)
        obj, norm = _safe_load_json(raw)
        if obj is None:
            continue
        gt_json_list.append(obj)
        gt_str_list.append(norm if isinstance(norm, str) and norm else json.dumps(obj, ensure_ascii=False))
    print(f"[3/N] {len(gt_json_list)}개의 유효한 Ground Truth 로드 완료.")

    # DET
    det_eval_results = {"scores": {}, "evidence": {}}
    if run_det:
        det_eval_results = run_deterministic_evaluation(candidate_json, gt_json_list, {})
        print(f"[4/N] 결정론적 평가 완료.")
    step_order = 4 if run_det else 3

    # LANG
    semantic_intent_ls = None
    ls_judge_reasoning = ""
    ls_multi_scores = {}
    if run_lang:
        step_order += 1
        print(f"[{step_order}/N] LangSmith Criteria Judge 시작...")
        crit = getattr(config, "SEMANTIC_JUDGE_CRITERIA", None) or getattr(config, "SEMANTIC_JUDGE_CRITERIA_PROMPT", "")
        reference_code = gt_json_list[0]["code"] if gt_json_list and "code" in gt_json_list[0] else ""
        try:
            if isinstance(crit, dict) and len(crit) > 1:
                evaluator = build_llm_multi_criteria_judge(crit)
                if evaluator:
                    res = evaluator.evaluate_strings(
                        prediction=candidate_json.get("code", ""),
                        input=command,
                        reference=reference_code,
                    )
                    ls_multi_scores = res.get("scores", {})
                    for k in ["semantic_intent", "intent", "overall"]:
                        if k in ls_multi_scores:
                            semantic_intent_ls = float(ls_multi_scores[k])
                            break
                    if semantic_intent_ls is None and ls_multi_scores:
                        semantic_intent_ls = float(np.mean(list(ls_multi_scores.values())))
                    ls_judge_reasoning = res.get("rationales", {})
                else:
                    ls_judge_reasoning = "skipped (libs unavailable)"
            else:
                evaluator = build_llm_semantic_judge(crit)
                if evaluator:
                    eval_result = evaluator.evaluate_strings(
                        prediction=candidate_json.get("code", ""),
                        input=command,
                        reference=reference_code,
                    )
                    semantic_intent_ls = float(eval_result.get("score", 0.0))
                    ls_judge_reasoning = eval_result.get("reasoning", "N/A")
                else:
                    ls_judge_reasoning = "skipped (libs unavailable)"
        except Exception as e:
            ls_judge_reasoning = f"error ({e})"

    # GPT Judge
    semantic_intent_gpt = None
    gpt_judge_reasoning = ""
    if run_gpt_j:
        step_order += 1
        print(f"[{step_order}/N] Custom GPT Judge 시작...")
        try:
            from cloud_judge import judge_gpt
            first_gt_code = gt_json_list[0]["code"] if gt_json_list and "code" in gt_json_list[0] else ""
            if first_gt_code:
                gpt_judge_result = judge_gpt.run_custom_gpt_judge(candidate_json.get("code", ""), first_gt_code, command)
                semantic_intent_gpt = gpt_judge_result.get("score", 0.0)
                gpt_judge_reasoning = gpt_judge_result.get("comment", "")
            else:
                gpt_judge_reasoning = "skipped (no valid GT)"
        except Exception as e:
            gpt_judge_reasoning = f"error ({e})"

    # 점수 통합
    final_scores: Dict[str, Any] = {}
    if run_det:
        final_scores.update(det_eval_results["scores"])
    if semantic_intent_ls is not None:
        final_scores["semantic_intent_ls"] = semantic_intent_ls
    if semantic_intent_gpt is not None:
        final_scores["semantic_intent_gpt"] = semantic_intent_gpt

    semantic_candidates = [
        ("semantic_intent_ls", final_scores.get("semantic_intent_ls")),
        ("semantic_intent_gpt", final_scores.get("semantic_intent_gpt")),
        ("semantic_intent_z3", final_scores.get("semantic_intent_z3")),
    ]
    final_semantic_key, final_semantic_score = None, None
    for k, v in semantic_candidates:
        if v is not None:
            try:
                final_semantic_score = float(v)
                final_semantic_key = k
                break
            except Exception:
                pass

    present_weights = {}
    if run_det:
        for k in ["syntax_schema", "logic_rules", "function_calls"]:
            if k in final_scores:
                present_weights[k] = config.WEIGHTS.get(k, 0.0)
    if final_semantic_score is not None:
        present_weights["semantic_intent"] = config.WEIGHTS.get("semantic_intent", 0.0)

    weight_sum = sum(present_weights.values())
    if weight_sum > 0:
        overall_final = 0.0
        if run_det:
            overall_final += final_scores.get("syntax_schema", 0.0) * (present_weights.get("syntax_schema", 0.0) / weight_sum)
            overall_final += final_scores.get("logic_rules", 0.0) * (present_weights.get("logic_rules", 0.0) / weight_sum)
            overall_final += final_scores.get("function_calls", 0.0) * (present_weights.get("function_calls", 0.0) / weight_sum)
        if final_semantic_score is not None:
            overall_final += final_semantic_score * (present_weights.get("semantic_intent", 0.0) / weight_sum)
        final_scores["overall_final"] = max(0.0, min(1.0, overall_final))
    else:
        final_scores["overall_final"] = ""

    # CSV 저장
    gen_finished_at_iso = datetime.now().isoformat(timespec="seconds")
    output_data = {
        "index": original_index,
        "model_name": f"{resolved_selector}:{full_model_name}",
        "command": command,
        "gen_started_at": gen_started_at_iso,
        "gen_ended_at": gen_finished_at_iso,
        "response_time": f"{response_time:.3f}",
        "gpt_elapsed_sec": gpt_elapsed_sec,
        "gpt_reported_sec": (None if gpt_reported_sec is None else gpt_reported_sec),
        "llm_prompt_tokens": (None if llm_prompt_tokens is None else llm_prompt_tokens),
        "llm_completion_tokens": (None if llm_completion_tokens is None else llm_completion_tokens),
        "llm_total_tokens": (None if llm_total_tokens is None else llm_total_tokens),
        "overall_final": final_scores.get("overall_final"),
        "overall_deterministic": final_scores.get("overall_deterministic") if run_det else "",
        "syntax_schema": final_scores.get("syntax_schema") if run_det else "",
        "logic_rules": final_scores.get("logic_rules") if run_det else "",
        "function_calls": final_scores.get("function_calls") if run_det else "",
        "semantic_intent_z3": final_scores.get("semantic_intent_z3") if run_det else "",
        "semantic_intent_ls": final_scores.get("semantic_intent_ls") if run_lang else "",
        "semantic_intent_gpt": final_scores.get("semantic_intent_gpt") if run_gpt_j else "",
        "equivalent_z3": det_eval_results["evidence"].get("equivalent_z3") if run_det else "",
        "generated_candidate_json": generated_code_json_str,
        "ground_truth_json_list": json.dumps(gt_str_list, ensure_ascii=False),
        "syntax_errors": det_eval_results["evidence"].get("syntax_errors") if run_det else "",
        "rule_violations": det_eval_results["evidence"].get("rule_violations") if run_det else "",
        "function_call_issues": det_eval_results["evidence"].get("function_call_issues") if run_det else "",
        "z3_diff": det_eval_results["evidence"].get("similarity_diff") if run_det else "",
        "ls_judge_reasoning": ls_judge_reasoning if run_lang else "",
        "gpt_judge_reasoning": gpt_judge_reasoning if run_gpt_j else "",
    }
    for k, v in (ls_multi_scores or {}).items():
        output_data[f"ls_{k}"] = v

    try:
        ordered_columns = [
            "index", "model_name", "command",
            "gen_started_at", "gen_ended_at", "response_time",
            "gpt_elapsed_sec", "gpt_reported_sec",
            "llm_prompt_tokens", "llm_completion_tokens", "llm_total_tokens",
            "overall_final", "overall_deterministic",
            "syntax_schema", "logic_rules", "function_calls",
            "semantic_intent_z3", "semantic_intent_ls", "semantic_intent_gpt",
            "equivalent_z3",
            "generated_candidate_json", "ground_truth_json_list",
            "syntax_errors", "rule_violations", "function_call_issues",
            "z3_diff", "ls_judge_reasoning", "gpt_judge_reasoning",
        ]
        numeric_cols = [
            "overall_final", "overall_deterministic",
            "syntax_schema", "logic_rules", "function_calls",
            "semantic_intent_z3", "semantic_intent_ls", "semantic_intent_gpt",
            "response_time", "gpt_elapsed_sec", "gpt_reported_sec",
            "llm_prompt_tokens", "llm_completion_tokens", "llm_total_tokens",
        ]
        for k in (ls_multi_scores or {}).keys():
            col_name = f"ls_{k}"
            if col_name not in ordered_columns:
                ordered_columns.append(col_name)
            if col_name not in numeric_cols:
                numeric_cols.append(col_name)

        if os.path.exists(output_filename):
            try:
                existing_df = pd.read_csv(output_filename, encoding="utf-8-sig", dtype={"index": str})
            except pd.errors.EmptyDataError:
                existing_df = pd.DataFrame(columns=ordered_columns)
            except Exception:
                existing_df = pd.DataFrame(columns=ordered_columns)
        else:
            existing_df = pd.DataFrame(columns=ordered_columns)

        output_data_clean = {k: ("" if (v is None or (isinstance(v, float) and pd.isna(v))) else v) for k, v in output_data.items()}

        if "index" not in existing_df.columns:
            existing_df["index"] = ""
        try:
            existing_df["index"] = existing_df["index"].astype(str)
        except Exception:
            pass

        index_str = str(original_index)
        match_indices = existing_df.index[existing_df["index"] == index_str].tolist()

        if match_indices:
            existing_row_idx = match_indices[0]
            for col, value in output_data_clean.items():
                if col not in existing_df.columns:
                    existing_df[col] = np.nan if col in numeric_cols else ""
                if col in numeric_cols:
                    if value == "":
                        existing_df.loc[existing_row_idx, col] = np.nan
                    else:
                        try:
                            existing_df.loc[existing_row_idx, col] = float(value)
                        except Exception:
                            existing_df.loc[existing_row_idx, col] = pd.to_numeric(value, errors="coerce")
                else:
                    if existing_df[col].dtype != "object":
                        try:
                            existing_df[col] = existing_df[col].astype("object")
                        except Exception:
                            pass
                    existing_df.loc[existing_row_idx, col] = "" if value is None else str(value)
            final_df = existing_df
            print(f"\n--- Index {original_index} 결과 업데이트: {output_filename} ---")
        else:
            new_row_df = pd.DataFrame([output_data_clean])
            for col in ordered_columns:
                if col not in new_row_df.columns:
                    new_row_df[col] = np.nan if col in numeric_cols else pd.Series("", index=new_row_df.index, dtype="object")
            for c in numeric_cols:
                if c in new_row_df.columns:
                    new_row_df[c] = pd.to_numeric(new_row_df[c], errors="coerce")
            new_row_df = new_row_df[ordered_columns]
            final_df = pd.concat([existing_df, new_row_df], ignore_index=True)
            print(f"\n--- Index {original_index} 결과 추가: {output_filename} ---")

        for col in ordered_columns:
            if col not in final_df.columns:
                final_df[col] = np.nan if col in numeric_cols else ""
        final_df = final_df.reindex(columns=ordered_columns)
        obj_cols = [c for c in final_df.columns if c not in numeric_cols]
        if obj_cols:
            final_df[obj_cols] = final_df[obj_cols].fillna("")
        final_df.to_csv(output_filename, mode="w", header=True, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(f"CSV 저장/업데이트 오류: {e}")
        traceback.print_exc()

    # 콘솔 요약
    print(f"\n--- 📊 최종 {mode_str.upper()} 점수 ---")
    if run_det:
        print("\n[DET]")
        det_keys = ["overall_deterministic", "syntax_schema", "logic_rules", "function_calls", "semantic_intent_z3"]
        det_scores = {k: final_scores.get(k) for k in det_keys}
        print(json.dumps({k: (f"{v:.4f}" if isinstance(v, float) else str(v))
                          for k, v in det_scores.items() if v not in (None, "")}, indent=2, ensure_ascii=False))
        print("  - Z3 동등성:", det_eval_results["evidence"].get("equivalent_z3"))

    if run_lang:
        print("\n[LANG]")
        print(json.dumps({"semantic_intent_ls": final_scores.get("semantic_intent_ls")}, indent=2, ensure_ascii=False))
        if ls_multi_scores:
            print("  - Per-criterion:", json.dumps({f"ls_{k}": float(v) for k, v in ls_multi_scores.items()}, indent=2, ensure_ascii=False))
        print("  - Reasoning:", ls_judge_reasoning if ls_judge_reasoning else "N/A")

    if run_gpt_j:
        print("\n[GPT]")
        print(json.dumps({"semantic_intent_gpt": final_scores.get("semantic_intent_gpt")}, indent=2, ensure_ascii=False))
        print("  - Explanation:", gpt_judge_reasoning if gpt_judge_reasoning else "N/A")

    print("\n[⏱️ 생성 타이밍/사용량]")
    print(json.dumps({
        "gpt_elapsed_sec": gpt_elapsed_sec,
        "gpt_reported_sec": gpt_reported_sec or "",
        "llm_prompt_tokens": llm_prompt_tokens or "",
        "llm_completion_tokens": llm_completion_tokens or "",
        "llm_total_tokens": llm_total_tokens or "",
    }, indent=2, ensure_ascii=False))

    print("\n[최종 통합 점수]")
    overall_final_val = final_scores.get("overall_final")
    overall_final_str = f"{overall_final_val:.4f}" if isinstance(overall_final_val, float) else str(overall_final_val)
    used_semantic = "N/A" if final_semantic_key is None else final_semantic_key
    print(f"  - overall_final: {overall_final_str} (Semantic used: {used_semantic})")

# ---------- 배치 실행 ----------
def main_langsmith():
    print("--- ☁️ Batch Hybrid Evaluation (DET+LANG+GPT) over dataset ---")
    try:
        df = pd.read_csv(config.DATA_FILE_PATH, encoding="utf-8-sig")
    except Exception as e:
        print(f"데이터 파일 로드 실패: {e}")
        return
    limit = os.getenv("EVAL_LIMIT")
    if limit and str(limit).isdigit():
        df = df.head(int(limit))
        print(f"  ▶ EVAL_LIMIT={limit} 적용")

    for i in tqdm(range(len(df)), desc="Batch Hybrid"):
        try:
            # 배치에선 기본 joi 사용 (원하면 여기도 selector 인자 추가 가능)
            run_local_test(["hybrid"], i, config.DEFAULT_MODEL_VERSION_PATH, config.DEFAULT_MODEL_SELECTOR)
        except Exception as e:
            print(f"[row {i}] 오류: {e}")

# ---------- CLI 파서 ----------
if __name__ == "__main__":
    args = sys.argv[1:]
    valid_modes = {"det", "lang", "gpt", "hybrid"}

    modes: List[str] = []
    selector: Optional[str] = None  # 'joi' | 'cap'
    row_idx: Optional[int] = None
    model_ver = config.DEFAULT_MODEL_VERSION_PATH  # 유지 (표시/호환용)

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in valid_modes:
            modes.append(arg)
        elif arg.lower() in ("joi", "cap"):
            selector = arg.lower()
        elif arg.isdigit():
            # 첫 숫자는 row index로 해석
            if row_idx is None:
                row_idx = int(arg)
            else:
                # 이미 row index가 있고 추가 토큰이면 model_ver로 둠
                model_ver = arg
        else:
            # 마지막 토큰을 model_ver로 사용할 수 있게 허용
            model_ver = arg
        i += 1

    if not modes and row_idx is None and selector is None and len(args) == 0:
        # 전체 배치 (기본: hybrid + joi)
        main_langsmith()
        sys.exit(0)

    if not modes:
        print("오류: 실행 모드가 필요합니다. (det | lang | gpt | hybrid)")
        sys.exit(1)

    if row_idx is None:
        print("오류: row_index가 필요합니다. 예) python main_evaluator.py hybrid cap 20")
        sys.exit(1)

    # selector 미지정 시 joi 기본
    if not selector:
        selector = config.DEFAULT_MODEL_SELECTOR

    # 실행
    run_local_test(modes, row_idx, model_ver, selector)
