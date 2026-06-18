from dotenv import load_dotenv
from openai import OpenAI
import os
import sys
import time
import importlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

load_dotenv()

api_key = (
    os.getenv("OPENAI_API_KEY_PROJ_BENCH")
    or os.getenv("JOI_EVAL_OPENAI_API_KEY")
    or os.getenv("JOI_V15_OPENAI_API_KEY")
    or os.getenv("OPENAI_API_KEY")
)

if not api_key:
    raise RuntimeError("OpenAI API key is not configured")

os.environ["OPENAI_API_KEY"] = api_key
client = OpenAI(api_key=api_key)

import pandas as pd
import json, ast, requests
from datetime import datetime
from tqdm import tqdm
import csv
import re


model_default = 'version0_6'
feedback=0
all_items = []
choice_no = 0
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#from Evaluation.compare_soplang_ir import compare_codes
def _normalize_version014_generated_code(model: str, generated_code):
    if "version0_14" not in str(model):
        return generated_code
    try:
        from gpt_mg.version0_14.utils.pipeline_common import normalize_candidate_json_text
    except Exception:
        try:
            from version0_14.utils.pipeline_common import normalize_candidate_json_text
        except Exception:
            return generated_code

    if generated_code in ("", None):
        return generated_code

    try:
        if isinstance(generated_code, list):
            if not generated_code:
                return generated_code
            payload_text = json.dumps(generated_code[0], ensure_ascii=False)
            normalized_text = normalize_candidate_json_text(payload_text, default_cron="", default_period=0)
            parsed = json.loads(normalized_text)
            return [parsed] if isinstance(parsed, dict) else generated_code
        if isinstance(generated_code, dict):
            payload_text = json.dumps(generated_code, ensure_ascii=False)
            normalized_text = normalize_candidate_json_text(payload_text, default_cron="", default_period=0)
            parsed = json.loads(normalized_text)
            return parsed if isinstance(parsed, dict) else generated_code
        if isinstance(generated_code, str):
            normalized_text = normalize_candidate_json_text(generated_code, default_cron="", default_period=0)
            try:
                parsed = json.loads(normalized_text)
                if isinstance(parsed, dict):
                    return [parsed]
            except Exception:
                return generated_code
    except Exception:
        return generated_code

    return generated_code


