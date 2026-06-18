#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def build_monolith_search_input(rendered_package: dict[str, Any]) -> dict[str, Any]:
    prompt = str(rendered_package.get("system_prompt") or "")
    return {
        "search_mode": "monolith",
        "model_render_mode": rendered_package.get("model_render_mode", "monolith"),
        "base_prompt": prompt,
        "prompt_length_chars": len(prompt),
        "prompt_token_estimate": max(1, int(len(prompt.split()) * 1.35)) if prompt else 0,
        "source_model_package": rendered_package.get("model_package"),
        "source_model_package_id": rendered_package.get("model_package_id"),
        "render_metadata": rendered_package.get("metadata", {}),
        "prompt_render": rendered_package.get("prompt_render", {}),
    }
