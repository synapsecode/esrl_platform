"""
eSRL Agents using direct Gemini API calls
"""

from gemini_client import GeminiClient


# Agent prompts
GAME_DESIGN_PROMPT = """
You are an expert **educational game designer** and **learning science specialist** building contextual mini-game concepts for a Self-Regulated Learning (SRL) platform.

Your task is to take **summarized study notes** as input and generate a **single interactive 2D mini-game concept** that can realistically be implemented using **pygame**.

### Core Objective

The output must describe a game that teaches the learner through **active gameplay mechanics**, not passive reading.

### Strict Constraints

* The game must be a **2D browser mini-game** suitable for Phaser.js.
* The game must be **interactive** and based on **player actions**.
* The game must be implementable within a small prototype scope.
* Avoid vague or generic ideas. Be concrete and implementable.
* Do NOT include level-by-level design (this will be handled by another agent).

### Required Output

Provide:
1. **Game Title** - Short, catchy, relevant to topic
2. **Story/Theme** - Theme tied to the notes
3. **Learning Objectives** - Main concepts, sub-concepts, misconceptions addressed
4. **Player Role** - Who the player is
5. **Core Gameplay Loop** - The main repeated interaction
6. **Core Mechanic** - Main interaction (sorting, aiming, matching, etc.)
7. **Win/Lose Conditions**
8. **How Learning is Embedded** - How concepts are encoded into gameplay
9. **Implementation Notes** - Brief Phaser.js feasibility notes

Keep it concise and implementable. Focus on creating a fun, educational experience.
"""

LEVEL_DESIGN_PROMPT = """
You are an expert **educational game designer** specializing in **level progression** and **scaffolded learning design**.

Your task is to take a **game design concept** as input and produce a **complete level progression structure** that allows the student to understand the gamified concept.

## Core Objective

You are provided with the game design concept and you must give a 3 level mini game's level descriptions.

Create a level structure that:
- Gradually introduces mechanics and concepts
- Builds on prior knowledge systematically
- Maintains engagement through varied challenges
- Is implementable in Phaser.js as distinct game levels/stages

General tips:
- Introduce complexity incrementally
- Each level should be challenging but achievable
- Difficulty curve should be smooth, not sudden
- Keep the mechanics simple

Output for each level:
- Level progression arc
- Primary concepts taught, secondary concepts taught
- Challenge structure
  - Challenge type [puzzle/timing/strategy/resource/combat/etc.]
  - Win condition
  - Lose condition
  - Other objectives
- Tutorial details on how to play
- Estimated difficulty

# QUALITY RULES

- Each level must have a clear learning purpose
- Difficulty progression must be logical and achievable
- Levels must build on previous knowledge
- Descriptions must be concrete enough for implementation
- Do NOT write code
- Do NOT design the full game again (focus only on level structure)

Keep it crisp and do not make it too long.
"""

CODE_GENERATION_PROMPT = """
You are a Pygame code Generator Agent.

You will have the game design and level design in your context.
Your task is to take all of that and convert it into a proper pygame mini game.

Output a single python file contents as your response.

CRITICAL RULES:
- Do not pad it with any starting or ending text, nor use any backticks etc. Just provide the raw python code as output
- Do not use any image assets or local data URIs. Draw everything using pygame primitives (circles, rectangles, polygons, lines, text)
- Keep the implementation simple and ensure you write correct code. Do not try to do too much at once
- ALWAYS have a section to show instructions at the start of the game
- Use simple mechanics such as arrow keys and limit mouse only to left clicks
- Show a UI element or instructions to indicate which key does what
- Do not write excessively large code, focus on quality more than quantity. It is a mini game and not a full fledged game
- Make sure pygame.init() is called at the start
- Make sure the game has a proper game loop with FPS control
- Handle QUIT events properly
- Use meaningful colors and make the game visually appealing
- Add clear win/lose conditions and display them
- Keep the game fun and educational

ONLY ALLOWED CONTROLS:
- Arrow keys (UP, DOWN, LEFT, RIGHT)
- WASD keys
- SPACE key
- Left mouse single click

DO NOT INCLUDE RIGHT CLICKS AND OTHER INPUT METHODS.

The game must be self-contained and runnable immediately after generation.

Start directly with the python code. Do not pad with any text"""


class GameDesignAgent:
    """Agent for generating game design concepts"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "game_design_agent"

    def run(self, study_notes: str) -> str:
        """Generate game design from study notes"""
        print(f"\n🎮 {self.name}: Generating game design...")
        result = self.client.generate(
            prompt=study_notes,
            system_instruction=GAME_DESIGN_PROMPT
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class LevelDesignAgent:
    """Agent for generating level progression"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "level_design_agent"

    def run(self, game_design: str) -> str:
        """Generate level design from game design"""
        print(f"\n📊 {self.name}: Creating level progression...")
        result = self.client.generate(
            prompt=f"Based on this game design, create a 3-level progression:\n\n{game_design}",
            system_instruction=LEVEL_DESIGN_PROMPT
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


class CodeGenerationAgent:
    """Agent for generating PyGame code"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = GeminiClient(model_name)
        self.name = "code_generation_agent"

    def run(self, game_design: str, level_design: str) -> str:
        """Generate Phaser.js code from designs"""
        print(f"\n💻 {self.name}: Generating Phaser.js code...")

        combined_input = f"""Game Design:
{game_design}

Level Design:
{level_design}

Please generate a complete, working Phaser.js game based on the above design."""

        result = self.client.generate(
            prompt=combined_input,
            system_instruction=CODE_GENERATION_PROMPT
        )
        print(f"✅ {self.name}: Complete ({len(result)} chars)")
        return result


# Create singleton instances
game_design_agent = GameDesignAgent()
level_design_agent = LevelDesignAgent()
code_generation_agent = CodeGenerationAgent()
