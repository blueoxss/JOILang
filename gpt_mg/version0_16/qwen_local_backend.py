import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class _Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


class _ChatCompletionResponse:
    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int):
        self.choices = [_Choice(message=_Message(content=content))]
        self.usage = _Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


def _find_run_module():
    for module_name in ("__main__", "run", "gpt_mg.run", "ModelMagementApp.gpt_mg.run"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "client"):
            return module
    for module in sys.modules.values():
        if module is None or not hasattr(module, "client"):
            continue
        module_file = getattr(module, "__file__", "")
        if module_file and os.path.basename(module_file) == "run.py":
            return module
    return None


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _default_worker_path() -> str:
    return str(Path(__file__).with_name("qwen_local_worker.py"))


def _default_python_path() -> str:
    env_python = os.getenv("JOI_VERSION013_PYTHON", "").strip()
    if env_python:
        return env_python
    return sys.executable or "python"


def _coalesce_path(value: Any, default_value: str) -> str:
    if value is None:
        return default_value
    normalized = str(value).strip()
    if not normalized:
        return default_value
    return normalized


def _resolve_worker_path(worker_path: str) -> str:
    path = Path(worker_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return str(path.resolve())


class _Version013LocalChatCompletion:
    def __init__(self, original_create):
        self._original_create = original_create

    def create(self, **kwargs):
        backend = kwargs.pop("backend", "")
        if backend != "local_qwen":
            return self._original_create(**kwargs)

        local_python = _coalesce_path(
            os.getenv("JOI_VERSION013_PYTHON") or kwargs.pop("local_python", None),
            _default_python_path(),
        )
        local_worker = _resolve_worker_path(
            _coalesce_path(
                os.getenv("JOI_VERSION013_WORKER") or kwargs.pop("local_worker", None),
                _default_worker_path(),
            )
        )
        local_timeout_sec = int(
            os.getenv(
                "JOI_VERSION013_TIMEOUT_SEC",
                str(kwargs.pop("local_timeout_sec", 1800)),
            )
        )

        payload = {
            "model": kwargs.get("model", "qwen2.5-Coder-7B-Instruct"),
            "local_model_name": kwargs.pop("local_model_name", "") or kwargs.get("model", ""),
            "messages": kwargs.get("messages", []),
            "local_device": os.getenv("JOI_VERSION013_DEVICE", kwargs.pop("local_device", "cuda:1")),
            "local_dtype": os.getenv("JOI_VERSION013_DTYPE", kwargs.pop("local_dtype", "bf16")),
            "local_max_new_tokens": int(
                os.getenv(
                    "JOI_VERSION013_MAX_NEW_TOKENS",
                    str(kwargs.pop("local_max_new_tokens", 256)),
                )
            ),
            "local_files_only": _parse_bool(
                os.getenv("JOI_VERSION013_LOCAL_FILES_ONLY", kwargs.pop("local_files_only", True)),
                True,
            ),
            "local_trust_remote_code": _parse_bool(
                os.getenv(
                    "JOI_VERSION013_TRUST_REMOTE_CODE",
                    kwargs.pop("local_trust_remote_code", False),
                ),
                False,
            ),
            "local_load_in_4bit": _parse_bool(
                os.getenv("JOI_VERSION013_LOAD_IN_4BIT", kwargs.pop("local_load_in_4bit", False)),
                False,
            ),
        }

        completed = subprocess.run(
            [local_python, local_worker],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=local_timeout_sec,
            check=False,
        )

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            detail = stderr or stdout or "No worker output."
            raise RuntimeError(f"version0_13 local_qwen backend failed: {detail}")

        try:
            worker_result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "version0_13 local_qwen backend returned non-JSON output: "
                f"{completed.stdout[:500]}"
            ) from exc

        return _ChatCompletionResponse(
            content=worker_result.get("content", ""),
            prompt_tokens=int(worker_result.get("prompt_tokens", 0)),
            completion_tokens=int(worker_result.get("completion_tokens", 0)),
        )

def ensure_version013_backend_installed():
    run_module = _find_run_module()
    if run_module is None:
        return

    client = getattr(run_module, "client", None)
    if client is None or not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        return

    completions = client.chat.completions
    completions_cls = completions.__class__
    if getattr(completions_cls, "_version013_dispatch_installed", False):
        return

    original_create = completions_cls.create

    def patched_create(self, *args, **kwargs):
        dispatcher = _Version013LocalChatCompletion(
            lambda **forwarded_kwargs: original_create(self, *args, **forwarded_kwargs)
        )
        return dispatcher.create(**kwargs)

    completions_cls.create = patched_create
    completions_cls._version013_dispatch_installed = True
