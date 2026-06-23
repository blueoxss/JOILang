#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

try:
    from .model_resolver import (
        ModelPackageSpec,
        normalize_prompt_render,
        resolve_model_package,
    )
except ImportError:
    from model_resolver import (  # type: ignore
        ModelPackageSpec,
        normalize_prompt_render,
        resolve_model_package,
    )


def load_model_config(model_package: str | Path) -> dict[str, Any]:
    spec = resolve_model_package(model_package=model_package)
    return spec.model_config


def load_config_loader(model_package: str | Path, loader_file: str = "config_loader.py") -> ModuleType:
    spec = resolve_model_package(model_package=model_package)
    if Path(spec.loader_path).name != loader_file:
        spec = resolve_model_package(model_package=model_package)
    return spec.loader_module


def load_model_package(model_package: str | Path) -> dict[str, Any]:
    spec = resolve_model_package(model_package=model_package)
    return model_spec_to_legacy_dict(spec)


def load_model_package_from_model(model: str) -> dict[str, Any]:
    spec = resolve_model_package(model=model)
    return model_spec_to_legacy_dict(spec)


def model_spec_to_legacy_dict(spec: ModelPackageSpec) -> dict[str, Any]:
    return {
        "model_package": Path(spec.package_path),
        "model_package_id": spec.model_id.replace(".", "__").replace("/", "__"),
        "model_config": spec.model_config,
        "prompt_render": spec.prompt_render,
        "loader_module": spec.loader_module,
        "loader_function": spec.loader_function,
        "model_spec": spec,
    }
