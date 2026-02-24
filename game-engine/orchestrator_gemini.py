"""
Orchestrator using direct Gemini API calls
"""

import os
from typing import Dict, Any
from agents import game_design_agent, level_design_agent, code_generation_agent


class Orchestrator:
    """Orchestrates the 3-phase workflow using Gemini agents"""

    def __init__(self):
        self.game_design_agent = game_design_agent
        self.level_design_agent = level_design_agent
        self.code_generation_agent = code_generation_agent

    def run(self, study_notes: str, save_output: bool = True) -> Dict[str, Any]:
        """
        Run the complete workflow: notes -> game design -> levels -> code

        Args:
            study_notes: Input study notes
            save_output: If True, saves index.html to current directory

        Returns:
            Dictionary with all outputs and the final HTML
        """
        print("=" * 80)
        print(" eSRL Notes-to-Game Generator".center(80))
        print("=" * 80)

        # Phase 1: Game Design
        print("\n📋 Phase 1/3: Game Design")
        print("-" * 80)
        game_design = self.game_design_agent.run(study_notes)

        # Phase 2: Level Design
        print("\n📋 Phase 2/3: Level Design")
        print("-" * 80)
        level_design = self.level_design_agent.run(game_design)

        # Phase 3: Code Generation
        print("\n📋 Phase 3/3: Code Generation")
        print("-" * 80)
        code = self.code_generation_agent.run(game_design, level_design)

        # Clean up code (remove markdown if present)
        code = code.replace('```python', '').replace('```', '').strip()

        # Save to file if requested
        if save_output:
            ROOT = os.getcwd()

            print(code)

            os.makedirs("pygames", exist_ok=True)
            output_file = os.path.join(ROOT, "pygames", "game.py")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"\n💾 Saved game to: {output_file}")

            # Auto Start
            python_path = os.path.join(ROOT, "venv", "bin", "python")
            os.system(f'{python_path} {output_file}')
            print(f"\n🎮 Game launched!")

        print("\n" + "=" * 80)
        print(" ✅ Complete!".center(80))
        print("=" * 80)

        return {
            'game_design': game_design,
            'level_design': level_design,
            'code': code,
            'success': True
        }


# Create default orchestrator instance
orchestrator = Orchestrator()


def generate_game(study_notes: str, save_output: bool = True) -> Dict[str, Any]:
    """
    Convenience function to generate a game from study notes

    Args:
        study_notes: The learning content to convert into a game
        save_output: If True, saves index.html to current directory

    Returns:
        Dictionary with all outputs

    Example:
        result = generate_game('''
            # Photosynthesis
            Process by which plants convert light into energy...
        ''')
    """
    return orchestrator.run(study_notes, save_output=save_output)
