#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .block_space_ops import (
        apply_dynamic_patch_output,
        load_genome,
        load_manifest,
        write_json,
    )
except ImportError:
    from block_space_ops import (  # type: ignore
        apply_dynamic_patch_output,
        load_genome,
        load_manifest,
        write_json,
    )


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_patch_file(
    *,
    prompt_patches_path: str | Path,
    base_path: str | Path,
    out_dir: str | Path,
    generation: int = 0,
    genome_path: str | Path | None = None,
    create_on_unresolved: bool = True,
) -> dict[str, Any]:
    base = Path(base_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    patches_output = read_json(prompt_patches_path)
    manifest = load_manifest(base, generation=generation)
    genome = load_genome(base, genome_path or base / "genomes" / f"base_genome_g{generation:03d}.json")
    result = apply_dynamic_patch_output(
        patches_output=patches_output,
        base_path=base,
        manifest=manifest,
        genome=genome,
        create_on_unresolved=create_on_unresolved,
    )
    write_json(out / f"generation_block_space_g{generation:03d}_patched.json", result["manifest"])
    write_json(out / "patched_genome.json", result["patched_genome"])
    write_json(out / "dynamic_patch_application_report.json", {
        "prompt_patches_path": str(prompt_patches_path),
        "base_path": str(base),
        "generation": generation,
        "summary": result["summary"],
        "applications": result["applications"],
        "unresolved_patches": result["unresolved_patches"],
        "policy": {
            "target_block_id_is_fallback_only": True,
            "silent_fallback_count": 0,
            "create_on_unresolved": create_on_unresolved,
        },
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply old advisor prompt patches to v16 dynamic atoms.")
    parser.add_argument("--prompt-patches", required=True)
    parser.add_argument("--base-path", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--generation", type=int, default=0)
    parser.add_argument("--genome", default="")
    parser.add_argument("--no-create-on-unresolved", action="store_true")
    args = parser.parse_args()
    result = apply_patch_file(
        prompt_patches_path=args.prompt_patches,
        base_path=args.base_path,
        out_dir=args.out_dir,
        generation=args.generation,
        genome_path=args.genome or None,
        create_on_unresolved=not args.no_create_on_unresolved,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
