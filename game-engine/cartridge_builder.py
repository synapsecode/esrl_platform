"""
Cartridge pipeline helpers.

Converts structured model output into deterministic game files that rely on
shared mechanics instead of full freeform code generation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


DEFAULT_CARTRIDGE = "quiz_runner_v1"


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


def build_cartridge_game_code(
    spec: Dict[str, Any],
    cartridge_name: str = DEFAULT_CARTRIDGE,
) -> str:
    if cartridge_name != DEFAULT_CARTRIDGE:
        raise ValueError(f"Unsupported cartridge '{cartridge_name}'")

    payload = {
        "cartridge": cartridge_name,
        "spec": spec or {},
    }
    payload_json = json.dumps(payload, ensure_ascii=True, indent=2)

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

from cartridges.quiz_runner import run_game_from_spec

PAYLOAD = json.loads({payload_json!r})


def main() -> int:
    return run_game_from_spec(PAYLOAD.get("spec", {{}}))


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_design_summary(spec: Dict[str, Any], cartridge_name: str = DEFAULT_CARTRIDGE) -> str:
    title = _clean(spec.get("title"), "Generated Learning Sprint")
    theme = _clean(spec.get("theme"), "Interactive concept recall and reinforcement")
    instructions = spec.get("instructions") if isinstance(spec.get("instructions"), list) else []
    levels = spec.get("levels") if isinstance(spec.get("levels"), list) else []

    instruction_lines = "\n".join(f"- {_clean(line, '')}" for line in instructions[:4] if _clean(line, ""))
    level_count = len(levels)
    question_count = 0
    for level in levels:
        if not isinstance(level, dict):
            continue
        qpool = level.get("question_pool")
        if isinstance(qpool, list):
            question_count += len(qpool)

    return (
        f"Game Title: {title}\n"
        f"Mechanic Cartridge: {cartridge_name}\n"
        f"Theme: {theme}\n"
        f"Planned Levels: {level_count}\n"
        f"Question Bank Size: {question_count}\n"
        "Core Loop: Move to collect the correct concept option while avoiding distractors.\n"
        "Learning Embedding: Each round maps topic concepts to targeted prompts and immediate feedback.\n"
        f"Controls:\n{instruction_lines if instruction_lines else '- Arrow keys / A-D to move, SPACE or click to advance'}"
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
            f"- Difficulty Signal: bubble speed {speed}\n"
            f"- Questions to Clear: {to_clear}\n"
            f"- Question Pool: {len(question_pool)} items\n"
        )
    return "\n".join(lines)


def _try_json_parse(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clean(value: Any, fallback: str) -> str:
    text = " ".join(str(value or "").strip().split())
    return text if text else fallback

