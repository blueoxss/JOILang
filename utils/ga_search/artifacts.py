#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: Any, default: str = "run") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text).strip("_")
    return text or default


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def default_run_dir(out_root: str | Path, model_package_id: str, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(out_root) / slugify(model_package_id, "model_package") / stamp


def build_base_candidate(search_mode: str, advisor_mode: str) -> dict[str, Any]:
    return {
        "candidate_id": "candidate_000_base_prompt",
        "source": "base_prompt",
        "search_mode": search_mode,
        "base_prompt_ref": "rendered_base_prompt.md",
        "patch_refs": [],
        "rendered_candidate_prompt_path": None,
        "blocks": None,
        "metadata": {
            "advisor_mode": advisor_mode,
            "mutation_intent": "baseline",
            "evidence_rows": [],
        },
    }


def write_candidate_artifacts(
    run_dir: str | Path,
    *,
    search_mode: str,
    advisor_mode: str,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir)
    candidates_dir = root / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    records = candidates or [build_base_candidate(search_mode, advisor_mode)]
    manifest_records = []
    for index, record in enumerate(records):
        candidate = dict(record)
        candidate.setdefault("candidate_id", f"candidate_{index:03d}")
        candidate.setdefault("source", "advisor_patch" if advisor_mode != "none" else "base_prompt")
        candidate.setdefault("search_mode", search_mode)
        candidate.setdefault("base_prompt_ref", "rendered_base_prompt.md")
        candidate.setdefault("patch_refs", [])
        candidate.setdefault("rendered_candidate_prompt_path", None)
        candidate.setdefault("blocks", None)
        candidate.setdefault("metadata", {})
        path = candidates_dir / f"candidate_{index:03d}.json"
        write_json(path, candidate)
        manifest_item = {
            "candidate_id": candidate["candidate_id"],
            "path": str(path),
            "source": candidate.get("source"),
            "patch_refs": candidate.get("patch_refs", []),
            "mutation_intent": candidate.get("metadata", {}).get("mutation_intent", ""),
        }
        manifest_records.append(manifest_item)
    manifest = {
        "created_at": utc_now(),
        "candidate_count": len(manifest_records),
        "search_mode": search_mode,
        "advisor_mode": advisor_mode,
        "candidates": manifest_records,
    }
    write_json(candidates_dir / "candidates_manifest.json", manifest)
    return manifest


def save_search_artifacts(
    run_dir: str | Path,
    *,
    rendered_package: dict[str, Any],
    search_input: dict[str, Any],
    search_mode: str,
    advisor_mode: str,
    decomposed_blocks: list[dict[str, Any]] | None = None,
    advisor_summary: dict[str, Any] | None = None,
    candidate_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "rendered_base_prompt.md", str(rendered_package.get("system_prompt") or ""))
    render_metadata = {
        "created_at": utc_now(),
        "model_package": rendered_package.get("model_package"),
        "model_package_id": rendered_package.get("model_package_id"),
        "model_config_summary": rendered_package.get("model_config_summary", {}),
        "model_render_mode": rendered_package.get("model_render_mode"),
        "prompt_render": rendered_package.get("prompt_render", {}),
        "merged_prompt_path": rendered_package.get("merged_prompt_path"),
        "messages_count": len(rendered_package.get("messages") or []),
        "metadata": rendered_package.get("metadata", {}),
    }
    write_json(root / "render_metadata.json", render_metadata)
    if decomposed_blocks is not None:
        write_json(root / "decomposed_blocks.json", decomposed_blocks)
    write_json(root / "search_input.json", search_input)
    manifest = {
        "created_at": utc_now(),
        "artifact_schema": "ga_search.foundation.v1",
        "run_dir": str(root),
        "search_mode": search_mode,
        "advisor_mode": advisor_mode,
        "model_render_mode": rendered_package.get("model_render_mode"),
        "official_score_policy": {
            "primary_metric": "strict_det",
            "cloud_is_auxiliary": True,
        },
        "artifacts": {
            "rendered_base_prompt": str(root / "rendered_base_prompt.md"),
            "render_metadata": str(root / "render_metadata.json"),
            "search_input": str(root / "search_input.json"),
            "decomposed_blocks": str(root / "decomposed_blocks.json") if decomposed_blocks is not None else "",
            "advisor_dir": str(root / "advisor") if advisor_summary else "",
            "candidates_manifest": str(root / "candidates" / "candidates_manifest.json") if candidate_manifest else "",
        },
        "advisor_summary": advisor_summary or {},
        "candidate_summary": candidate_manifest or {},
    }
    write_json(root / "manifest.json", manifest)
    return manifest