def save_sentence_and_code(sentence, best_code, filename="sentence_best_code_log.csv"):
    """
    입력 sentence와 best_code를 한 파일에 누적으로 저장 (중복 허용)
    """
    filename = os.path.join(os.path.dirname(__file__), filename)
    file_exists = os.path.isfile(filename)
    #print(filename)
    with open(filename, "a", newline='', encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["sentence", "best_code"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({"sentence": sentence, "best_code": best_code})

def move_global_assignments(response_text):
    # 코드블럭만 추출
    code_block = re.search(r"```(.*?)```", response_text, re.DOTALL)
    if not code_block:
        return response_text  # 코드블럭 없으면 그대로 반환

    code_content = code_block.group(1).strip()
    lines = code_content.split('\n')

    # code=의 위치 찾기
    code_eq_idx = None
    # := 패턴을 찾고, 해당 줄의 인덱스와 내용 저장
    assignment_lines = []
    assignment_idxs = []

    for i, line in enumerate(lines):
#        print(f"Checking line {i}: {line}")
        if re.match(r'^\s*code\s*=', line):
            code_eq_idx = i
            print("Code= found at line:", i)
            break
        if re.match(r'^\s*\w+\s*:=\s*.+$', line):
            assignment_lines.append(line)
            assignment_idxs.append(i)
    if code_eq_idx is None:
        return response_text  # code= 없으면 그대로 반환

    # 해당 줄 제거
    for idx in reversed(assignment_idxs):
        del lines[idx]
    print('All lines after deletion:\n')
    for idx, line in enumerate(lines):
        print(f'line[{idx}]: {line}')
    # code= 바로 뒤에 삽입
    insert_idx = code_eq_idx - 1
    print("insert_idx: ", insert_idx)
    print("assignment lines : ", assignment_lines)
    lines[insert_idx:insert_idx] = assignment_lines

    # 최종 문자열 복원
    new_code = '\n'.join(lines)
    # 원본의 ```~``` 포맷에 맞게 반환
    return f"```\n{new_code}\n```"

def generate_joi_code(sentence: str, model: str, connected_devices: dict, current_time: str, other_params: dict = None) -> dict:
    # 1. 메시지 구성
    start = time.perf_counter()
    #from version0_1.config_loader import load_version_config
    #model_path = f"gpt_mg.{model}.config_loader"
    model_path = f"{model}.config_loader"
    print("Model Path :: ", model_path)
    config_loader_module = importlib.import_module(model_path)
    load_version_config = getattr(config_loader_module, 'load_version_config')
    path_tmp = '.'#os.path.join("gpt_mg",version_path,"config_loader")
    choice_responses = []
    start_infer = time.perf_counter()
    #feedback = 1
    if feedback == 1:
        fd_prompt = """\n\n ---\n Generate JOI Lang code for the following natural language instruction.  
Provide three of the most likely or appropriate code translations, depending on confidence.  
Output the results as a list under a "choices" key, where each item contains only the JOI Lang code snippet."""
        config, model_input = load_version_config(f"Current Time: {current_time}\n\nGenerate JOI Lang code for Natural Language: {sentence}. {fd_prompt}", \
                                        connected_devices, other_params, path_tmp)
    else:
        config, model_input = load_version_config(f"Current Time: {current_time}\n\nGenerate JOI Lang code for Natural Language: {sentence}", \
                                                connected_devices, other_params, path_tmp)
    logs={}
    end_infer = time.perf_counter()
    logs["inference_time"] = f"{end_infer - start_infer:.4f} seconds"

    # 2. 모델 호출
    response = {}
    global all_items  # 전체 item을 누적할 리스트
    global choice_no
    all_items = []
    choice_no = 0
    try:
        response = client.chat.completions.create(**model_input)
        print("Response:: ", response)

        #print("Output:: >> ", response)
        if (feedback == 1) and not (choice_no):
            # 저장 폴더 경로 (필요시 변경)
            for ch_idx in range(len(response.choices)):
                #response.choices[ch_idx].message.content = move_global_assignments(response.choices[ch_idx].message.content)
                #cleaned = re.sub(r"json|", "", response.choices[ch_idx].message.content).replace("```", "").strip()

                raw_content = response.choices[ch_idx].message.content

                # ✅ Case 1: Triple backtick with json block
                if raw_content.strip().startswith("```json"):
                    # Remove ```json and final ```
                    cleaned = re.sub(r"^```json", "", raw_content.strip())
                    cleaned = re.sub(r"```$", "", cleaned).strip()

                # ✅ Case 2: Pipe-prefixed format (e.g., "json|{ ... }")
                elif raw_content.strip().startswith("json|"):
                    # Remove only the "json|" part
                    cleaned = raw_content.strip()[len("json|"):].strip()

                # ✅ Case 3: Already-clean content
                else:
                    cleaned = raw_content.strip()

                # ✅ Optional: Handle custom JOI pre-processing if needed
                cleaned = move_global_assignments(cleaned)

                data = json.loads(cleaned)
                choice_responses = data["choices"]
                #print(f"ch_idx-{ch_idx}-{len(choice_responses)},  ::\n  {choice_responses}")
                if len(choice_responses):
                    all_items.extend(choice_responses)
                else:
                    break
            print("Response JSON :: ", data)
    
            output_path = "./joi_outputs/choices_result.joi"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            # code 별도 텍스트 파일에 실제 줄바꿈 살려 저장
            #print("저장 경로:", output_path)
            try:
                with open(output_path, "a", encoding="utf-8") as f_code:
                    #print("# of all_items :: ", len(all_items), flush=True)
                    f_code.write(f"{{command : {sentence}}}\n")
                    for item in all_items:
                        try:
                            #print(item)
                            f_code.write(f", {{\nname : {item['name']}\n")
                            if item['cron']:
                                f_code.write(f"cron : {item['cron']}\n")
                            else:
                                f_code.write(f"cron : ""\n")
                            f_code.write(f"period : {item['period']}\n")
                            f_code.write(f"code : \n")
                            code_text = item['code']
                            # 백슬래시 두 개 + n 으로 되어 있으면 실제 줄바꿈으로 변환sor
                            if "\\n" in code_text:
                                code_text = code_text.replace("\\n", "\n")
                            # 혹시 \r\n 같은 윈도우 개행도 정리 (선택사항)
                            code_text = code_text.replace("\r\n", "\n")
                            indented_code = '\n'.join('    ' + line for line in code_text.split('\n'))
                            f_code.write(indented_code + "\n}\n\n")
                        except Exception as e:
                            print(f"Error writing item {item.get('name', '')}: {e}")
            except Exception as e:
                print("파일 열기 또는 쓰기 실패:", e)
        else:
            #generated_code = response.get("code", "")
    #except Exception as e:
            try:
                #print("exception in response:", e)
                
                generated_code = response.choices[0].message.content
                print("In exception, Response Content :: ", generated_code)
                #generated_code = move_global_assignments(generated_code)
                if isinstance(generated_code, dict):
                    generated_code = generated_code.get("choices", "")
                #generated_code = to_json_style_string(generated_code)
                if generated_code.strip().startswith("```json"):
                    # Remove ```json and final ```
                    cleaned = re.sub(r"^```json", "", generated_code)
                    cleaned = re.sub(r"```$", "", cleaned)

                # ✅ Case 2: Pipe-prefixed format (e.g., "json|{ ... }")
                elif generated_code.strip().startswith("json|"):
                    # Remove only the "json|" part
                    cleaned = generated_code.strip()[len("json|"):].strip()

                # ✅ Case 3: Already-clean content
                else:
                    cleaned = generated_code.strip()
                
                # ✅ 문자열 → dict로 파싱
                                                

                def fix_multiline_code_json(json_str):
                    # "code": "..." 안의 멀티라인 실제 줄바꿈을 \n 으로 치환
                    
                    # 정규식으로 "code": "..." 구간 찾기 (멀티라인 포함)
                    pattern = r'("code"\s*:\s*")([\s\S]*?)(")'

                    def replacer(match):
                        prefix = match.group(1)
                        content = match.group(2)
                        suffix = match.group(3)

                        # 실제 줄바꿈을 \n 으로 변환
                        content_fixed = content.replace('\n', '\\n').replace('\r', '\\r').replace('"', '\\"')
                        return f'{prefix}{content_fixed}{suffix}'

                    fixed_json = re.sub(pattern, replacer, json_str)
                    return fixed_json

                # 사용 예시
                cleaned_fixed = fix_multiline_code_json(cleaned)

                    
                parsed = json.loads(cleaned_fixed)
                all_items.append(parsed)
                '''
                choice_responses = parsed.get("choices", [])
                if isinstance(choice_responses, list):
                    all_items.extend(choice_responses)
                else:
                    print("Warning: 'choices' is not a list.")
                '''
                choice_no=0
            except Exception as e:
                #print(generated_code)
                #print('----')
                #print(all_items)
                print("## <<2. generate_joi_code>> \n Error in generate_joi_code:", e)
                logs["error"] = f"response_parse_failed: {e}"
                generated_code = {}
    except Exception as e:
        print("exception in response:", e)
        logs["error"] = f"model_call_failed: {e}"
    #print("Length of Created Code :: ", len(all_items))
    #if feedback == 1:
    #    for idx, generated_code in enumerate(choice_responses):
    #        print(f"Each Code {idx}:: {generated_code}")
    # ✅ Case Next: 선택된 결과가 있을 경우, choice_responses에서 첫 번째로 직접 설정
    if len(choice_responses) >= 1:
        generated_code = choice_responses#[choice_no]
    elif len(all_items) >= 1:
        generated_code = all_items#[choice_no]
    else:
        generated_code = ""

    generated_code = _normalize_version014_generated_code(model, generated_code)

    end = time.perf_counter()
    logs["response_time"] = f"{end - start:.4f} seconds"
    print("Response Time: ", logs["response_time"])
    
    best_code = generated_code
    logs["translated_sentence"] = ""
    logs["mapped_devices"] = ""
    logs["best_code"] = best_code
    save_sentence_and_code(sentence, best_code)
    try:
        # dict 형태일 경우
        if isinstance(response, dict):
            usage = response.get("usage", {})
            logs["prompt_tokens"] = usage.get("prompt_tokens", "")
            logs["completion_tokens"] = usage.get("completion_tokens", "")
            logs["total_tokens"] = usage.get("total_tokens", "")
        else:
            # 객체일 경우 (예: OpenAI 응답 객체)
            usage = getattr(response, "usage", None)
            logs["prompt_tokens"] = getattr(usage, "prompt_tokens", "") if usage else ""
            logs["completion_tokens"] = getattr(usage, "completion_tokens", "") if usage else ""
            logs["total_tokens"] = getattr(usage, "total_tokens", "") if usage else ""
    except Exception as e:
        # 어떤 예외가 발생해도 빈값으로
        logs["prompt_tokens"] = ""
        logs["completion_tokens"] = ""
        logs["total_tokens"] = ""
    return {
        "code": 
            best_code
        ,
        "log": logs
    }

def get_script_gpt(sentence, version_path=model_default): #[TODO] 경로 입력받도록 수정
    # 1. 메시지 구성
    start = time.perf_counter()
    #from version0_1.config_loader import load_version_config
    config_loader_module = importlib.import_module(f"gpt_mg.{version_path}.config_loader")
    load_version_config = getattr(config_loader_module, 'load_version_config')
    path_tmp = '.'#os.path.join("gpt_mg",version_path,"config_loader")
    config, model_input = load_version_config(sentence, path_tmp)
    logs={}

    # 2. 모델 호출
    response = client.chat.completions.create(**model_input)

    # 3. 서버 전송을 위한 매핑
    logs["device_name"] = config["device_name"]
    best_code = response.choices[0].message.content.strip() #content
    logs["translated_sentence"] = ""
    logs["mapped_devices"] = ""
    logs["best_code"] = best_code
    
    end = time.perf_counter()
    logs["response_time"] = f"{end - start:.4f} seconds"
    logs["prompt_tokens"] = response.usage.prompt_tokens
    logs["completion_tokens"] = getattr(response.usage, "completion_tokens", "")
    logs["total_tokens"] = response.usage.total_tokens

    print("Prompt tokens:", logs["prompt_tokens"])
#    print(f"Completion tokens: {logs["completion_tokens"]}")
    print("Total tokens:", logs["total_tokens"])

    return logs

def concat_list_to_string(lst):
    # 각 인덱스에 맞게 prefix 붙이기
    result = []
    for i, item in enumerate(dataset):
        result.append(f"command{i+1}: {item}")

    # ,로 구분하고 [ ]로 감싸기
    final_string =[ " + ", ".join(result) + " ]
def concat_df_to_string(df):
    result = []
    for i, row in enumerate(df.iterrows()):
        idx, data = row
        item = data['command']
        prefix = f"command{i+1}:" if i % 2 == 0 else f"command{i+1};"
        result.append(f"{prefix} {item}")

    final_string = "Please convert each of the following command statements into JoILang code, and return them as a list one JoILang script per command. " \
        + "[" + ", ".join(result) + "]"

def check_service_consistency(service_list, basepath='../datasets/'):
    """
    service_list: 코드에서 추출한 서비스 이름(str) 리스트
    basepath: 서비스 json 파일이 있는 경로
    """
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    function_path = os.path.join(BASE_DIR, basepath, 'service_list_ver1.5.4_function.json')
    value_path = os.path.join(BASE_DIR, basepath, 'service_list_ver1.5.4_value.json')
    with open(function_path, encoding='utf-8') as f:
        function_json = json.load(f)
    with open(value_path, encoding='utf-8') as f:
        value_json = json.load(f)
    # 모든 서비스 이름 set으로
    valid_services = set()
    for item in function_json:
        if "service" in item:
            valid_services.add(item["service"])
    for item in value_json:
        if "service" in item:
            valid_services.add(item["service"])
    # 검사
    for service in service_list:
        if service not in valid_services:
            return 1  # 불일치
    return 0  # 모두 일치

def extract_services_from_code(code_value):
    # (#...여러개태그...) . 서비스이름(
    # 예: (#Door #Odd).doorControl_door == "closed"
    #     (#Arm).armControl_raise()
    #     (#A #B).service_name(
    pattern = r'\((#[^)]*)\)\.([a-zA-Z0-9_]+)\s*\('
    return [m[1] for m in re.findall(pattern, code_value)]

def to_json_style_string(generated_code):
    # 리스트라면 첫 번째 요소를 꺼냄
    if isinstance(generated_code, list):
        if generated_code:
            generated_code = generated_code[0]
        else:
            generated_code = ""
    code = generated_code.strip()
    # 맨 앞/뒤에 ``` 있으면 제거
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    # 중괄호 있으면 제거
    if code.startswith("{") and code.endswith("}"):
        code = code[1:-1].strip()

    # 초기화
    fields = {"name": "", "cron": "", "period": "", "code": ""}
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # "name": ... 또는 name = ... 모두 지원
        m = re.match(r'^"?name"?\s*[:=]\s*(.*?)(,)?$', line)
        if m:
            value = m.group(1).strip().strip(',')
            value = value.strip('"')
            fields["name"] = f'"{value}"'
            i += 1
            continue
        m = re.match(r'^"?cron"?\s*[:=]\s*(.*?)(,)?$', line)
        if m:
            value = m.group(1).strip().strip(',')
            value = value.strip('"')
            fields["cron"] = f'"{value}"'
            i += 1
            continue
        m = re.match(r'^"?period"?\s*[:=]\s*(.*?)(,)?$', line)
        if m:
            value = m.group(1).strip().strip(',')
            # 숫자만 추출, 이미 따옴표 있으면 제거
            value = value.strip('"')
            fields["period"] = value
            i += 1
            continue
        # code 필드 (여러 줄)
        m = re.match(r'^"?code"?\s*[:=]\s*(.*)$', line)
        if m:
            value = m.group(1).strip().strip(',')
            code_lines = []
            if value:
                code_lines.append(value)
            i += 1
            # 다음 필드가 나오기 전까지 모두 code로
            while i < len(lines):
                next_line = lines[i].strip()
                if re.match(r'^"?name"?\s*[:=]', next_line) or \
                   re.match(r'^"?cron"?\s*[:=]', next_line) or \
                   re.match(r'^"?period"?\s*[:=]', next_line) or \
                   re.match(r'^"?code"?\s*[:=]', next_line):
                    break
                code_lines.append(next_line)
                i += 1
            code_value = "\n".join(code_lines).strip()
            code_value = code_value.strip('"')
            fields["code"] = f'"{code_value}"'
            continue
        i += 1
    service_list = extract_services_from_code(fields["code"])
    error = check_service_consistency(service_list, './version0_5')
    if not error:
        result = '{' + f'"name": {fields["name"]}, "cron": {fields["cron"]}, "period": {fields["period"]}, "code": {fields["code"]}' + '}'
    else:
        result = '{'+'}'
    return result
def clean_value(val):
    if isinstance(val, str):
        return val.strip().strip('"').strip(',')#.strip()
    return val
def merge_duplicate_blocks(generated_code):
    import re
    import json
    # 리스트라면 첫 번째 요소를 꺼냄
    if isinstance(generated_code, list):
        if generated_code:
            generated_code = generated_code[0]
        else:
            generated_code = ""

    code = generated_code#.strip()
    # 맨 앞/뒤에 ``` 있으면 제거
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    #code = code.strip()

    # 정확히 "key" 형식만 매칭하도록 수정
    name_pattern = re.compile(r'"name"\s*:\s*"([^"]*)"', re.DOTALL)
    cron_pattern = re.compile(r'"cron"\s*:\s*"([^"]*)"', re.DOTALL)
    period_pattern = re.compile(r'"period"\s*:\s*(-?\d+(?:\.\d+)?)', re.DOTALL)
    code_pattern = re.compile(r'"code"\s*:\s*"((?:\\.|[^"\\])*)"', re.DOTALL)
    

    name_fields = [m.group(1).strip().strip(',').strip() for m in name_pattern.finditer(code)]
    cron_fields = [m.group(1).strip().strip(',').strip() for m in cron_pattern.finditer(code)]
    period_fields = [m.group(1).strip().strip(',').strip() for m in period_pattern.finditer(code)]
    #code_fields = [m.group(1).strip().strip(',').strip('"') for m in code_pattern.finditer(code)]
    # code 필드 디코딩 적용 (이스케이프 문자 복원)
    code_fields = [m.group(1).encode().decode("unicode_escape") for m in code_pattern.finditer(code)]

    n_blocks = min(len(name_fields), len(cron_fields), len(period_fields), len(code_fields))
    if (n_blocks<2):
        return generated_code, 0
    
    blocks = []
    for i in range(n_blocks):
        if not (name_fields[i] and period_fields[i] and code_fields[i]):
            continue  # 값이 하나라도 없으면 건너뜀

        try:
            period_val = int(period_fields[i])
        except Exception:
            period_val = period_fields[i]
        blocks.append({
            "name": name_fields[i],
            "cron": cron_fields[i],
            "period": period_val,
            "code": code_fields[i]
        })
    # cron, period가 같으면 code를 합침
    merged = {}
    for b in blocks:
        print(f"\nBlock :: {b} \n")
        key = (b["cron"], b["period"])
        b["code"] = b["code"].replace('---', '')  # --- 구분자 제거, 이스케이프 문자 복원
        if key in merged:
            merged[key]["code"] += "\n"+ b["code"]   # --- 구분자 제거
        else:
            merged[key] = b
    merged_list = list(merged.values())
    #merged_list = [b for b in merged_list if all(str(b.get(k, "")).strip() for k in ("name", "cron", "period", "code"))]
    
    # 코드 필드 내부 \\n → \n, \\" → ", 등 이스케이프 복원 처리
    #for b in merged_list:
    #    b["code"] = b["code"].encode().decode("unicode_escape")
    if len(merged_list) == 1:
        json_result = merged_list[0]
        #json_str = json.dumps(merged_list[0], ensure_ascii=False)
    else:
        json_result = merged_list
        #json_str = json.dumps(merged_list, ensure_ascii=False)
    
    # 2. 후처리로 이스케이프 문자 제거 (\n, \", 등)
    #cleaned_str = json_str.replace('""', '"') #json_str.encode().decode("unicode_escape")
    #cleaned_str = json_str.encode().decode("unicode_escape").replace('""', '"')

    # 3. 반환
    return json_result, 1 #cleaned_str, 1

def benchmark_each_command():
    # 실행
    """
    for data in dataset:
        for model in paths:
            print("\n", model)
            get_script_gpt(data, model)
    """
    with open("../datasets/things.json", "r") as f:
        things = json.load(f)
    # print(things)

    #model = "Qwen2.5-Coder:7B"
    model = model_default
    is_english = False
    if is_english:
        english = "_english"
    else:
        english = ""

    # df = pd.read_excel("./final_output_250616.xlsx", engine='openpyxl')
    f_file_name = "../datasets/final_output_250630_test.csv"
    df = pd.read_csv(f_file_name, encoding='utf-8-sig')

    # 출력 경로 생성 및 한 줄 실시간 기록
    # 현재 시간 문자열 생성 (예: 20240625_153012)
    now_str = datetime.now().strftime("%y%m%d_%H%M%S")
    if f"joi{english}_pred_{model}" not in df.columns:
        df[f"joi_pred{english}_{model}"] = ""
        df[f"cloud_similarity{english}_{model}"] = 0.0
        df[f"script_similarity{english}_{model}"] = 0.0
        df[f"response_time{english}_{model}"] = ""
    fieldnames = list(df.columns)
    # 기존 파일명에서 확장자 분리
    base, ext = os.path.splitext(f_file_name)
    output_path = f"{base}_{now_str}{ext}"
    with open(output_path, "w", newline='', encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in tqdm(df.iterrows()):    #.head(2) #.iterrows()
            if row.get("selected") != 1:
                continue
            print(f"Processing row {i+1}/{len(df)}: {row['command']}")

            sentence = row[f"command{english}"]
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connected_devices = row["connected_devices"]
            other_params = row["options"]

            # 파싱
            if pd.isna(other_params):
                other_params = []
            else:
                try:
                    other_params = ast.literal_eval(other_params)
                except:
                    other_params = []

            if isinstance(connected_devices, str) and not pd.isna(connected_devices) and connected_devices.strip():
                try:
                    connected_devices = ast.literal_eval(connected_devices)
                except:
                    connected_devices = things
            else:
                connected_devices = things

            payload = {
                "sentence": sentence,
                "model": model,
                "connected_devices": connected_devices,
                "current_time": current_time,
                "other_params": other_params,
            }
            merged = 0
            start = time.time()
            resp = generate_joi_code(sentence=sentence,\
                                    model=model_default,\
                                    connected_devices= connected_devices,\
                                    current_time= current_time,\
                                    other_params= other_params)
            #resp = requests.post("http://localhost:8000/generate_joi_code", json=payload)
            end = time.time()
            try:
                generated_code = (resp.get("code", ""))
            except:
                generated_code = []
            #print("Output:: ", generated_code)
            if isinstance(generated_code, list):
                if (generated_code[0].count('"name"') < 2):
                    generated_code = generated_code[0]
                    merged = 0
                else:
                    generated_code, merged = merge_duplicate_blocks(generated_code)
            elif generate_joi_code is None:
                generated_code = str("{}")
            else:
                generated_code = str(generated_code)

            """
            if not merged:
                generated_code = to_json_style_string(generated_code)
            """
            resp_time = f"{end - start:.3f}"

            # gt = ast.literal_eval(row["joi_gt"])

            # eval = compare_codes(gt, generated_code)
            # total_score = eval["ast_similarity"]
            # if eval["cron_eqaul"]:
            #     total_score *= 0.5
            # if eval["period_eqaul"]:
            #     total_score *= 0.5
            
            df.at[i, f"joi_pred{english}_{model}"] = generated_code
            df.at[i, f"cloud_similarity{english}_{model}"] = 0.0
            df.at[i, f"script_similarity{english}_{model}"] = 0.0
            df.at[i, f"response_time{english}_{model}"] = float(resp_time)

            #df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print("GT :: ", df.loc[i, 'joi_gt'])
            writer.writerow(df.loc[i].to_dict())
            f.flush()  # 즉시 디스크에 기록
    print(">> ", output_path, "... saved")


def joilang_each_command(sentences, model=model_default):
    output_path = "output_each_command.csv"
    fieldnames = ["sentence", "model", "generated_code"]
    if isinstance(sentences, str):
        sentences = [sentences]
    # 파일이 있으면 append, 없으면 write
    file_exists = os.path.isfile(output_path)
    mode = "a" if file_exists else "w"
    resp = {}
    with open(output_path, mode, newline='', encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for sentence in sentences:
            try:
                print("Input Sentence:: ", sentence)
                resp = generate_joi_code(
                    sentence=sentence,
                    model=model,
                    connected_devices=None,
                    current_time=None,
                    other_params=None #'user_id': "noname"'
                )
                print("Response:: ", resp)
                generated_code = resp.get("code", "")
                print("Output:: >> ", generated_code)
            except Exception as e:
                print("## <<1. joilang_each_command>> \n Error :", e)
                generated_code = ""

            #############################              #############################
            #############################  code 후처리  #############################
            ''' # code 후처리
            # merge_duplicate_blocks 적용
            if isinstance(generated_code, list):
                if generated_code:
                    if (generated_code[0].count('"name"') < 2):
                        generated_code = generated_code[0]
                        merged = 0
                    else:
                        generated_code, merged = merge_duplicate_blocks(generated_code)
                else:
                    merged = 0
                    generated_code = ""
            else:
                if (generated_code.count('"name"') >= 2):
                    generated_code, merged = merge_duplicate_blocks(generated_code)
                    merged = 0                    
                else:
                    merged = 0            
            # to_json_style_string 적용
            print(generated_code)
            if not merged:
                generated_code = to_json_style_string(generated_code)
            #else:
            #    generated_code = generated_code.strip()
            #generated_code = json.loads(generated_code)
            '''
            #############################              #############################

            print("Output to_json_style_string:: ", generated_code)
            writer.writerow({
                "sentence": sentence,
                "model": model,
                "generated_code": generated_code
            })
            f.flush()
    return resp

if __name__ == '__main__':
    args = sys.argv[1:] #(한글 자체의 모호성에 대해서 LLM 번역 전에, 번역한 다음에 모호성을 주는 것이 맞나?)
    #dataset = ["if button 4 is swiped up, sound the alarm's siren.", '버튼4가 위로 스와이프되었으면 알람의 사이렌을 울려줘.']
    text = """블라인드가 열려 있고 조명이 꺼져 있으며 습도가 80% 이상이면 블라인드를 닫고 조명을 켜 줘. 창문이 닫혀 있고 에어컨이 꺼져 있으면 창문을 열고 에어컨을 켜 줘.
TV가 꺼져 있고 커튼이 닫혀 있으며 선풍기가 꺼져 있으면 TV를 켜고 커튼을 열어 줘. 스피커가 재생 중이고 조명이 꺼져 있으면 조명을 켜고 블라인드를 닫아 줘.
TV가 켜져 있고 스피커가 꺼져 있으며 조명이 꺼져 있으면 스피커를 켜고 조명을 켜 줘. 에어컨이 난방 모드이고 온도가 21도 이상이면 에어컨을 끄고 블라인드를 닫아 줘.
10초마다 알람과 사이렌을 껐다 켰다 반복해 줘.
매일 30초마다 선풍기를 껐다 켰다 반복해 줘.
토양 습도가 25% 이하가 되면 급수기를 켜고 이후 3초마다 상태를 확인해서 습도가 30% 이상이 될 때까지 급수기를 껐다 켰다 반복해 줘.
조명이 켜지면 블라인드를 닫고, 이후 2초마다 커튼을 열었다 닫았다 반복해 줘.
주말에는 5초마다 펌프가 꺼져 있으면 켜고, 켜져 있으면 꺼 주고, 선풍기 속도를 10으로 설정해 줘.
실시간으로 확인하여 토양 습도 센서 값이 연속으로 3회 15 이하를 기록하고 그 중 두 번째 값이 가장 낮았다면 관개 장치를 켜고 블라인드를 닫아 줘. 단, 3월은 제외하고.
매주 평일 오전 9시 창문이 닫혀 있고 이산화탄소 농도가 1000ppm 이상이며 기온이 30도 이상이면, 5초 후 창문을 열고, 팬이 꺼져 있으면 켜 줘. 그 후, 실시간으로 확인하여 1분 연속으로 미세먼지 농도가 50 이상으로 유지되면 창문을 다시 닫고, 팬도 꺼 줘. 만약 그 때 온실 내 습도가 40% 이하이면 가습기를 작동시켜 줘. 또한 마찬가지로 그 때 토양 습도가 25% 이하이고 관개 장치가 꺼져 있으면 물을 줘.
매일 밤 10시에 하단부에 있는 창문이 열려 있고 짝수 태그가 붙은 조명이 켜져 있으면 사이렌을 울려 줘. 사이렌을 울렸다면 5초 후 블라인드를 닫아 줘. 사이렌을 울렸는지 상관 없이 5초 후부터는 실시간으로 확인해서 홀수 태그가 붙은 문이 두 번 열렸다 닫히면 커튼을 닫아 줘. 커튼을 닫은 후 문이 두 번 열린 총 시간만큼 알람의 경광등을 켰다가 꺼 줘.
그룹2번이 하나라도 80을 초과하면 그룹2번은 꺼줘.
불이 30분이상 켜져있으면 알림을 울려줘.
1초마다 확인하여 관개 장치가 꺼졌다 켜진 횟수가 4번을 초과하고 펌프가 2번 이상 작동했으면 블라인드를 닫고 커튼을 내려 줘.
1초 주기로 확인해서 관개 장치가 직전에 꺼지고 이후 켜지는 횟수가 4번을 초과하고 펌프가 2번 이상 작동했으면 블라인드를 닫고 커튼을 내려 줘."""
    dataset = ['"' + line.strip() + '"' for line in text.strip().split('\n') if line.strip()]
    print('args lenght:: ', len(args))
    if len(args) == 2:
        selected_model = args[0]
        dataset = [args[1]]
        resp = joilang_each_command(dataset, selected_model)
        paths = [selected_model]

        try_no = 0
        current_sentence = dataset[0]  # 요구사항 누적용
        while True:
            if (all_items is None) or (len(all_items) == 0):
                print("No candidates generated.")
                break
            else:
                print(f"---\nCandidate #{choice_no+1}: {all_items[choice_no]}")
                ###########################
                ### re-converted sentence
                response_kor = ""
                model_path = f"version0_6_reconverted.config_loader"
                config_loader_module = importlib.import_module(model_path)
                load_version_config = getattr(config_loader_module, 'load_version_config')

                config, model_input = load_version_config(f"""넌 한글 언어학자 마스터야.
        {all_items[choice_no]}를 다시 한글 명령어로 바꿔서 아래 [ ] 를 채워줘. 단, 아래 조건들을 모두 만족하는, 한글 1~3 줄 커맨드로 구체적이고 정확하게 알아듣기 좋게 잘 변환해줘.
    all이나 any가 없는 경우 임의의 ~를 ~한다 임의의 ~가 ~를 만족하면과 같이 구체적으로 명시해줘. all/any도 마찬가지고.
    사용자 지정, 임의의 태그는 정확히 한글로 명시하는데, 특히 A, B, C와 같은 태그는 반드시 한글로 구분해줘. 예를 들어, 온실A, 온실B, 온실C와 같이.
    """) 
    #'/geners~/{url_id, setnece0} 
    #'/regenerated/{url_id, sentence0}
                response_kor = client.chat.completions.create(**model_input)
                if response_kor:
                    resp['log']['translated_sentence'] = response_kor.choices[0].message.content.strip() #content
                else:
                    print("No reconverted response, using original sentence.")
                    resp['log']['translated_sentence'] = current_sentence

                print("Reconverted Version of The Detailed Sentence: \n", resp['log']["translated_sentence"])
                ###########################
                answer = input("최종 결과에 만족하는가? (y: 저장 / n: 종료 / 엔터: 다음 / 요구사항: 요구사항 추가) >>> ")
                
                if answer.lower() == 'y':
                    save_sentence_and_code(current_sentence, all_items[choice_no])
                    break
                elif answer.lower() == 'n':
                    print("종료합니다.")
                    break 
                elif answer == "":
                    # 빈칸 엔터: 다음 후보로 이동
                    choice_no += 1
                    if choice_no >= len(all_items):
                        print("후보가 더 이상 없습니다.")
                        #break
                else:
                    # 어떤 문자열이든 요구사항으로 누적
                    all_items = []
                    choice_no = 0
                    current_sentence += " " + f"+추가 조건: {answer}"
                    new_dataset = [current_sentence]
                    joilang_each_command(new_dataset, selected_model)
                    print(f"요구사항 {try_no} '{answer}' 반영하여 재시작")
                    try_no += 1

    elif len(args) == 1:
        #selected_model = args[0]
        #paths = [selected_model]
        mode = args[0]
        if(mode=='dataset'):
            for each_sentence in dataset:
                print('dataset length:: ', len(dataset))
                joilang_each_command(sentences=each_sentence)
        elif('version' in mode):
            benchmark_each_command(model = mode)
        else:
            joilang_each_command(sentences=mode)        
    else:
        base_dir = "."
        paths = []
        for name in os.listdir(base_dir):
            tmp_path = os.path.join(base_dir, name)
            if os.path.isdir(tmp_path):
                config_path = os.path.join(tmp_path, "model_config.json")
                if os.path.isfile(config_path):
                    paths.append(name)
        benchmark_each_command()
