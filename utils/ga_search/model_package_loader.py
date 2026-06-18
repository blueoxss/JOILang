#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


VALID_RENDER_MODES = {"monolith", "blocks", "auto"}


def repo_root_from_model_package(model_package: Path) -> Path:
    resolved = model_package.resolve()
    for parent in [resolved, *resolved.parents]:
        if (parent / ".git").exists() or (parent / "gpt_mg").exists():
            return parent
    return resolved.parents[1]


def load_model_config(model_package: str | Path) -> dict[str, Any]:
    package = Path(model_package).resolve()
    config_path = package / "model_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"model_config.json not found under model package: {package}")
    with config_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"model_config.json must contain a JSON object: {config_path}")
    return data


def normalize_prompt_render(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("prompt_render") if isinstance(config, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    mode = str(raw.get("mode") or "monolith").strip().lower()
    if mode not in VALID_RENDER_MODES:
        mode = "monolith"
    normalized = {
        "mode": mode,
        "loader": str(raw.get("loader") or "config_loader.py"),
        "loader_function": str(raw.get("loader_function") or "load_version_config"),
        "merged_prompt_output": str(raw.get("merged_prompt_output") or "merged_system_prompt.md"),
    }
    for key, value in raw.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def _ensure_import_paths(model_package: Path) -> None:
    repo_root = repo_root_from_model_package(model_package)
    candidates = [repo_root, model_package.parent, model_package]
    for path in candidates:
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def load_config_loader(model_package: str | Path, loader_file: str = "config_loader.py") -> ModuleType:
    package = Path(model_package).resolve()
    loader_path = package / loader_file
    if not loader_path.exists():
        raise FileNotFoundError(f"config loader not found: {loader_path}")
    _ensure_import_paths(package)
    module_name = f"ga_search_loader_{package.name}_{abs(hash(str(loader_path))) & 0xfffffff:x}"
    spec = importlib.util.spec_from_file_location(module_name, loader_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import config loader: {loader_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model_package(model_package: str | Path) -> dict[str, Any]:
    package = Path(model_package).resolve()
    if not package.exists() or not package.is_dir():
        raise FileNotFoundError(f"model package directory not found: {package}")
    config = load_model_config(package)
    prompt_render = normalize_prompt_render(config)
    loader_module = load_config_loader(package, prompt_render["loader"])
    loader_function = prompt_render["loader_function"]
    if not hasattr(loader_module, loader_function):
        raise AttributeError(
            f"loader function '{loader_function}' not found in {package / prompt_render['loader']}"
        )
    return {
        "model_package": package,
        "model_package_id": "__".join(package.parts[-2:]),
        "model_config": config,
        "prompt_render": prompt_render,
        "loader_module": loader_module,
        "loader_function": loader_function,
    }
