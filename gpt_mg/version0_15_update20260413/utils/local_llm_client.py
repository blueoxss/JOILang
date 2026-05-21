#!/usr/bin/env python3
# Assumption: by default this client reuses the existing local worker environment from gpt_mg/version0_13 without modifying it.
from __future__ import annotations

import atexit
import json
import os
import select
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

from utils.pipeline_common import REPO_ROOT, dump_json

# ---------------------------------------------------------------------
# JOI local LLM worker debug utilities
# Enable with:
#   JOI_V15_DEBUG_WORKER=1
# Optional:
#   JOI_V15_DEBUG_LOG=/tmp/joi_local_llm_worker_debug.log
# ---------------------------------------------------------------------
def _joi_debug_enabled() -> bool:
    return str(os.environ.get("JOI_V15_DEBUG_WORKER", "")).lower() in {"1", "true", "yes", "on"}


def _joi_debug_log_path() -> str:
    return os.environ.get("JOI_V15_DEBUG_LOG", "/tmp/joi_local_llm_worker_debug.log")


def _joi_debug_log(message: str) -> None:
    if not _joi_debug_enabled():
        return

    try:
        from datetime import datetime
        with open(_joi_debug_log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        # Debug logger must never break benchmark execution.
        pass


def _joi_debug_exc(context: str, exc: BaseException | None = None) -> None:
    if not _joi_debug_enabled():
        return

    try:
        import traceback
        if exc is None:
            _joi_debug_log(f"{context}\n{traceback.format_exc()}")
        else:
            _joi_debug_log(
                f"{context}\n"
                f"exception_type={type(exc).__name__}\n"
                f"exception_message={exc}\n"
                f"{traceback.format_exc()}"
            )
    except Exception:
        pass


def _joi_read_available_pipe(pipe, max_bytes: int = 200_000) -> str:
    """
    Non-blocking best-effort read from a subprocess pipe.
    Safe for debugging worker stderr when the worker crashed or gave no response.
    """
    if pipe is None:
        return ""

    try:
        import os as _os
        import select

        fd = pipe.fileno()
        chunks = []
        total = 0

        while total < max_bytes:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break

            data = _os.read(fd, min(8192, max_bytes - total))
            if not data:
                break

            chunks.append(data)
            total += len(data)

        return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as e:
        return f"<failed to read pipe: {type(e).__name__}: {e}>"
    

# Persistent worker stderr is drained in a background thread.
# This prevents the worker from blocking when transformers/tqdm writes a lot of logs
# and preserves the recent stderr tail for crash diagnostics.
_PERSISTENT_WORKER_STDERR_BUFFER: deque[str] = deque(maxlen=1000)
_PERSISTENT_WORKER_STDERR_THREAD: threading.Thread | None = None


def _joi_worker_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONFAULTHANDLER", "1")
    env.setdefault("TRANSFORMERS_VERBOSITY", "error")
    env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    return env


def _joi_drain_pipe_to_debug(pipe, label: str) -> None:
    """Continuously drain a subprocess pipe so the worker cannot block on stderr."""
    if pipe is None:
        return
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            text = line.rstrip("\n")
            _PERSISTENT_WORKER_STDERR_BUFFER.append(text)
            if _joi_debug_enabled():
                _joi_debug_log(f"{label}: {text}")
    except Exception as exc:
        _PERSISTENT_WORKER_STDERR_BUFFER.append(f"<stderr drain failed: {type(exc).__name__}: {exc}>")
        _joi_debug_log(f"{label}: stderr drain failed: {type(exc).__name__}: {exc}")


def _joi_persistent_stderr_tail(max_lines: int = 120) -> str:
    if not _PERSISTENT_WORKER_STDERR_BUFFER:
        return ""
    return "\n".join(list(_PERSISTENT_WORKER_STDERR_BUFFER)[-max_lines:])


def _joi_debug_payload_summary(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return f"payload_type={type(payload).__name__}"
    messages = payload.get("messages") or []
    message_lengths = []
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                message_lengths.append({
                    "role": message.get("role"),
                    "chars": len(str(message.get("content", ""))),
                })
    summary = {
        "keys": sorted(payload.keys()),
        "model": payload.get("model"),
        "local_model_name": payload.get("local_model_name"),
        "local_device": payload.get("local_device"),
        "local_dtype": payload.get("local_dtype"),
        "local_files_only": payload.get("local_files_only"),
        "local_load_in_4bit": payload.get("local_load_in_4bit"),
        "local_max_new_tokens": payload.get("local_max_new_tokens"),
        "message_lengths": message_lengths,
    }
    return json.dumps(summary, ensure_ascii=False, default=str)


def _env(name_v15: str, name_v14: str, default: str = "") -> str:
    value = os.getenv(name_v15, "").strip()
    if value:
        return value
    value = os.getenv(name_v14, "").strip()
    if value:
        return value
    return default


DEFAULT_MODEL = _env("JOI_V15_MODEL", "JOI_V14_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
DEFAULT_MODE = _env("JOI_V15_LLM_MODE", "JOI_V14_LLM_MODE", "worker")
DEFAULT_ENDPOINT = _env("JOI_V15_OPENAI_ENDPOINT", "JOI_V14_OPENAI_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
DEFAULT_WORKER = str((REPO_ROOT / "gpt_mg" / "version0_13" / "qwen_local_worker.py").resolve())
DEFAULT_PERSISTENT_WORKER = str((Path(__file__).resolve().parent / "persistent_qwen_worker.py").resolve())
DEFAULT_PYTHON = _env("JOI_V15_PYTHON", "JOI_V14_PYTHON", sys.executable or "python3")
DEFAULT_HF_MODULES_CACHE = _env("JOI_V15_HF_MODULES_CACHE", "JOI_V14_HF_MODULES_CACHE", "/tmp/joi_v15_hf_modules")

_PYTHON_RUNTIME_PROBE = (
    "import json\n"
    "payload = {}\n"
    "try:\n"
    "    import torch\n"
    "    payload['ok'] = True\n"
    "    payload['torch_version'] = getattr(torch, '__version__', '')\n"
    "    payload['cuda_available'] = bool(torch.cuda.is_available())\n"
    "    payload['device_count'] = int(torch.cuda.device_count()) if payload['cuda_available'] else 0\n"
    "    payload['cuda_devices'] = [torch.cuda.get_device_name(i) for i in range(payload['device_count'])] if payload['cuda_available'] else []\n"
    "except Exception as exc:\n"
    "    payload['ok'] = False\n"
    "    payload['error'] = str(exc)\n"
    "try:\n"
    "    import transformers\n"
    "    payload['transformers_version'] = getattr(transformers, '__version__', '')\n"
    "except Exception as exc:\n"
    "    payload.setdefault('warnings', []).append(f'transformers: {exc}')\n"
    "print(json.dumps(payload, ensure_ascii=False))\n"
)


def classify_error_text(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return "unknown_error"
    if "out of memory" in lowered or "cuda out of memory" in lowered or "cuda oom" in lowered:
        return "cuda_oom"
    if "gatedrepoerror" in lowered or "gated repo" in lowered or "access to model" in lowered:
        return "gated_model"
    if "local_files_only=true" in lowered or "not cached locally" in lowered:
        return "missing_cache"
    if "incompatible runtime" in lowered or "python_not_found" in lowered:
        return "incompatible_runtime"
    if "timed out" in lowered or "timeout" in lowered:
        return "cpu_fallback_timeout"
    if "non-json" in lowered or "invalid json" in lowered or "jsondecodeerror" in lowered:
        return "invalid_json"
    if "worker" in lowered and ("failed" in lowered or "closed" in lowered or "broke" in lowered or "crash" in lowered):
        return "worker_crash"
    if "401" in lowered and "unauthorized" in lowered:
        return "gated_model"
    if "repo id must be in the form" in lowered:
        return "incompatible_runtime"
    return "local_llm_error"


def is_oom_error_type(error_type: str) -> bool:
    return str(error_type or "").strip().lower() == "cuda_oom"


class LocalLLMError(RuntimeError):
    def __init__(self, message: str, *, error_type: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_type = str(error_type or classify_error_text(message))
        self.details = dict(details or {})


def _python_has_torch(python_path: str) -> bool:
    return bool(_probe_python_runtime(python_path).get("ok"))


def _probe_python_runtime(python_path: str) -> dict[str, Any]:
    if not python_path:
        return {"ok": False, "python_path": python_path, "error": "empty_python_path"}
    candidate = Path(python_path).expanduser()
    if not candidate.exists():
        return {"ok": False, "python_path": str(candidate), "error": "python_not_found"}
    try:
        completed = subprocess.run(
            [str(candidate), "-c", _PYTHON_RUNTIME_PROBE],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "python_path": str(candidate), "error": str(exc)}
    
    
    if completed.returncode != 0:
        return {
            "ok": False,
            "python_path": str(candidate),
            "error": (completed.stderr or completed.stdout or "").strip() or f"exit_code={completed.returncode}",
        }
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except Exception as exc:
        return {
            "ok": False,
            "python_path": str(candidate),
            "error": f"invalid_probe_output: {exc}",
            "stdout": (completed.stdout or "")[:500],
        }
    if not isinstance(payload, dict):
        payload = {"ok": False, "error": f"unexpected_probe_payload: {type(payload).__name__}"}
    payload["python_path"] = str(candidate)
    return payload


def _discover_worker_python() -> str:
    explicit = _env("JOI_V15_WORKER_PYTHON", "JOI_V14_WORKER_PYTHON")
    if explicit:
        return explicit
    candidates = [
        DEFAULT_PYTHON,
        "/home/mgjeong/miniconda3/envs/l/bin/python",
        "/home/mgjeong/miniconda3/envs/paper-gpu/bin/python",
        "/home/mgjeong/miniconda3/envs/nas_new/bin/python",
        "/home/andrew/llm/v/bin/python",
        "/usr/bin/python3",
    ]
    seen: set[str] = set()
    ok_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        probe = _probe_python_runtime(candidate)
        if probe.get("ok"):
            ok_candidates.append(probe)
            if bool(probe.get("cuda_available")):
                return str(probe["python_path"])
    if ok_candidates:
        return str(ok_candidates[0]["python_path"])
    return DEFAULT_PYTHON


DEFAULT_WORKER_PYTHON = _discover_worker_python()
_PERSISTENT_WORKER_PROCESS: subprocess.Popen[str] | None = None
_PERSISTENT_WORKER_KEY: tuple[str, ...] | None = None


def _hf_cache_root() -> Path:
    explicit = os.getenv("HF_HUB_CACHE", "").strip() or os.getenv("HUGGINGFACE_HUB_CACHE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    transformers_cache = os.getenv("TRANSFORMERS_CACHE", "").strip()
    if transformers_cache:
        return Path(transformers_cache).expanduser()
    return Path.home() / ".cache" / "huggingface" / "hub"


def _hf_repo_cache_dir(model_name: str) -> Path:
    return _hf_cache_root() / f"models--{model_name.replace('/', '--')}"


def _resolve_local_model_name(model_name: str) -> str:
    raw = str(model_name or "").strip()
    if not raw:
        return raw
    path = Path(raw).expanduser()
    if path.exists():
        return str(path.resolve())
    if "/" not in raw:
        return raw
    cache_dir = _hf_repo_cache_dir(raw)
    snapshots_dir = cache_dir / "snapshots"
    if not snapshots_dir.exists():
        return raw
    snapshots = sorted((item for item in snapshots_dir.iterdir() if item.is_dir()), key=lambda item: item.name)
    if not snapshots:
        return raw
    return str(snapshots[-1].resolve())


def describe_worker_runtime(python_path: str | None = None) -> dict[str, Any]:
    worker_python = str(python_path or DEFAULT_WORKER_PYTHON)
    runtime = _probe_python_runtime(worker_python)
    runtime["worker_path"] = _env("JOI_V15_WORKER_PATH", "JOI_V14_WORKER_PATH", DEFAULT_WORKER)
    runtime["persistent_worker_path"] = _env(
        "JOI_V15_PERSISTENT_WORKER_PATH",
        "JOI_V14_PERSISTENT_WORKER_PATH",
        DEFAULT_PERSISTENT_WORKER,
    )
    runtime["persistent_worker"] = _use_persistent_worker()
    runtime["hf_modules_cache"] = DEFAULT_HF_MODULES_CACHE
    return runtime


def _local_max_new_tokens(max_tokens: int) -> int:
    configured = _env("JOI_V15_LOCAL_MAX_NEW_TOKENS", "JOI_V14_LOCAL_MAX_NEW_TOKENS", "256")
    try:
        configured_value = int(configured)
    except Exception:
        configured_value = 256
    if configured_value <= 0:
        configured_value = int(max_tokens)
    return max(32, min(int(max_tokens), configured_value))


def _use_persistent_worker() -> bool:
    value = _env("JOI_V15_PERSISTENT_WORKER", "JOI_V14_PERSISTENT_WORKER", "true").lower()
    return value in {"1", "true", "yes", "on"}


def _payload_use_persistent_worker(extra_payload: dict[str, Any] | None) -> bool:
    if extra_payload:
        for key in ("persistent_worker", "local_persistent_worker", "worker_reuse"):
            if key not in extra_payload:
                continue
            value = extra_payload.get(key)
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return _use_persistent_worker()

def _is_phi_family_model(model_name: str) -> bool:
    normalized = str(model_name or "").strip().lower()

    return any(
        marker in normalized
        for marker in (
            "microsoft/phi",
            "microsoft--phi",
            "phi-3",
            "phi3",
            "phi-3.5",
            "phi35",
            "phi-4",
            "phi4",
        )
    )


def _infer_default_attn_implementation(model: str, local_model_name: str) -> str:
    """
    Phi-family models can emit warnings or fail on sliding-window attention paths
    when flash-attn/window_size support is unavailable.

    If the user did not explicitly set JOI_V15_LOCAL_ATTN_IMPLEMENTATION,
    default Phi-family models to attn_implementation='eager'.

    Explicit environment/config values still take precedence.
    """
    configured = _env("JOI_V15_LOCAL_ATTN_IMPLEMENTATION", "JOI_V14_LOCAL_ATTN_IMPLEMENTATION", "").strip()
    if configured:
        return configured

    if _is_phi_family_model(model) or _is_phi_family_model(local_model_name):
        return "eager"

    return ""

def _local_model_dir_from_base(model: str, configured_model_name: str) -> str:
    """
    If JOI_V15_LOCAL_MODEL_BASE_DIR is set, map known benchmark model ids
    to local folders downloaded by download_models.sh.

    This keeps --model-key as the benchmark registry key while loading weights
    from local_models/<model_folder>.
    """
    base_dir = _env("JOI_V15_LOCAL_MODEL_BASE_DIR", "JOI_V14_LOCAL_MODEL_BASE_DIR", "").strip()
    if not base_dir:
        return configured_model_name

    # Explicit JOI_V15_LOCAL_MODEL_NAME should still win.
    explicit_model_name = _env("JOI_V15_LOCAL_MODEL_NAME", "JOI_V14_LOCAL_MODEL_NAME", "").strip()
    if explicit_model_name:
        return explicit_model_name

    normalized = str(model or "").strip().lower()

    mapping = {
        "microsoft/phi-3.5-mini-instruct": "phi35_mini",
        "google/gemma-2-9b-it": "gemma2_9b_it",
        "qwen/qwen2.5-coder-7b-instruct": "qwen25_coder_7b",

        # Llama 3.1 8B variants
        "meta-llama/llama-3.1-8b-instruct": "llama31_8b",
        "meta-llama/meta-llama-3.1-8b-instruct": "llama31_8b",

        "qwen/qwen2.5-coder-14b-instruct": "qwen25_coder_14b",
    }

    folder_name = mapping.get(normalized)
    if not folder_name:
        return configured_model_name

    if folder_name is None and "llama-3.1-8b" in normalized:
        folder_name = "llama31_8b"
        
    candidate = Path(base_dir).expanduser() / folder_name
    if candidate.exists():
        return str(candidate.resolve())

    return configured_model_name

def _build_worker_payload(
    system: str,
    user: str,
    *,
    model: str,
    max_tokens: int,
    extra_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    configured_model_name = _env("JOI_V15_LOCAL_MODEL_NAME", "JOI_V14_LOCAL_MODEL_NAME", model)
    configured_model_name = _local_model_dir_from_base(model, configured_model_name)
    default_attn_implementation = _infer_default_attn_implementation(model, configured_model_name)  

    payload = {
        "model": model,
        "local_model_name": configured_model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "local_device": _env("JOI_V15_LOCAL_DEVICE", "JOI_V14_LOCAL_DEVICE", "cuda:1"),
        "local_dtype": _env("JOI_V15_LOCAL_DTYPE", "JOI_V14_LOCAL_DTYPE", "bf16"),
        "local_max_new_tokens": _local_max_new_tokens(max_tokens),
        "local_files_only": _env("JOI_V15_LOCAL_FILES_ONLY", "JOI_V14_LOCAL_FILES_ONLY", "true").lower() in {"1", "true", "yes", "on"},
        "local_trust_remote_code": _env("JOI_V15_LOCAL_TRUST_REMOTE_CODE", "JOI_V14_LOCAL_TRUST_REMOTE_CODE", "false").lower() in {"1", "true", "yes", "on"},
        "local_load_in_4bit": _env("JOI_V15_LOCAL_LOAD_IN_4BIT", "JOI_V14_LOCAL_LOAD_IN_4BIT", "false").lower() in {"1", "true", "yes", "on"},
        "local_hf_modules_cache": DEFAULT_HF_MODULES_CACHE,
        "local_attn_implementation": default_attn_implementation,
    }    
    if extra_payload:
        payload.update(extra_payload)

    # If extra_payload cleared local_attn_implementation, re-apply Phi default.
    if not str(payload.get("local_attn_implementation", "") or "").strip():
        inferred_attn = _infer_default_attn_implementation(
            str(payload.get("model", model)),
            str(payload.get("local_model_name", configured_model_name)),
        )
        if inferred_attn:
            payload["local_attn_implementation"] = inferred_attn

    payload["local_model_name"] = _resolve_local_model_name(str(payload.get("local_model_name", "")))
    if not str(payload.get("local_attn_implementation", "") or "").strip():
        inferred_attn = _infer_default_attn_implementation(
            str(payload.get("model", model)),
            str(payload.get("local_model_name", "")),
        )
        if inferred_attn:
            payload["local_attn_implementation"] = inferred_attn

    payload["local_hf_modules_cache"] = str(Path(str(payload.get("local_hf_modules_cache", DEFAULT_HF_MODULES_CACHE))).expanduser())
    return payload

def _persistent_worker_key(worker_python: str, worker_path: str, payload: dict[str, Any]) -> tuple[str, ...]:
    return (
        worker_python,
        worker_path,
        str(payload.get("local_model_name", "")),
        str(payload.get("local_device", "")),
        str(payload.get("local_dtype", "")),
        str(payload.get("local_files_only", "")),
        str(payload.get("local_trust_remote_code", "")),
        str(payload.get("local_load_in_4bit", "")),
        str(payload.get("local_attn_implementation", "")),
    )



def _close_persistent_worker() -> None:
    global _PERSISTENT_WORKER_PROCESS, _PERSISTENT_WORKER_KEY
    process = _PERSISTENT_WORKER_PROCESS
    _PERSISTENT_WORKER_PROCESS = None
    _PERSISTENT_WORKER_KEY = None
    if process is None:
        return

    _joi_debug_log(
        "CLOSE persistent worker\n"
        f"pid={getattr(process, 'pid', None)}\n"
        f"returncode_before={process.poll()}"
    )

    try:
        if process.stdin and process.poll() is None:
            process.stdin.write(json.dumps({"_command": "shutdown"}) + "\n")
            process.stdin.flush()
    except Exception as exc:
        _joi_debug_log(f"failed to send persistent worker shutdown command: {type(exc).__name__}: {exc}")

    try:
        process.wait(timeout=5)
    except Exception:
        try:
            _joi_debug_log("persistent worker did not exit after shutdown; killing")
            process.kill()
        except Exception as exc:
            _joi_debug_log(f"failed to kill persistent worker: {type(exc).__name__}: {exc}")

    _joi_debug_log(
        "CLOSED persistent worker\n"
        f"returncode_after={process.poll()}\n"
        f"stderr_tail:\n{_joi_persistent_stderr_tail()}"
    )

atexit.register(_close_persistent_worker)


def close_persistent_worker() -> None:
    _close_persistent_worker()



def _ensure_persistent_worker(worker_python: str, worker_path: str, payload: dict[str, Any]) -> subprocess.Popen[str]:
    global _PERSISTENT_WORKER_PROCESS, _PERSISTENT_WORKER_KEY, _PERSISTENT_WORKER_STDERR_THREAD

    key = _persistent_worker_key(worker_python, worker_path, payload)
    process = _PERSISTENT_WORKER_PROCESS

    if process is not None and process.poll() is None and _PERSISTENT_WORKER_KEY == key:
        return process

    _close_persistent_worker()
    _PERSISTENT_WORKER_STDERR_BUFFER.clear()

    env = _joi_worker_env()

    _joi_debug_log(
        "START persistent worker\n"
        f"worker_python={worker_python}\n"
        f"worker_path={worker_path}\n"
        f"cwd={os.getcwd()}\n"
        f"JOI_V15_LOCAL_DEVICE={env.get('JOI_V15_LOCAL_DEVICE')}\n"
        f"TRANSFORMERS_VERBOSITY={env.get('TRANSFORMERS_VERBOSITY')}\n"
        f"HF_HUB_DISABLE_PROGRESS_BARS={env.get('HF_HUB_DISABLE_PROGRESS_BARS')}\n"
        f"TOKENIZERS_PARALLELISM={env.get('TOKENIZERS_PARALLELISM')}\n"
        f"PYTHONUNBUFFERED={env.get('PYTHONUNBUFFERED')}\n"
        f"PYTHONFAULTHANDLER={env.get('PYTHONFAULTHANDLER')}\n"
        f"payload_summary={_joi_debug_payload_summary(payload)}"
    )

    try:
        process = subprocess.Popen(
            [worker_python, worker_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
    except Exception as exc:
        _joi_debug_exc("FAILED TO START persistent worker", exc)
        raise LocalLLMError(
            f"failed to start persistent worker: {type(exc).__name__}: {exc}",
            error_type="worker_crash",
        ) from exc

    if process.stderr is not None:
        _PERSISTENT_WORKER_STDERR_THREAD = threading.Thread(
            target=_joi_drain_pipe_to_debug,
            args=(process.stderr, f"persistent worker pid={process.pid} stderr"),
            daemon=True,
        )
        _PERSISTENT_WORKER_STDERR_THREAD.start()

    if process.stdin is None or process.stdout is None or process.stderr is None:
        _joi_debug_log(
            "persistent worker missing one or more pipes\n"
            f"stdin={process.stdin is not None}\n"
            f"stdout={process.stdout is not None}\n"
            f"stderr={process.stderr is not None}\n"
            f"returncode={process.poll()}"
        )
        raise LocalLLMError("persistent worker did not expose stdin/stdout/stderr pipes", error_type="worker_crash")

    _joi_debug_log(
        "persistent worker started\n"
        f"pid={process.pid}\n"
        f"returncode={process.poll()}"
    )

    _PERSISTENT_WORKER_PROCESS = process
    _PERSISTENT_WORKER_KEY = key
    return process


def _read_persistent_worker_response(process: subprocess.Popen[str], timeout_sec: int) -> dict[str, Any]:
    if process.stdout is None:
        raise LocalLLMError("persistent worker stdout is unavailable", error_type="worker_crash")

    _joi_debug_log(
        "WAIT persistent worker response\n"
        f"pid={getattr(process, 'pid', None)}\n"
        f"timeout_sec={timeout_sec}\n"
        f"returncode_before={process.poll()}"
    )

    ready, _, _ = select.select([process.stdout], [], [], timeout_sec)
    if not ready:
        rc = process.poll()
        stderr_tail = _joi_persistent_stderr_tail()
        _joi_debug_log(
            "PERSISTENT WORKER TIMEOUT\n"
            f"returncode={rc}\n"
            f"timeout_sec={timeout_sec}\n"
            f"stderr_tail:\n{stderr_tail}"
        )
        raise LocalLLMError(
            f"persistent worker timed out after {timeout_sec} seconds; "
            f"returncode={rc}; stderr_tail={stderr_tail[-4000:]}",
            error_type="cpu_fallback_timeout",
            details={"returncode": rc, "stderr_tail": stderr_tail[-4000:]},
        )

    line = process.stdout.readline()

    if not line:
        rc = process.poll()
        stderr_tail = _joi_persistent_stderr_tail()

        _joi_debug_log(
            "PERSISTENT WORKER EMPTY RESPONSE\n"
            f"returncode={rc}\n"
            f"timeout_sec={timeout_sec}\n"
            f"stderr_tail:\n{stderr_tail}"
        )

        raise LocalLLMError(
            f"persistent worker returned empty response; "
            f"returncode={rc}; stderr_tail={stderr_tail[-4000:]}",
            error_type="worker_crash",
            details={"returncode": rc, "stderr_tail": stderr_tail[-4000:]},
        )

    _joi_debug_log(f"PERSISTENT WORKER RAW RESPONSE HEAD={line[:1000]!r}")

    try:
        payload = json.loads(line)
    except Exception as exc:
        stderr_tail = _joi_persistent_stderr_tail()

        _joi_debug_log(
            "PERSISTENT WORKER BAD JSON RESPONSE\n"
            f"raw_line={line!r}\n"
            f"stderr_tail:\n{stderr_tail}"
        )

        raise LocalLLMError(
            f"persistent worker returned non-JSON response: {line[:1000]!r}; "
            f"stderr_tail={stderr_tail[-4000:]}",
            error_type="invalid_json",
            details={"raw_line": line[:4000], "stderr_tail": stderr_tail[-4000:]},
        ) from exc

    if not payload.get("ok", False):
        error_text = str(payload.get("error", "persistent worker failed"))
        stderr_tail = _joi_persistent_stderr_tail()
        details = dict(payload)
        if stderr_tail and "stderr_tail" not in details:
            details["stderr_tail"] = stderr_tail[-4000:]
        _joi_debug_log(
            "PERSISTENT WORKER RETURNED ERROR PAYLOAD\n"
            f"error_text={error_text}\n"
            f"payload={json.dumps(payload, ensure_ascii=False, default=str)[:4000]}\n"
            f"stderr_tail:\n{stderr_tail}"
        )
        raise LocalLLMError(
            error_text,
            error_type=str(payload.get("error_type") or classify_error_text(error_text)),
            details=details,
        )
    return payload

def _request_json(
    url: str,
    payload: dict[str, Any],
    timeout_sec: int,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_auth_headers() -> dict[str, str]:
    bearer = _env("JOI_V15_HTTP_AUTH_BEARER", "JOI_V14_HTTP_AUTH_BEARER", "")
    if not bearer:
        bearer = _env("JOI_V15_OPENAI_API_KEY", "JOI_V14_OPENAI_API_KEY", "")
    if not bearer:
        return {}
    return {"Authorization": f"Bearer {bearer}"}


def _call_openai_compatible(
    system: str,
    user: str,
    *,
    endpoint: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_sec: int,
    extra_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if extra_payload:
        payload.update(extra_payload)
    response = _request_json(
        endpoint,
        payload,
        timeout_sec,
        headers=_request_auth_headers(),
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LocalLLMError(f"OpenAI-compatible endpoint returned unexpected payload: {response}") from exc
    usage = response.get("usage") or {}
    return {
        "content": content,
        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
        "completion_tokens": int(usage.get("completion_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "raw": response,
    }



def _call_worker(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_sec: int,
    extra_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = _build_worker_payload(
        system,
        user,
        model=model,
        max_tokens=max_tokens,
        extra_payload=extra_payload,
    )
    worker_python = DEFAULT_WORKER_PYTHON
    worker_path = _env("JOI_V15_WORKER_PATH", "JOI_V14_WORKER_PATH", DEFAULT_WORKER)
    env = _joi_worker_env()

    _joi_debug_log(
        "START one-shot local worker\n"
        f"worker_python={worker_python}\n"
        f"worker_path={worker_path}\n"
        f"cwd={os.getcwd()}\n"
        f"timeout_sec={timeout_sec}\n"
        f"payload_summary={_joi_debug_payload_summary(payload)}"
    )

    try:
        completed = subprocess.run(
            [worker_python, worker_path],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
            env=env,
        )
    except Exception as exc:
        _joi_debug_exc("one-shot local worker subprocess.run failed", exc)
        raise LocalLLMError(
            f"local worker subprocess.run failed: {type(exc).__name__}: {exc}",
            error_type=classify_error_text(str(exc)),
        ) from exc

    _joi_debug_log(
        "one-shot local worker finished\n"
        f"returncode={completed.returncode}\n"
        f"stdout_head={(completed.stdout or '')[:2000]}\n"
        f"stdout_tail={(completed.stdout or '')[-2000:]}\n"
        f"stderr_head={(completed.stderr or '')[:2000]}\n"
        f"stderr_tail={(completed.stderr or '')[-4000:]}"
    )

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise LocalLLMError(
            f"local worker failed with exit code {completed.returncode}: {detail}",
            error_type=classify_error_text(detail),
            details={
                "returncode": completed.returncode,
                "stdout_tail": (completed.stdout or "")[-4000:],
                "stderr_tail": (completed.stderr or "")[-4000:],
            },
        )
    try:
        worker_result = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise LocalLLMError(
            f"local worker returned non-JSON output: {(completed.stdout or '')[:1000]}; "
            f"stderr_tail={(completed.stderr or '')[-4000:]}",
            error_type="invalid_json",
            details={
                "stdout_tail": (completed.stdout or "")[-4000:],
                "stderr_tail": (completed.stderr or "")[-4000:],
            },
        ) from exc
    if not worker_result.get("ok", True):
        error_text = str(worker_result.get("error", "local worker failed"))
        raise LocalLLMError(
            error_text,
            error_type=str(worker_result.get("error_type") or classify_error_text(error_text)),
            details=worker_result,
        )
    response = {
        "content": worker_result.get("content", ""),
        "prompt_tokens": int(worker_result.get("prompt_tokens", 0)),
        "completion_tokens": int(worker_result.get("completion_tokens", 0)),
        "total_tokens": int(worker_result.get("prompt_tokens", 0)) + int(worker_result.get("completion_tokens", 0)),
        "raw": worker_result,
    }
    for key in (
        "peak_vram_bytes",
        "peak_vram_gb",
        "load_sec",
        "load_peak_vram_bytes",
        "load_peak_vram_gb",
        "prompt_prep_sec",
        "generate_sec",
        "decode_sec",
        "total_worker_sec",
        "worker_pid",
    ):
        if key in worker_result:
            response[key] = worker_result.get(key)
    return response

def _call_worker_persistent(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_sec: int,
    extra_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    del temperature
    payload = _build_worker_payload(
        system,
        user,
        model=model,
        max_tokens=max_tokens,
        extra_payload=extra_payload,
    )
    worker_python = DEFAULT_WORKER_PYTHON
    worker_path = _env("JOI_V15_PERSISTENT_WORKER_PATH", "JOI_V14_PERSISTENT_WORKER_PATH", DEFAULT_PERSISTENT_WORKER)
    process = _ensure_persistent_worker(worker_python, worker_path, payload)
    if process.stdin is None:
        raise LocalLLMError("persistent worker stdin is unavailable", error_type="worker_crash")
    try:
        request_line = json.dumps(payload, ensure_ascii=False)
        _joi_debug_log(
            "SEND persistent worker request\n"
            f"pid={getattr(process, 'pid', None)}\n"
            f"request_chars={len(request_line)}\n"
            f"payload_summary={_joi_debug_payload_summary(payload)}"
        )
        process.stdin.write(request_line + "\n")
        process.stdin.flush()
    except BrokenPipeError as exc:
        stderr_tail = _joi_persistent_stderr_tail()
        _joi_debug_exc("persistent worker stdin pipe broke", exc)
        _close_persistent_worker()
        raise LocalLLMError(
            f"persistent worker stdin pipe broke; stderr_tail={stderr_tail[-4000:]}",
            error_type="worker_crash",
            details={"stderr_tail": stderr_tail[-4000:]},
        ) from exc
    worker_result = _read_persistent_worker_response(process, timeout_sec)
    response = {
        "content": worker_result.get("content", ""),
        "prompt_tokens": int(worker_result.get("prompt_tokens", 0)),
        "completion_tokens": int(worker_result.get("completion_tokens", 0)),
        "total_tokens": int(worker_result.get("prompt_tokens", 0)) + int(worker_result.get("completion_tokens", 0)),
        "raw": worker_result,
    }
    for key in (
        "peak_vram_bytes",
        "peak_vram_gb",
        "load_sec",
        "load_peak_vram_bytes",
        "load_peak_vram_gb",
        "prompt_prep_sec",
        "generate_sec",
        "decode_sec",
        "total_worker_sec",
        "worker_pid",
    ):
        if key in worker_result:
            response[key] = worker_result.get(key)
    return response


def call(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    mode: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    timeout_sec: int = 1800,
    retries: int = 2,
    backoff_sec: float = 2.0,
    seed: int | None = None,
    log_path: str | Path | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_mode = (mode or DEFAULT_MODE).strip().lower()
    effective_model = str(model).strip() if model else _env("JOI_V15_MODEL", "JOI_V14_MODEL", DEFAULT_MODEL)
    effective_endpoint = endpoint or DEFAULT_ENDPOINT
    last_error: Exception | None = None
    worker_payload_preview: dict[str, Any] | None = None
    use_persistent_worker = effective_mode == "worker" and _payload_use_persistent_worker(extra_payload)
    if effective_mode == "worker":
        worker_payload_preview = _build_worker_payload(
            system,
            user,
            model=effective_model,
            max_tokens=max_tokens,
            extra_payload=extra_payload,
        )
    request_record = {
        "mode": effective_mode,
        "model": effective_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": seed,
        "system": system,
        "user": user,
        "endpoint": effective_endpoint if effective_mode != "worker" else None,
        "worker_path": (
            _env("JOI_V15_PERSISTENT_WORKER_PATH", "JOI_V14_PERSISTENT_WORKER_PATH", DEFAULT_PERSISTENT_WORKER)
            if effective_mode == "worker" and use_persistent_worker
            else _env("JOI_V15_WORKER_PATH", "JOI_V14_WORKER_PATH", DEFAULT_WORKER) if effective_mode == "worker" else None
        ),
        "worker_python": DEFAULT_WORKER_PYTHON if effective_mode == "worker" else None,
        "persistent_worker": use_persistent_worker if effective_mode == "worker" else False,
        "resolved_local_model_name": (
            worker_payload_preview.get("local_model_name") if worker_payload_preview is not None else None
        ),
        "local_device": worker_payload_preview.get("local_device") if worker_payload_preview is not None else None,
        "local_dtype": worker_payload_preview.get("local_dtype") if worker_payload_preview is not None else None,
        "local_files_only": (
            worker_payload_preview.get("local_files_only") if worker_payload_preview is not None else None
        ),
        "local_trust_remote_code": (
            worker_payload_preview.get("local_trust_remote_code") if worker_payload_preview is not None else None
        ),
        "local_load_in_4bit": (
            worker_payload_preview.get("local_load_in_4bit") if worker_payload_preview is not None else None
        ),
        "local_hf_modules_cache": (
            worker_payload_preview.get("local_hf_modules_cache") if worker_payload_preview is not None else None
        ),
        "local_attn_implementation": (
            worker_payload_preview.get("local_attn_implementation") if worker_payload_preview is not None else None
        ),
        "worker_runtime": describe_worker_runtime() if effective_mode == "worker" else None,
    }
    for attempt in range(retries + 1):
        started_at = time.time()
        try:
            if effective_mode == "worker":
                if use_persistent_worker:
                    response = _call_worker_persistent(
                        system,
                        user,
                        model=effective_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_sec=timeout_sec,
                        extra_payload=extra_payload,
                    )
                else:
                    response = _call_worker(
                        system,
                        user,
                        model=effective_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_sec=timeout_sec,
                        extra_payload=extra_payload,
                    )
            elif effective_mode in {"openai", "openai_compatible", "http"}:
                response = _call_openai_compatible(
                    system,
                    user,
                    endpoint=effective_endpoint,
                    model=effective_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_sec=timeout_sec,
                    extra_payload=extra_payload,
                )
            elif effective_mode == "mock":
                response = {
                    "content": os.getenv(
                        "JOI_V15_MOCK_RESPONSE",
                        os.getenv(
                            "JOI_V14_MOCK_RESPONSE",
                            '{"name":"MockCandidate","cron":"","period":-1,"code":""}',
                        ),
                    ),
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "peak_vram_gb": 0.0,
                    "raw": {"mock": True},
                }
            else:
                raise LocalLLMError(
                    f"Unsupported JOI_V15_LLM_MODE: {effective_mode}",
                    error_type="incompatible_runtime",
                )
            response["latency_sec"] = round(time.time() - started_at, 4)
            response["attempt"] = attempt + 1
            if log_path is not None:
                dump_json(log_path, {"request": request_record, "response": response})
            return response
        except (LocalLLMError, urllib.error.URLError, urllib.error.HTTPError, subprocess.SubprocessError) as exc:
            last_error = exc
            _joi_debug_exc(
                f"local_llm_client.call attempt failed attempt={attempt + 1}/{retries + 1} mode={effective_mode}",
                exc,
            )
            if attempt >= retries:
                break
            time.sleep(backoff_sec * (attempt + 1))
    if log_path is not None:
        payload = {"request": request_record, "error": str(last_error)}
        if isinstance(last_error, LocalLLMError):
            payload["error_type"] = last_error.error_type
            if last_error.details:
                payload["error_details"] = last_error.details
        dump_json(log_path, payload)
    if isinstance(last_error, LocalLLMError):
        raise last_error
    raise LocalLLMError(str(last_error) if last_error else "local llm call failed")
