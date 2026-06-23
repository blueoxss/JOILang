#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .artifacts import utc_now
except ImportError:
    from artifacts import utc_now  # type: ignore


def _read_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_advisor_dir(advisor_dir: str | Path | None, run_dir: str | Path | None) -> Path | None:
    if advisor_dir:
        return Path(advisor_dir)
    if run_dir:
        candidate = Path(run_dir) / "advisor"
        if candidate.exists():
            return candidate
    return None


def _count_patches(payload: Any) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("prompt_patches"), list):
        return len(payload["prompt_patches"])
    return 0


def _advisor_transport(advisor_path: Path | None) -> tuple[str, dict[str, Any]]:
    if advisor_path is None:
        return "WARN", {"message": "No advisor run directory was provided."}
    prompt = advisor_path / "advisor_prompt.json"
    patches = advisor_path / "prompt_patches.json"
    population = advisor_path / "mutation_population.json"
    missing = [str(path) for path in (prompt, patches, population) if not path.exists()]
    details: dict[str, Any] = {
        "advisor_dir": str(advisor_path),
        "advisor_prompt_exists": prompt.exists(),
        "prompt_patches_exists": patches.exists(),
        "mutation_population_exists": population.exists(),
        "missing": missing,
    }
    if missing:
        return "FAIL", details
    try:
        details["prompt_patches_count"] = _count_patches(_read_json_if_exists(patches))
        pop = _read_json_if_exists(population)
        details["mutation_population_candidate_count"] = len(pop.get("candidates", [])) if isinstance(pop, dict) else 0
    except Exception as exc:
        details["error"] = str(exc)
        return "FAIL", details
    return ("PASS" if details["prompt_patches_count"] >= 1 and details["mutation_population_candidate_count"] >= 1 else "FAIL"), details


def _advisor_effectiveness(advisor_path: Path | None, run_path: Path | None) -> tuple[str, dict[str, Any]]:
    if advisor_path is None:
        return "WARN", {"message": "No advisor run directory was provided; effectiveness cannot be asserted."}
    transport_status, details = _advisor_transport(advisor_path)
    proposal = _read_json_if_exists(advisor_path / "proposal_state.json") or {}
    patch_report = _read_json_if_exists(advisor_path / "patch_application_report.json") or {}
    if run_path:
        patch_report = patch_report or _read_json_if_exists(run_path / "patch_application" / "patch_application_report.json") or {}
    prompt_patches = _read_json_if_exists(advisor_path / "prompt_patches.json") or {}
    population = _read_json_if_exists(advisor_path / "mutation_population.json") or {}
    accepted = int(proposal.get("accepted_proposal_count") or patch_report.get("accepted_proposal_count") or 0)
    scheduled = int(proposal.get("advisor_child_scheduled_count") or patch_report.get("advisor_child_scheduled_count") or 0)
    backed_diff = int(proposal.get("advisor_backed_diff_count") or patch_report.get("advisor_backed_diff_count") or 0)
    patch_count = _count_patches(prompt_patches)
    candidate_count = len(population.get("candidates", [])) if isinstance(population, dict) else 0
    details.update(
        {
            "transport_status": transport_status,
            "accepted_proposal_count": accepted,
            "advisor_child_scheduled_count": scheduled,
            "advisor_backed_diff_count": backed_diff,
            "prompt_patches_count": patch_count,
            "mutation_population_candidate_count": candidate_count,
        }
    )
    if transport_status != "PASS":
        return "FAIL", details
    ok = accepted >= 1 and scheduled >= 1 and backed_diff >= 1 and patch_count >= 1 and candidate_count >= 1
    return ("PASS" if ok else "FAIL"), details


def run_check(
    check_name: str,
    out_dir: str | Path | None = None,
    *,
    advisor_dir: str | Path | None = None,
    run_dir: str | Path | None = None,
    strict_results_dir: str | Path | None = None,
) -> dict[str, Any]:
    status = "PASS"
    details: dict[str, Any] = {}
    advisor_path = _resolve_advisor_dir(advisor_dir, run_dir)
    run_path = Path(run_dir) if run_dir else None
    if check_name == "advisor_effectiveness_smoke":
        status, details = _advisor_effectiveness(advisor_path, run_path)
    elif check_name == "advisor_transport_smoke":
        status, details = _advisor_transport(advisor_path)
    elif check_name == "smoke":
        details = {
            "message": "Use render/eval/search subcommands for full smoke validation.",
            "strict_results_dir": str(strict_results_dir or ""),
        }
    else:
        status = "WARN"
        details = {"message": f"unknown check '{check_name}' recorded as warning"}
    result = {"check": check_name, "status": status, "created_at": utc_now(), "details": details}
    if out_dir:
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{check_name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
