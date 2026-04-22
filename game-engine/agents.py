"""
eSRL Agents using direct Gemini API calls.
"""

from gemini_client import GeminiClient


GAME_DESIGN_PROMPT = """
You are an expert educational game designer and learning science specialist.

Given summarized study notes, produce one concrete PyGame mini-game concept.
The concept must be interactive, educational, and feasible for a small prototype.

Output sections:
1) Game Title
2) Story/Theme
3) Learning Objectives
4) Player Role
5) Core Gameplay Loop
6) Win/Lose Conditions
7) How Learning Is Embedded
8) Implementation Notes for PyGame

Constraints:
- No vague ideas. Be specific about player actions.
- Keep scope realistic for one self-contained mini-game.
- Do not provide source code.
"""


LEVEL_DESIGN_PROMPT = """
You are an educational level designer.

Given a game concept, produce a clear 3-level progression for a PyGame mini-game.
Each level should introduce or deepen concepts with smooth, logical difficulty.

For each level, provide:
- Level name and progression purpose
- Primary/secondary concept focus
- Challenge structure (win/lose conditions)
- Tutorial guidance
- Difficulty estimate

Constraints:
- Do not write code.
- Keep level specs concrete and implementation-ready.
"""


CARTRIDGE_SPEC_PROMPT = """
You are creating content for a deterministic PyGame cartridge called `quiz_runner_v1`.

Return STRICT JSON only (no markdown, no commentary) with schema:
{
  "title": "string",
  "theme": "string",
  "instructions": ["string", "string", "string"],
  "levels": [
    {
      "name": "string",
      "learning_goal": "string",
      "speed": 2.0,
      "questions_to_clear": 4,
      "question_pool": [
        {
          "prompt": "string",
          "correct": "string",
          "distractors": ["string", "string"],
          "explanation": "string"
        }
      ]
    }
  ]
}

Quality requirements:
- 2 to 3 levels.
- 3 to 6 questions per level.
- Questions and options must come from the study notes.
- Distractors should be plausible misconceptions.
- Keep each option concise (<= 10 words if possible).
- Ensure educational progression from easier to harder.
"""


CODE_GENERATION_PROMPT = """
You are a PyGame code generation agent.

Generate a single Python file for an educational mini-game based on the design.
Return only raw Python code.

Critical requirements:
- pygame.init() must be called.
- Must include instructions screen before gameplay starts.
- Must include a robust game loop with FPS control.
- Must process pygame.QUIT and exit cleanly.
- Must draw with pygame primitives only (no local assets).
- Must define clear win/lose conditions and UI feedback.

Input controls allowed:
- Arrow keys
- WASD
- SPACE
- Left mouse click
"""


CODE_REPAIR_PROMPT = """
You are fixing a generated PyGame script that failed validation.

Return only corrected raw Python code.

Rules:
- Preserve original game idea and learning intent.
- Fix syntax/runtime issues from the validation report.
- Keep code self-contained and runnable.
- Keep controls limited to Arrow keys/WASD/SPACE/left click.
- Keep scope small and stable over novelty.
"""


class GameDesignAgent:
    """Agent for generating game design concepts."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "game_design_agent"

    def run(self, study_notes: str) -> str:
        print(f"\n🎮 {self.name}: Generating game design...")
        result = self.client.generate(prompt=study_notes, system_instruction=GAME_DESIGN_PROMPT)
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class LevelDesignAgent:
    """Agent for generating level progression."""

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


class CartridgeSpecAgent:
    """Agent for generating structured cartridge specs."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "cartridge_spec_agent"

    def run(self, study_notes: str, game_design: str, level_design: str) -> str:
        print(f"\n🧩 {self.name}: Building cartridge content spec...")
        prompt = f"""Study Notes:
{study_notes}

Game Design:
{game_design}

Level Design:
{level_design}
"""
        result = self.client.generate(
            prompt=prompt,
            system_instruction=CARTRIDGE_SPEC_PROMPT,
            response_mime_type="application/json",
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CodeGenerationAgent:
    """Agent for freeform PyGame code generation."""

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
    """Agent for repairing broken freeform game code."""

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
cartridge_spec_agent = CartridgeSpecAgent()
code_generation_agent = CodeGenerationAgent()
code_repair_agent = CodeRepairAgent()
