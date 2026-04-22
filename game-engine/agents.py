"""
eSRL agents using direct Gemini API calls.
"""

from __future__ import annotations

import json
from typing import Dict, List

from gemini_client import GeminiClient


GAME_DESIGN_PROMPT = """
You are an expert educational game designer and learning science specialist.

Given summarized study notes, design one educational mini-game concept with:
- Clear learning objective and measurable mastery condition
- Distinct player fantasy and mechanic identity
- High replayability through varied challenge patterns

Output sections:
1) Game Title
2) Story/Theme
3) Learning Objectives (primary + misconceptions addressed)
4) Player Role and Actions
5) Core Gameplay Loop
6) Difficulty Curve (early, mid, late)
7) Win/Lose Conditions
8) How Learning Is Embedded in mechanics
9) Why this is engaging (game-feel hooks)

Constraints:
- Must be implementable in a self-contained PyGame mini-game.
- Prioritize concrete interactions over generic descriptions.
- No source code.
"""


LEVEL_DESIGN_PROMPT = """
You are an educational level designer.

Given a game concept, produce a clear 3-level progression with:
- Scaffolded concept difficulty
- Increasing gameplay challenge without abrupt spikes
- Explicit misconception correction moments

For each level:
- Level name
- Learning goal
- What changes in mechanics/challenge
- Win/lose conditions
- Tutorial/support notes
- Difficulty estimate

Constraints:
- Keep implementation realistic for a compact PyGame project.
- No code.
"""


CARTRIDGE_SELECTION_PROMPT = """
You are selecting the best educational game cartridge for source content.

Input includes:
- Study notes
- Game design
- Level design
- Cartridge catalog

Return STRICT JSON:
{
  "selected_cartridge": "cartridge_id|none",
  "confidence": 0.0,
  "reason": "short reason",
  "alternatives": [
    {"cartridge_id": "id", "confidence": 0.0, "reason": "short"}
  ]
}

Rules:
- Choose `none` when no cartridge cleanly fits.
- Confidence must reflect fit quality and gameplay suitability.
- Prefer cartridges that maximize learning fidelity and mechanic clarity.
"""


CARTRIDGE_SPEC_PROMPT_TEMPLATE = """
You are generating structured content for an educational PyGame cartridge.

Selected cartridge:
- ID: {cartridge_id}
- Name: {display_name}
- Mechanic: {mechanic}
- Summary: {summary}
- Best for: {best_for}
- Prompt hint: {prompt_hint}

Task:
Create strict JSON content that fits the selected mechanic and the source notes.

Return STRICT JSON ONLY with schema:
{{
  "title": "string",
  "theme": "string",
  "style_variant": "{cartridge_id}",
  "instructions": ["string", "string", "string"],
  "levels": [
    {{
      "name": "string",
      "learning_goal": "string",
      "speed": 2.0,
      "questions_to_clear": 4,
      "question_pool": [
        {{
          "prompt": "string",
          "correct": "string",
          "distractors": ["string", "string"],
          "explanation": "string"
        }}
      ]
    }}
  ]
}}

Quality bar:
- 2 to 3 levels.
- 3 to 6 questions per level.
- Tight coupling to source content (no generic trivia).
- Distractors should be plausible misconceptions.
- Improve game feel via concise, high-contrast options and readable phrasing.
- Ensure progression: level 1 foundational, level 2 applied, level 3 transfer/challenge.
- Keep prompts and options concise enough for real-time play.
"""


CODE_GENERATION_PROMPT = """
You are a PyGame code generation agent for educational games.

Generate one complete Python file with high gameplay quality:
- Responsive controls and clear feedback states
- Intentional visual style (color, rhythm, readability)
- Non-cookie-cutter mechanics tied to learning objectives
- Robust loop/quit handling and clean state transitions

Must include:
- pygame.init()
- Instructions screen before gameplay
- FPS-controlled game loop
- Explicit win/lose states
- Clear educational feedback
- No external assets; pygame primitives/text only

Input controls allowed:
- Arrow keys
- WASD
- SPACE
- Left mouse click

Return raw Python code only.
"""


