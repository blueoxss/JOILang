#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LLMBackendError(RuntimeError):
    def __init__(self, message: str, error_type: str = "unknown_error", raw: Any | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.raw = raw


def get_openai_api_key() -> str:
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("JOI_EVAL_OPENAI_API_KEY")
        or os.environ.get("JOI_V15_OPENAI_API_KEY")
        or ""
    )


def messages_from_rendered(rendered_package: dict[str, Any]) -> list[dict[str, str]]:
    messages = rendered_package.get("messages")
    if isinstance(messages, list) and messages:
        return [
            {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")}
            for item in messages
            if isinstance(item, dict)
        ]
    system = str(rendered_package.get("system_prompt") or rendered_package.get("prompt_text") or "")
    user = str(rendered_package.get("user_prompt") or "")
    out = []
    if system:
        out.append({"role": "system", "content": system})
    if user:
        out.append({"role": "user", "content": user})
    return out or [{"role": "user", "content": str(rendered_package.get("prompt_text") or "")}]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _classify_text_error(text: str, fallback: str = "unknown_error") -> str:
    lowered = str(text or "").lower()
    if "cuda" in lowered and ("out of memory" in lowered or "oom" in lowered):
        return "cuda_oom"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "unauthorized" in lowered or "401" in lowered or "invalid api key" in lowered:
        return "openai_unauthorized"
    if "rate limit" in lowered or "429" in lowered:
        return "openai_rate_limit"
    if "no such file" in lowered or "not found" in lowered or "from_pretrained" in lowered:
        return "model_load_error"
    return fallback


def _usage(prompt_tokens: Any = 0, completion_tokens: Any = 0, total_tokens: Any = 0) -> dict[str, int]:
    prompt = _int(prompt_tokens, 0)
    completion = _int(completion_tokens, 0)
    total = _int(total_tokens, prompt + completion)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _worker_path(rendered_package: dict[str, Any], extra_payload: dict[str, Any]) -> Path:
    model_input = rendered_package.get("model_input") if isinstance(rendered_package.get("model_input"), dict) else {}
    raw = (
        extra_payload.get("local_worker")
        or os.environ.get("JOI_GA_WORKER_PATH")
        or model_input.get("local_worker")
        or ""
    )
    if not raw:
        raise LLMBackendError("worker mode requires a local_worker path from render metadata, --llm-extra-json, or JOI_GA_WORKER_PATH", "model_load_error")
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        package_path = Path(str(rendered_package.get("source_model_package") or "."))
        path = package_path / path
    path = path.resolve()
    if not path.exists():
        raise LLMBackendError(f"worker script not found: {path}", "model_load_error")
    return path


def _call_worker(
    rendered_package: dict[str, Any],
    *,
    model_key: str,
    timeout_sec: int,
    extra_payload: dict[str, Any],
) -> dict[str, Any]:
    worker = _worker_path(rendered_package, extra_payload)
    worker_python = (
        str(extra_payload.get("worker_python") or "")
        or os.environ.get("JOI_GA_WORKER_PYTHON", "")
        or os.environ.get("JOI_VERSION013_PYTHON", "")
        or sys.executable
        or "python"
    )
    model_input = rendered_package.get("model_input") if isinstance(rendered_package.get("model_input"), dict) else {}
    model_config = rendered_package.get("model_config") if isinstance(rendered_package.get("model_config"), dict) else {}
    messages = messages_from_rendered(rendered_package)
    payload = {
        "model": model_key or model_config.get("model_name") or "local-model",
        "local_model_name": extra_payload.get("local_model_name") or model_input.get("local_model_name") or model_key or model_config.get("model_name") or "",
        "messages": messages,
        "local_device": extra_payload.get("local_device") or os.environ.get("JOI_GA_LOCAL_DEVICE", "cuda"),
        "local_dtype": extra_payload.get("local_dtype") or os.environ.get("JOI_GA_LOCAL_DTYPE", "bf16"),
        "local_max_new_tokens": _int(extra_payload.get("local_max_new_tokens") or os.environ.get("JOI_GA_MAX_NEW_TOKENS"), 512),
        "local_files_only": _bool(extra_payload.get("local_files_only"), True),
        "local_trust_remote_code": _bool(extra_payload.get("local_trust_remote_code"), False),
        "local_load_in_4bit": _bool(extra_payload.get("local_load_in_4bit"), False),
    }
    for key, value in extra_payload.items():
        if key.startswith("local_") and key not in payload:
            payload[key] = value
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [worker_python, str(worker)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMBackendError(f"worker timed out after {timeout_sec} seconds", "timeout") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise LLMBackendError(f"worker failed with exit code {completed.returncode}: {detail}", _classify_text_error(detail, "worker_crash"))
    try:
        raw = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise LLMBackendError(f"worker returned non-JSON output: {(completed.stdout or '')[:500]}", "worker_crash") from exc
    if not raw.get("ok", True):
        error_type = str(raw.get("error_type") or _classify_text_error(str(raw.get("error") or ""), "worker_crash"))
        raise LLMBackendError(str(raw.get("error") or "worker failed"), error_type, raw=raw)
    usage = _usage(raw.get("prompt_tokens"), raw.get("completion_tokens"))
    return {
        "content": str(raw.get("content") or ""),
        "usage": usage,
        "latency_sec": round(time.perf_counter() - started, 6),
        "peak_vram_gb": raw.get("peak_vram_gb", ""),
        "raw": raw,
        "backend": "worker",
        "request": {"worker_path": str(worker), "worker_python": worker_python, "payload": {k: v for k, v in payload.items() if k != "messages"}},
    }


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_sec: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        if exc.code == 401:
            error_type = "openai_unauthorized"
        elif exc.code == 429:
            error_type = "openai_rate_limit"
        else:
            error_type = _classify_text_error(body, "unknown_error")
        raise LLMBackendError(f"HTTP {exc.code}: {body[:500]}", error_type) from exc
    except urllib.error.URLError as exc:
        raise LLMBackendError(str(exc), _classify_text_error(str(exc), "model_load_error")) from exc


def _call_openai_compatible_http(
    rendered_package: dict[str, Any],
    *,
    model_key: str,
    endpoint: str,
    timeout_sec: int,
    extra_payload: dict[str, Any],
    api_key: str = "",
    backend: str = "local",
) -> dict[str, Any]:
    payload = {
        "model": model_key or extra_payload.get("model") or "local-model",
        "temperature": float(extra_payload.get("temperature", 0.0) or 0.0),
        "max_tokens": _int(extra_payload.get("max_tokens") or os.environ.get("JOI_GA_MAX_NEW_TOKENS"), 512),
        "messages": messages_from_rendered(rendered_package),
    }
    for key, value in extra_payload.items():
        if key not in payload and key not in {"api_key", "worker_python", "local_worker"}:
            payload[key] = value
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    started = time.perf_counter()
    raw = _request_json(endpoint, payload, headers, timeout_sec)
    try:
        content = raw["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMBackendError(f"endpoint returned unexpected payload: {raw}", "unknown_error") from exc
    usage_raw = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    return {
        "content": str(content or ""),
        "usage": _usage(usage_raw.get("prompt_tokens"), usage_raw.get("completion_tokens"), usage_raw.get("total_tokens")),
        "latency_sec": round(time.perf_counter() - started, 6),
        "peak_vram_gb": raw.get("peak_vram_gb", ""),
        "raw": raw,
        "backend": backend,
        "request": {"endpoint": endpoint, "model": payload["model"]},
    }


def _call_openai_sdk(
    rendered_package: dict[str, Any],
    *,
    model_key: str,
    endpoint: str,
    timeout_sec: int,
    extra_payload: dict[str, Any],
) -> dict[str, Any]:
    key = get_openai_api_key()
    if not key:
        raise LLMBackendError("openai mode requires OPENAI_API_KEY, JOI_EVAL_OPENAI_API_KEY, or JOI_V15_OPENAI_API_KEY", "openai_unauthorized")
    try:
        from openai import OpenAI
    except Exception as exc:
        raise LLMBackendError("openai package is not installed", "model_load_error") from exc
    client = OpenAI(api_key=key, base_url=endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1", timeout=timeout_sec)
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model_key or str(extra_payload.get("model") or "gpt-4.1-mini"),
            messages=messages_from_rendered(rendered_package),
            temperature=float(extra_payload.get("temperature", 0.0) or 0.0),
            max_tokens=_int(extra_payload.get("max_tokens") or os.environ.get("JOI_GA_MAX_NEW_TOKENS"), 512),
        )
    except Exception as exc:
        raise LLMBackendError(str(exc), _classify_text_error(str(exc), "unknown_error")) from exc
    content = response.choices[0].message.content if response.choices else ""
    usage_raw = getattr(response, "usage", None)
    usage = _usage(
        getattr(usage_raw, "prompt_tokens", 0),
        getattr(usage_raw, "completion_tokens", 0),
        getattr(usage_raw, "total_tokens", 0),
    )
    raw = response.model_dump() if hasattr(response, "model_dump") else {"content": content}
    return {
        "content": str(content or ""),
        "usage": usage,
        "latency_sec": round(time.perf_counter() - started, 6),
        "peak_vram_gb": "",
        "raw": raw,
        "backend": "openai",
        "request": {"base_url": endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1", "model": model_key or "gpt-4.1-mini"},
    }


def call_llm_backend(
    *,
    llm_mode: str,
    rendered_package: dict[str, Any],
    model_key: str = "",
    endpoint: str = "",
    timeout_sec: int = 1800,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = str(llm_mode or "mock").strip().lower()
    extra = extra_payload or {}
    if mode == "worker":
        return _call_worker(rendered_package, model_key=model_key, timeout_sec=timeout_sec, extra_payload=extra)
    if mode == "local":
        local_endpoint = endpoint or os.environ.get("JOI_GA_LOCAL_ENDPOINT") or "http://127.0.0.1:8000/v1/chat/completions"
        return _call_openai_compatible_http(
            rendered_package,
            model_key=model_key,
            endpoint=local_endpoint,
            timeout_sec=timeout_sec,
            extra_payload=extra,
            api_key=str(extra.get("api_key") or os.environ.get("JOI_GA_LOCAL_API_KEY") or ""),
            backend="local",
        )
    if mode == "openai":
        return _call_openai_sdk(
            rendered_package,
            model_key=model_key,
            endpoint=endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
            timeout_sec=timeout_sec,
            extra_payload=extra,
        )
    raise LLMBackendError(f"unsupported llm_mode: {llm_mode}", "unsupported_llm_mode")
