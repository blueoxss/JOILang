#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


MODEL_SPECS: dict[str, dict[str, str]] = {
    "phi35_mini": {
        "label": "Phi-3.5-mini-instruct",
        "hf_id": "microsoft/Phi-3.5-mini-instruct",
        "local_dir": "phi35_mini",
    },
    "qwen25_coder_7b": {
        "label": "Qwen2.5-Coder-7B-Instruct",
        "hf_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "local_dir": "qwen25_coder_7b",
    },
    "llama31_8b": {
        "label": "Llama-3.1-8B-Instruct",
        "hf_id": "meta-llama/Llama-3.1-8B-Instruct",
        "local_dir": "llama31_8b",
    },
    "gemma2_9b_it": {
        "label": "Gemma-2-9B-it",
        "hf_id": "google/gemma-2-9b-it",
        "local_dir": "gemma2_9b_it",
    },
    "qwen25_coder_14b": {
        "label": "Qwen2.5-Coder-14B-Instruct",
        "hf_id": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "local_dir": "qwen25_coder_14b",
    },
}

_HF_TO_KEY = {spec["hf_id"].lower(): key for key, spec in MODEL_SPECS.items()}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_local_model_base_dir() -> Path:
    raw = (
        os.environ.get("JOI_GA_LOCAL_MODEL_BASE_DIR")
        or os.environ.get("JOI_V15_LOCAL_MODEL_BASE_DIR")
        or os.environ.get("JOI_V14_LOCAL_MODEL_BASE_DIR")
        or ""
    )
    if raw:
        return Path(raw).expanduser()
    return repo_root().parent / "local_models"


def canonical_model_id(model_key_or_id: str) -> str:
    token = str(model_key_or_id or "").strip()
    if not token:
        return token
    spec = MODEL_SPECS.get(token)
    if spec:
        return spec["hf_id"]
    return token


def model_key_from_id(model_key_or_id: str) -> str:
    token = str(model_key_or_id or "").strip()
    if not token:
        return token
    if token in MODEL_SPECS:
        return token
    return _HF_TO_KEY.get(token.lower(), token)


def resolve_local_model_name(
    model_key_or_id: str,
    *,
    explicit_model_name: str | None = None,
    base_dir: str | Path | None = None,
) -> str:
    explicit = str(explicit_model_name or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        return str(p.resolve()) if p.exists() else explicit

    key = model_key_from_id(model_key_or_id)
    spec = MODEL_SPECS.get(key)

    base = Path(base_dir).expanduser() if base_dir else default_local_model_base_dir()
    if spec:
        candidate = base / spec["local_dir"]
        if candidate.exists():
            return str(candidate.resolve())

    canonical = canonical_model_id(model_key_or_id)
    return canonical or str(model_key_or_id or "")


def canonical_worker_path() -> str:
    return str((repo_root() / "utils" / "ga_search" / "local_worker.py").resolve())


def build_worker_extra_payload(
    model_key_or_id: str,
    *,
    base_dir: str | Path | None = None,
    worker_python: str = "",
    local_device: str = "cuda:0",
    local_dtype: str = "bf16",
    local_files_only: bool = True,
    local_trust_remote_code: bool = True,
    local_load_in_4bit: bool = False,
    local_max_new_tokens: int = 512,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(extra or {})
    payload.setdefault("local_worker", canonical_worker_path())
    if worker_python:
        payload.setdefault("worker_python", worker_python)
    payload.setdefault(
        "local_model_name",
        resolve_local_model_name(model_key_or_id, base_dir=base_dir),
    )
    payload.setdefault("local_device", local_device)
    payload.setdefault("local_dtype", local_dtype)
    payload.setdefault("local_files_only", local_files_only)
    payload.setdefault("local_trust_remote_code", local_trust_remote_code)
    payload.setdefault("local_load_in_4bit", local_load_in_4bit)
    payload.setdefault("local_max_new_tokens", int(local_max_new_tokens))
    return payload