CODE_REPAIR_PROMPT = """
You are fixing a generated PyGame script that failed validation.

Return only corrected raw Python code.

Priorities:
1) Fix syntax/runtime failures first.
2) Preserve intended educational mechanics.
3) Keep controls restricted to Arrow keys/WASD/SPACE/left click.
4) Keep structure maintainable and stable.
"""


class GameDesignAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "game_design_agent"

    def run(self, study_notes: str) -> str:
        print(f"\n🎮 {self.name}: Generating game design...")
        result = self.client.generate(prompt=study_notes, system_instruction=GAME_DESIGN_PROMPT)
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class LevelDesignAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "level_design_agent"

    def run(self, game_design: str) -> str:
        print(f"\n📊 {self.name}: Creating level progression...")
        result = self.client.generate(
            prompt=f"Based on this game design, create a 3-level progression:\n\n{game_design}",
            system_instruction=LEVEL_DESIGN_PROMPT,
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CartridgeSelectionAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "cartridge_selection_agent"

    def run(self, study_notes: str, game_design: str, level_design: str, cartridge_catalog: List[Dict]) -> str:
        print(f"\n🧭 {self.name}: Selecting best cartridge...")
        prompt = f"""Study Notes:
{study_notes}

Game Design:
{game_design}

Level Design:
{level_design}

Cartridge Catalog:
{json.dumps(cartridge_catalog, ensure_ascii=True, indent=2)}
"""
        result = self.client.generate(
            prompt=prompt,
            system_instruction=CARTRIDGE_SELECTION_PROMPT,
            response_mime_type="application/json",
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CartridgeSpecAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "cartridge_spec_agent"

    def run(self, study_notes: str, game_design: str, level_design: str, cartridge_profile: Dict) -> str:
        print(f"\n🧩 {self.name}: Building cartridge content spec...")
        system_prompt = CARTRIDGE_SPEC_PROMPT_TEMPLATE.format(
            cartridge_id=cartridge_profile.get("cartridge_id", "unknown"),
            display_name=cartridge_profile.get("display_name", "Unknown Cartridge"),
            mechanic=cartridge_profile.get("mechanic", "unknown"),
            summary=cartridge_profile.get("summary", ""),
            best_for=", ".join(cartridge_profile.get("best_for", [])),
            prompt_hint=cartridge_profile.get("prompt_hint", ""),
        )
        prompt = f"""Study Notes:
{study_notes}

Game Design:
{game_design}

Level Design:
{level_design}
"""
        result = self.client.generate(
            prompt=prompt,
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CodeGenerationAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "code_generation_agent"

    def run(self, game_design: str, level_design: str) -> str:
        print(f"\n💻 {self.name}: Generating PyGame code...")
        combined_input = f"""Game Design:
{game_design}

Level Design:
{level_design}

Generate a complete, working educational PyGame mini-game."""
        result = self.client.generate(prompt=combined_input, system_instruction=CODE_GENERATION_PROMPT)
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CodeRepairAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "code_repair_agent"

    def run(
        self,
        game_design: str,
        level_design: str,
        failed_code: str,
        validation_report: dict,
        attempt_number: int,
    ) -> str:
        print(f"\n🛠️  {self.name}: Repairing code (attempt {attempt_number})...")
        prompt = f"""Game Design:
{game_design}

Level Design:
{level_design}

Validation Report:
{validation_report}

Broken Code:
{failed_code}
"""
        result = self.client.generate(prompt=prompt, system_instruction=CODE_REPAIR_PROMPT)
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


game_design_agent = GameDesignAgent()
level_design_agent = LevelDesignAgent()
cartridge_selection_agent = CartridgeSelectionAgent()
cartridge_spec_agent = CartridgeSpecAgent()
code_generation_agent = CodeGenerationAgent()
code_repair_agent = CodeRepairAgent()

