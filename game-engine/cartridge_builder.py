"""
Cartridge pipeline helpers.

Converts structured model output into deterministic game files backed by
shared cartridge mechanics and provides cartridge selection logic.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from cartridges.catalog import get_cartridge, heuristic_rank_cartridges, list_cartridges_dict


DEFAULT_CARTRIDGE = "concept_sprint_v2"
MIN_HEURISTIC_CONFIDENCE = 0.26
MIN_LLM_CONFIDENCE = 0.54


def extract_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse model output as JSON.

    Handles direct JSON output and fenced/embedded JSON blocks.
    """
    text = (raw_text or "").strip()
    if not text:
        return None

    parsed = _try_json_parse(text)
    if isinstance(parsed, dict):
        return parsed

    left = text.find("{")
    right = text.rfind("}")
    if left == -1 or right == -1 or right <= left:
        return None

    parsed = _try_json_parse(text[left : right + 1])
    if isinstance(parsed, dict):
        return parsed
    return None


def cartridge_catalog_for_prompt() -> list:
    """
    Minimal catalog fields for model-driven cartridge selection.
    """
    out = []
    for item in list_cartridges_dict():
        out.append(
            {
                "cartridge_id": item["cartridge_id"],
                "display_name": item["display_name"],
                "mechanic": item["mechanic"],
                "summary": item["summary"],
                "best_for": item["best_for"],
                "keywords": item["keywords"],
                "prompt_hint": item["prompt_hint"],
            }
        )
    return out


def build_cartridge_game_code(
    spec: Dict[str, Any],
    cartridge_name: str = DEFAULT_CARTRIDGE,
) -> str:
    cartridge = get_cartridge(cartridge_name)
    if not cartridge:
        raise ValueError(f"Unsupported cartridge '{cartridge_name}'")

    payload = {
        "cartridge": cartridge_name,
        "spec": spec or {},
    }
    payload_json = json.dumps(payload, ensure_ascii=True, indent=2)
    import_line = f"from cartridges.{cartridge.module} import run_game_from_spec"

    return f'''"""
Auto-generated eSRL PyGame.
Generation mode: cartridge
Cartridge: {cartridge_name}
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

{import_line}

PAYLOAD = json.loads({payload_json!r})


def main() -> int:
    return run_game_from_spec(PAYLOAD.get("spec", {{}}))


if __name__ == "__main__":
    raise SystemExit(main())
'''


def select_best_cartridge(
    study_notes: str,
    game_design: str,
    level_design: str,
    llm_selection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pick best cartridge using model recommendation + heuristic fallback.

    Returns selection payload:
    {
      "selected_cartridge": "<id>|none",
      "confidence": 0.0-1.0,
      "selection_mode": "llm|heuristic|none",
      "reason": "...",
      "candidates": [...]
    }
    """
    ranks = heuristic_rank_cartridges(study_notes, game_design, level_design)
    top = ranks[0] if ranks else None
    top_score = float(top.get("score", 0.0)) if top else 0.0

    llm_id = ""
    llm_conf = 0.0
    llm_reason = ""
    if isinstance(llm_selection, dict):
        llm_id = str(llm_selection.get("selected_cartridge") or "").strip()
        llm_conf = _safe_float(llm_selection.get("confidence"), 0.0)
        llm_reason = str(llm_selection.get("reason") or "").strip()

    if llm_id and llm_id != "none" and get_cartridge(llm_id) and llm_conf >= MIN_LLM_CONFIDENCE:
        return {
            "selected_cartridge": llm_id,
            "confidence": round(llm_conf, 4),
            "selection_mode": "llm",
            "reason": llm_reason or "Model selected this cartridge.",
            "candidates": ranks[:3],
        }

    if top and top_score >= MIN_HEURISTIC_CONFIDENCE:
        cartridge = get_cartridge(top["cartridge_id"])
        reason = f"Heuristic match by keyword profile for {cartridge.display_name if cartridge else top['cartridge_id']}."
        return {
            "selected_cartridge": top["cartridge_id"],
            "confidence": round(top_score, 4),
            "selection_mode": "heuristic",
            "reason": reason,
            "candidates": ranks[:3],
        }

    return {
        "selected_cartridge": "none",
        "confidence": round(max(top_score, llm_conf), 4),
        "selection_mode": "none",
        "reason": "No cartridge reached confidence threshold; falling back to custom code generation.",
        "candidates": ranks[:3],
    }


def build_design_summary(spec: Dict[str, Any], cartridge_name: str = DEFAULT_CARTRIDGE) -> str:
    cartridge = get_cartridge(cartridge_name)
    title = _clean(spec.get("title"), "Generated Learning Sprint")
    theme = _clean(spec.get("theme"), "Interactive concept reinforcement")
    levels = spec.get("levels") if isinstance(spec.get("levels"), list) else []
    instructions = spec.get("instructions") if isinstance(spec.get("instructions"), list) else []

    level_count = len(levels)
    question_count = 0
    for level in levels:
        qpool = level.get("question_pool") if isinstance(level, dict) else None
        if isinstance(qpool, list):
            question_count += len(qpool)

    mechanic = cartridge.mechanic if cartridge else "unknown"
    summary = cartridge.summary if cartridge else "Cartridge-backed educational mini-game."

    instruction_lines = "\n".join(f"- {_clean(line, '')}" for line in instructions[:4] if _clean(line, ""))
    return (
        f"Game Title: {title}\n"
        f"Mechanic Cartridge: {cartridge_name}\n"
        f"Mechanic Type: {mechanic}\n"
        f"Theme: {theme}\n"
        f"Cartridge Summary: {summary}\n"
        f"Planned Levels: {level_count}\n"
        f"Question Bank Size: {question_count}\n"
        "Learning Embedding: Concept prompts are tested through interactive decisions and immediate feedback.\n"
        f"Controls:\n{instruction_lines if instruction_lines else '- Arrow keys / WASD / SPACE / left click'}"
    )


def build_level_summary(spec: Dict[str, Any]) -> str:
    levels = spec.get("levels") if isinstance(spec.get("levels"), list) else []
    if not levels:
        return "No levels defined."

    lines = []
    for idx, level in enumerate(levels[:3], start=1):
        if not isinstance(level, dict):
            continue
        name = _clean(level.get("name"), f"Level {idx}")
        goal = _clean(level.get("learning_goal"), "Strengthen topic recall")
        speed = level.get("speed", "n/a")
        question_pool = level.get("question_pool") if isinstance(level.get("question_pool"), list) else []
        to_clear = level.get("questions_to_clear", len(question_pool))
        lines.append(
            f"Level {idx}: {name}\n"
            f"- Learning Goal: {goal}\n"
            f"- Difficulty Signal: speed {speed}\n"
            f"- Questions to Clear: {to_clear}\n"
            f"- Question Pool: {len(question_pool)} items\n"
        )
    return "\n".join(lines)


def _try_json_parse(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clean(value: Any, fallback: str) -> str:
    text = " ".join(str(value or "").strip().split())
    return text if text else fallback

