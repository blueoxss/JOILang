#!/usr/bin/env python3
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

try:
    from .model_resolver import ModelPackageSpec, resolve_model_package
except ImportError:
    from model_resolver import ModelPackageSpec, resolve_model_package  # type: ignore


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


def extract_user_prompt(loader_result: Any) -> str:
    if isinstance(loader_result, dict) and isinstance(loader_result.get("user_prompt"), str):
        return loader_result["user_prompt"]
    for message in extract_messages(loader_result):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    return ""


def _extract_model_input(loader_result: Any) -> dict[str, Any]:
    if isinstance(loader_result, dict) and isinstance(loader_result.get("model_input"), dict):
        return loader_result["model_input"]
    if isinstance(loader_result, tuple) and len(loader_result) >= 2 and isinstance(loader_result[1], dict):
        return loader_result[1]
    return {}


def _extract_config(loader_result: Any) -> dict[str, Any]:
    if isinstance(loader_result, dict) and isinstance(loader_result.get("config"), dict):
        return loader_result["config"]
    if isinstance(loader_result, tuple) and loader_result and isinstance(loader_result[0], dict):
        return loader_result[0]
    return {}


def _latest_merged_prompt_path(model_package: Path) -> str:
    candidates = sorted(model_package.glob("merged_system_prompt_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0]) if candidates else ""


def _call_loader(spec: ModelPackageSpec, user_input: str, connected_devices: dict[str, Any], other_params: dict[str, Any]) -> Any:
    module = spec.loader_module
    package_path = Path(spec.package_path)
    if hasattr(module, "render_prompt_package"):
        render_fn = getattr(module, "render_prompt_package")
        try:
            return render_fn(
                user_input,
                connected_devices=connected_devices,
                other_params=other_params,
                base_path=str(package_path),
            )
        except TypeError:
            return render_fn(user_input, connected_devices, other_params, str(package_path))

    loader_fn = getattr(module, spec.loader_function)
    signature = inspect.signature(loader_fn)
    params = list(signature.parameters)

    # gpt_mg-style: load_version_config(user_input, connected_devices, other_params, base_path)
    if len(params) <= 4:
        try:
            return loader_fn(
                user_input,
                connected_devices=connected_devices,
                other_params=other_params,
                base_path=str(package_path),
            )
        except TypeError:
            return loader_fn(user_input, connected_devices, other_params, str(package_path))

    # gpt_cap stage-style: load_version_config(sentence, services, category_tags, other_params, error_msg, base_path)
    services = other_params.get("services", "") if isinstance(other_params, dict) else ""
    category_tags = other_params.get("category_tags", "") if isinstance(other_params, dict) else ""
    error_msg = other_params.get("error_msg", "") if isinstance(other_params, dict) else ""
    try:
        return loader_fn(user_input, services, category_tags, other_params, error_msg, str(package_path))
    except TypeError:
        return loader_fn(user_input, services, category_tags, other_params, error_msg, ".")


def render_model_spec(
    spec: ModelPackageSpec,
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package_path = Path(spec.package_path)
    loader_result = _call_loader(spec, user_input, connected_devices or {}, other_params or {})

    system_prompt = extract_system_prompt(loader_result)
    user_prompt = extract_user_prompt(loader_result)
    messages = extract_messages(loader_result)
    model_input = _extract_model_input(loader_result)
    config = _extract_config(loader_result) or spec.model_config
    prompt_text = "\n\n".join(part for part in [system_prompt, user_prompt] if part)
    merged_prompt_path = ""
    blocks = None
    manifest: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    if isinstance(loader_result, dict):
        merged_prompt_path = str(loader_result.get("merged_prompt_path") or "")
        blocks = loader_result.get("blocks") or loader_result.get("blocks_metadata")
        manifest = loader_result.get("prompt_manifest") if isinstance(loader_result.get("prompt_manifest"), dict) else {}
        metadata = loader_result.get("metadata") if isinstance(loader_result.get("metadata"), dict) else {}
    if isinstance(config.get("resolved_block_manifest"), dict):
        manifest = config["resolved_block_manifest"]
    if not merged_prompt_path:
        merged_prompt_path = _latest_merged_prompt_path(package_path)
    if not prompt_text:
        raise ValueError(f"could not extract rendered prompt text from model package: {package_path}")
    return {
        "model_package": str(package_path),
        "model_package_id": spec.model_id.replace(".", "__").replace("/", "__"),
        "model_id": spec.model_id,
        "model_spec": spec.to_public_dict(),
        "model_config_summary": {
            "model_name": config.get("model_name"),
            "model_version": config.get("model_version"),
            "device_name": config.get("device_name"),
        },
        "prompt_render": spec.prompt_render,
        "model_render_mode": spec.render_mode,
        "render_mode": spec.render_mode,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_text": prompt_text,
        "messages": messages,
        "model_input": model_input,
        "merged_prompt_path": merged_prompt_path,
        "blocks": blocks,
        "blocks_metadata": blocks,
        "prompt_manifest": manifest,
        "model_config": config,
        "source_model_package": spec.package_path,
        "metadata": metadata,
    }


def render_model_package(
    model_package: str | Path,
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = resolve_model_package(model_package=model_package)
    return render_model_spec(spec, user_input, connected_devices=connected_devices, other_params=other_params)


def render_model(
    model: str,
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = resolve_model_package(model=model)
    return render_model_spec(spec, user_input, connected_devices=connected_devices, other_params=other_params)
