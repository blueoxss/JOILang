#!/usr/bin/env python3
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


LEGACY_VERSION_TOKEN = "version0_15_update" + "20260413"
FORBIDDEN_LEGACY_TOKENS = {
    "gpt_mg." + LEGACY_VERSION_TOKEN,
    LEGACY_VERSION_TOKEN,
}


@dataclass
class ModelPackageSpec:
    model_id: str
    package_path: str
    package_module: str
    package_family: str
    loader_path: str
    loader_module: ModuleType
    loader_function: str
    model_config: dict[str, Any]
    prompt_render: dict[str, Any]
    blocks_dir: str
    genomes_dir: str
    generated_blocks_dir: str
    generated_genomes_dir: str
    artifact_default_dir: str
    render_mode: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "package_path": self.package_path,
            "package_module": self.package_module,
            "package_family": self.package_family,
            "loader_path": self.loader_path,
            "loader_module": getattr(self.loader_module, "__name__", ""),
            "loader_function": self.loader_function,
            "model_config": self.model_config,
            "prompt_render": self.prompt_render,
            "blocks_dir": self.blocks_dir,
            "genomes_dir": self.genomes_dir,
            "generated_blocks_dir": self.generated_blocks_dir,
            "generated_genomes_dir": self.generated_genomes_dir,
            "artifact_default_dir": self.artifact_default_dir,
            "render_mode": self.render_mode,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _guard_legacy_reference(value: str) -> None:
    normalized = str(value)
    if any(token in normalized for token in FORBIDDEN_LEGACY_TOKENS):
        raise ValueError(
            "the legacy v15 update folder is backup/reference only and cannot be used as a canonical GA runtime."
        )


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def normalize_prompt_render(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("prompt_render") if isinstance(config, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    mode = str(raw.get("mode") or "monolith").strip().lower()
    if mode not in {"monolith", "blocks", "auto"}:
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


def _ensure_import_roots(package_path: Path) -> None:
    root = repo_root()
    for candidate in (root, package_path.parent, package_path):
        text = str(candidate)
        if text not in sys.path:
            sys.path.insert(0, text)


def _load_loader_from_path(loader_path: Path, module_hint: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_hint, loader_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import config loader: {loader_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package_family_from_id(model_id: str) -> str:
    token = str(model_id).replace("/", ".").split(".")
    return token[0] if token and token[0] else "custom"


def _path_model_id(package_path: Path) -> str:
    root = repo_root()
    try:
        rel = package_path.resolve().relative_to(root.resolve())
        return ".".join(rel.parts)
    except ValueError:
        return package_path.name


def resolve_model_package(
    *,
    model: str | None = None,
    model_package: str | Path | None = None,
    loader_function: str | None = None,
) -> ModelPackageSpec:
    if not model and not model_package:
        raise ValueError("either --model or --model-package is required")
    if model and model_package:
        raise ValueError("use only one of --model or --model-package")

    if model_package:
        _guard_legacy_reference(str(model_package))
        package_path = Path(model_package)
        if not package_path.is_absolute():
            package_path = repo_root() / package_path
        package_path = package_path.resolve()
        if not package_path.exists() or not package_path.is_dir():
            raise FileNotFoundError(f"model package directory not found: {package_path}")
        _ensure_import_roots(package_path)
        model_config = _load_json_if_exists(package_path / "model_config.json")
        prompt_render = normalize_prompt_render(model_config)
        loader_path = (package_path / str(prompt_render.get("loader") or "config_loader.py")).resolve()
        if not loader_path.exists():
            raise FileNotFoundError(f"config_loader.py not found: {loader_path}")
        module_name = f"ga_search_path_loader_{abs(hash(str(loader_path))) & 0xfffffff:x}"
        loader_module = _load_loader_from_path(loader_path, module_name)
        package_module = ""
        model_id = _path_model_id(package_path)
    else:
        assert model is not None
        _guard_legacy_reference(model)
        _ensure_import_roots(repo_root())
        module_name = f"{model}.config_loader"
        loader_module = importlib.import_module(module_name)
        loader_file = getattr(loader_module, "__file__", None)
        if not loader_file:
            raise ImportError(f"could not resolve loader file for {module_name}")
        loader_path = Path(loader_file).resolve()
        package_path = loader_path.parent
        model_config = _load_json_if_exists(package_path / "model_config.json")
        prompt_render = normalize_prompt_render(model_config)
        package_module = str(model)
        model_id = str(model)

    function_name = loader_function or str(prompt_render.get("loader_function") or "load_version_config")
    if not hasattr(loader_module, function_name):
        raise AttributeError(f"loader function '{function_name}' not found in {loader_path}")

    blocks_dir = package_path / str(prompt_render.get("blocks_dir") or "blocks")
    genomes_dir = package_path / str(prompt_render.get("genomes_dir") or "genomes")
    artifact_default_dir = repo_root() / "artifacts" / "ga_search" / model_id.replace(".", "__").replace("/", "__")
    return ModelPackageSpec(
        model_id=model_id,
        package_path=str(package_path),
        package_module=package_module,
        package_family=_package_family_from_id(model_id),
        loader_path=str(loader_path),
        loader_module=loader_module,
        loader_function=function_name,
        model_config=model_config,
        prompt_render=prompt_render,
        blocks_dir=str(blocks_dir),
        genomes_dir=str(genomes_dir),
        generated_blocks_dir=str(blocks_dir / "generated"),
        generated_genomes_dir=str(genomes_dir / "generated"),
        artifact_default_dir=str(artifact_default_dir),
        render_mode=str(prompt_render.get("mode") or "monolith"),
    )


def find_model_spec(model: str | None = None, model_package: str | Path | None = None) -> ModelPackageSpec:
    return resolve_model_package(model=model, model_package=model_package)
