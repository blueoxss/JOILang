#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from .prompt_decomposer import decompose_prompt_to_blocks
except ImportError:
    from prompt_decomposer import decompose_prompt_to_blocks  # type: ignore


def _normalize_provided_blocks(blocks: Any) -> list[dict[str, Any]]:
    if isinstance(blocks, dict):
        items = blocks.get("blocks") if isinstance(blocks.get("blocks"), list) else []
    elif isinstance(blocks, list):
        items = blocks
    else:
        items = []
    normalized = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            block = dict(item)
        else:
            block = {"text": str(item)}
        block.setdefault("block_id", f"P{index:03d}")
        block.setdefault("family", "provided")
        block.setdefault("title", str(block.get("block_id")))
        block.setdefault("order", index)
        block.setdefault("source", "provided_blocks")
        normalized.append(block)
    return normalized


def build_blocks_search_input(rendered_package: dict[str, Any]) -> dict[str, Any]:
    provided = _normalize_provided_blocks(rendered_package.get("blocks"))
    if provided:
        blocks = provided
        source = "provided_blocks"
    else:
        blocks = decompose_prompt_to_blocks(str(rendered_package.get("prompt_text") or rendered_package.get("system_prompt") or ""))
        source = "decomposed_from_monolith"
    family_distribution = Counter(str(block.get("family") or "misc") for block in blocks)
    return {
        "search_mode": "blocks",
        "model_render_mode": rendered_package.get("model_render_mode", "monolith"),
        "blocks": blocks,
        "block_count": len(blocks),
        "family_distribution": dict(sorted(family_distribution.items())),
        "source": source,
        "source_model_package": rendered_package.get("model_package"),
        "source_model_package_id": rendered_package.get("model_package_id"),
        "render_metadata": rendered_package.get("metadata", {}),
        "prompt_render": rendered_package.get("prompt_render", {}),
        "prompt_text_preserved": "".join(str(block.get("text") or "") for block in blocks)
        == str(rendered_package.get("prompt_text") or rendered_package.get("system_prompt") or ""),
    }
