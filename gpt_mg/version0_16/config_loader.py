#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from .tools.block_space_ops import (
        load_genome,
        load_manifest,
        make_default_genome,
        render_from_manifest,
    )
except ImportError:
    from tools.block_space_ops import (  # type: ignore
        load_genome,
        load_manifest,
        make_default_genome,
        render_from_manifest,
    )


def _resolve_base_path(base_path: str = ".") -> Path:
    raw = Path(str(base_path))
    if raw.is_absolute():
        return raw
    if raw.exists():
        return raw.resolve()
    return Path(__file__).resolve().parent


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _default_local_python() -> str:
    return (
        os.environ.get("JOI_PY", "").strip()
        or os.environ.get("JOI_V16_PYTHON", "").strip()
        or sys.executable
        or "python"
    )


def _default_local_worker(base_path: Path) -> str:
    repo_root = base_path.parents[1]
    return str((repo_root / "utils" / "ga_search" / "local_worker.py").resolve())


def _prompt_render_config(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("prompt_render") if isinstance(config.get("prompt_render"), dict) else {}
    return {
        "mode": str(raw.get("mode") or "blocks"),
        "loader": str(raw.get("loader") or "config_loader.py"),
        "loader_function": str(raw.get("loader_function") or "load_version_config"),
        "source_prompt": str(raw.get("source_prompt") or "prompts/source/merged_system_prompt_260413.md"),
        "default_manifest": str(raw.get("default_manifest") or "registries/generation_block_space_g000.json"),
        "default_genome": str(raw.get("default_genome") or "genomes/base_genome_g000.json"),
        "supports_dynamic_block_space": True,
        **{k: v for k, v in raw.items() if k not in {"mode", "loader", "loader_function"}},
    }


def _select_manifest_and_genome(base_path: Path, other_params: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    other_params = other_params if isinstance(other_params, dict) else {}
    generation = other_params.get("generation")
    if generation is not None:
        try:
            generation = int(generation)
        except Exception:
            generation = None
    block_space_id = other_params.get("block_space_id")
    genome_path = other_params.get("genome_json") or other_params.get("genome_path")
    genome_payload = other_params.get("genome") if isinstance(other_params.get("genome"), dict) else None
    manifest = load_manifest(base_path, generation=generation, block_space_id=block_space_id)
    if genome_payload:
        genome = copy.deepcopy(genome_payload)
    elif genome_path:
        genome = load_genome(base_path, genome_path)
    else:
        default = base_path / "genomes" / f"base_genome_g{int(manifest.get('generation', 0)):03d}.json"
        genome = load_genome(base_path, default) if default.exists() else make_default_genome(manifest)
    return manifest, genome


def render_prompt_package(
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
    base_path: str = ".",
) -> dict[str, Any]:
    root = _resolve_base_path(base_path)
    config = _read_json(root / "model_config.json")
    prompt_render = _prompt_render_config(config)
    manifest, genome = _select_manifest_and_genome(root, other_params)
    rendered = render_from_manifest(
        base_path=root,
        manifest=manifest,
        genome=genome,
        user_input=str(user_input or ""),
        connected_devices=connected_devices or {},
        other_params=other_params or {},
    )

    model_input = copy.deepcopy(config.get("model_input", {}))
    model_input["local_python"] = _default_local_python()
    model_input["local_worker"] = _default_local_worker(root)
    model_input["messages"] = rendered["messages"]
    rendered["mode"] = prompt_render["mode"]
    rendered["prompt_render"] = prompt_render
    rendered["merged_prompt_path"] = str(root / prompt_render["source_prompt"])
    rendered["source_prompt_path"] = str(root / prompt_render["source_prompt"])
    rendered["metadata"].update(
        {
            "model_name": config.get("model_name"),
            "model_version": config.get("model_version"),
            "base_path": str(root),
            "prompt_render": prompt_render,
            "genome_id": rendered["genome"].get("genome_id"),
            "gpt_mg.version0_15_update20260413.scripts_runtime_dependency": False,
        }
    )
    rendered["config"] = {**config, "prompt_render": prompt_render, "resolved_block_manifest": manifest}
    rendered["model_input"] = model_input
    return rendered


def load_version_config(
    user_input: str,
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
    base_path: str = ".",
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = render_prompt_package(
        user_input,
        connected_devices=connected_devices,
        other_params=other_params,
        base_path=base_path,
    )
    return package["config"], package["model_input"]
