#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .model_package_loader import load_model_package
except ImportError:
    from model_package_loader import load_model_package  # type: ignore


def extract_messages(loader_result: Any) -> list[dict[str, Any]]:
    if isinstance(loader_result, dict):
        messages = loader_result.get("messages")
        if isinstance(messages, list):
            return [m for m in messages if isinstance(m, dict)]
        model_input = loader_result.get("model_input")
        if isinstance(model_input, dict) and isinstance(model_input.get("messages"), list):
            return [m for m in model_input["messages"] if isinstance(m, dict)]
    if isinstance(loader_result, tuple) and len(loader_result) >= 2:
        model_input = loader_result[1]
        if isinstance(model_input, dict) and isinstance(model_input.get("messages"), list):
            return [m for m in model_input["messages"] if isinstance(m, dict)]
    return []


def extract_system_prompt(loader_result: Any) -> str:
    if isinstance(loader_result, dict) and isinstance(loader_result.get("system_prompt"), str):
        return loader_result["system_prompt"]
    for message in extract_messages(loader_result):
        if message.get("role") == "system" and message.get("content"):
            return str(message["content"])
    return ""


def _extract_config(loader_result: Any) -> dict[str, Any]:
    if isinstance(loader_result, dict) and isinstance(loader_result.get("config"), dict):
        return loader_result["config"]
    if isinstance(loader_result, tuple) and loader_result and isinstance(loader_result[0], dict):
        return loader_result[0]
    return {}


def _latest_merged_prompt_path(model_package: Path) -> str:
    candidates = sorted(model_package.glob("merged_system_prompt_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0]) if candidates else ""


def render_model_package(
    model_package: str | Path,
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package_info = load_model_package(model_package)
    package_path = Path(package_info["model_package"])
    loader_module = package_info["loader_module"]

    if hasattr(loader_module, "render_prompt_package"):
        loader_result = loader_module.render_prompt_package(
            user_input,
            connected_devices=connected_devices or {},
            other_params=other_params or {},
            base_path=str(package_path),
        )
    else:
        loader_fn = getattr(loader_module, package_info["loader_function"])
        loader_result = loader_fn(
            user_input,
            connected_devices=connected_devices or {},
            other_params=other_params or {},
            base_path=str(package_path),
        )

    system_prompt = extract_system_prompt(loader_result)
    messages = extract_messages(loader_result)
    config = _extract_config(loader_result) or package_info["model_config"]
    merged_prompt_path = ""
    blocks = None
    metadata: dict[str, Any] = {}
    if isinstance(loader_result, dict):
        merged_prompt_path = str(loader_result.get("merged_prompt_path") or "")
        blocks = loader_result.get("blocks")
        metadata = loader_result.get("metadata") if isinstance(loader_result.get("metadata"), dict) else {}
    if not merged_prompt_path:
        merged_prompt_path = _latest_merged_prompt_path(package_path)
    if not system_prompt:
        raise ValueError(f"could not extract a system prompt from model package: {package_path}")
    return {
        "model_package": str(package_path),
        "model_package_id": package_info["model_package_id"],
        "model_config_summary": {
            "model_name": config.get("model_name"),
            "model_version": config.get("model_version"),
            "device_name": config.get("device_name"),
        },
        "prompt_render": package_info["prompt_render"],
        "model_render_mode": package_info["prompt_render"].get("mode", "monolith"),
        "system_prompt": system_prompt,
        "messages": messages,
        "merged_prompt_path": merged_prompt_path,
        "blocks": blocks,
        "metadata": metadata,
    }
