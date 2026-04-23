"""
Blueprint Builder cartridge.

Mechanic:
- Reconstruct a concept system by placing correct tiles.
- Mouse click or SPACE to place selected tile.
- Logical connection lines build the final blueprint.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Dict, List

import pygame

from .common import (
    FPS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    draw_instruction_block,
    draw_stars,
    make_stars,
    normalize_spec,
    pick_question,
    wrap_text,
)


QUESTION_TIME_LIMIT_MS = 17000
MAX_LIVES = 3

COLORS = {
    "bg": (13, 15, 25),
    "panel": (24, 30, 46),
    "text": (241, 246, 255),
    "subtle": (162, 176, 211),
    "accent": (134, 224, 255),
    "success": (110, 229, 159),
    "danger": (244, 122, 136),
    "warning": (255, 206, 121),
    "canvas": (18, 25, 40),
    "tile": (60, 80, 120),
    "selected": (255, 237, 152),
    "placed": (95, 184, 139),
}

DEFAULT_SPEC = {
    "title": "Blueprint Builder",
    "theme": "Place and connect the right concept tiles to reconstruct a system.",
    "style_variant": "blueprint_builder_v1",
    "instructions": [
        "Choose a tile with LEFT/RIGHT or by clicking it.",
        "Press SPACE or click selected tile to place.",
        "Build a coherent chain of correct concepts.",
    ],
    "levels": [
        {
            "name": "System Sketch",
            "learning_goal": "Build logical concept structure step by step",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "In ecosystem flow, what follows producers?",
                    "correct": "Primary consumers",
                    "distractors": ["Abiotic factors", "Decomposers first"],
                    "explanation": "Primary consumers feed on producers in basic chains.",
                },
                {
                    "prompt": "In circuit reasoning, what enables current?",
                    "correct": "A closed path",
                    "distractors": ["An open gap", "Disconnected load"],
                    "explanation": "Current requires a complete closed circuit.",
                },
                {
                    "prompt": "In argument structure, what supports a claim?",
                    "correct": "Evidence and reasoning",
                    "distractors": ["Unrelated opinion", "Conclusion only"],
                    "explanation": "Claims are strengthened through evidence-based support.",
                },
            ],
        }
    ],
}


@dataclass
class TileOption:
    text: str
    is_correct: bool
    rect: pygame.Rect


class BlueprintBuilderGame:
    def __init__(self, raw_spec: dict):
        self.spec = normalize_spec(raw_spec, DEFAULT_SPEC)
        self.title = self.spec["title"]
        random.seed(self.title)

        pygame.init()
        pygame.display.set_caption(self.title)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("arial", 46, bold=True)
        self.font_heading = pygame.font.SysFont("arial", 32, bold=True)
        self.font_body = pygame.font.SysFont("arial", 24)
        self.font_small = pygame.font.SysFont("arial", 20)

        self.levels = self.spec["levels"]
        self.level_index = 0
        self.question_index = 0
        self.total_questions = sum(level["questions_to_clear"] for level in self.levels)
        self.correct_answers = 0
        self.lives = MAX_LIVES
        self.state = "instructions"

        self.feedback_text = ""
        self.feedback_color = COLORS["text"]
        self.feedback_until_ms = 0
        self.banner_until_ms = 0
        self.question_started_ms = 0
        self.game_over_reason = ""

        self.current_question: Dict = {}
        self.options: List[TileOption] = []
        self.selected_idx = 0
        self.placed_tiles: List[str] = []
        self.placed_positions: List[tuple] = []

        self.stars = make_stars(90, seed=sum(ord(ch) for ch in self.title) + 1703)
        self.smoke_mode = os.getenv("ESRL_SMOKE_TEST_MODE") == "1"
        self.smoke_started_ms = pygame.time.get_ticks()

        self._start_level()

    def run(self) -> int:
        running = True
        while running:
            now_ms = pygame.time.get_ticks()
            if self.smoke_mode and now_ms - self.smoke_started_ms > 2200:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._update(now_ms)
            self._draw(now_ms)
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        return 0

    def _handle_key(self, key: int) -> None:
        if self.state == "instructions":
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self.state = "playing"
                self._start_question()
            elif key == pygame.K_ESCAPE:
                self.state = "finished"
            return

        if self.state in ("victory", "game_over"):
            if key == pygame.K_r:
                self._restart()
            elif key == pygame.K_ESCAPE:
                self.state = "finished"
            return

        if self.state != "playing":
            return

        if key in (pygame.K_LEFT, pygame.K_a):
            self.selected_idx = max(0, self.selected_idx - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.selected_idx = min(2, self.selected_idx + 1)
        elif key == pygame.K_SPACE:
            self._place_selected()
        elif key == pygame.K_ESCAPE:
            self.state = "game_over"
            self.game_over_reason = "Session ended by user."

    def _handle_click(self, pos) -> None:
        if self.state == "instructions":
            self.state = "playing"
            self._start_question()
            return
        if self.state in ("victory", "game_over"):
            self._restart()
            return
        if self.state != "playing":
            return

        for idx, option in enumerate(self.options):
            if option.rect.collidepoint(pos):
                self.selected_idx = idx
                self._place_selected()
                return

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Blueprint step timed out.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.placed_tiles = []
        self.placed_positions = []
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: assemble a coherent model."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q
        options = [(q["correct"], True), (q["distractors"][0], False), (q["distractors"][1], False)]
        random.shuffle(options)

        self.options = []
        for idx, (text, is_correct) in enumerate(options):
            rect = pygame.Rect(90 + idx * 330, 540, 300, 128)
            self.options.append(TileOption(text=text, is_correct=is_correct, rect=rect))
        self.selected_idx = 1
        self.question_started_ms = pygame.time.get_ticks()

    def _place_selected(self) -> None:
        if not (0 <= self.selected_idx < len(self.options)):
            return
        option = self.options[self.selected_idx]
        self._apply_result(option.is_correct, "Solid connection." if option.is_correct else "Logical mismatch.")

    def _apply_result(self, correct: bool, reason: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
            self.placed_tiles.append(self.current_question.get("correct", ""))
            x = 160 + len(self.placed_tiles) * 230
            y = 320 if len(self.placed_tiles) % 2 == 0 else 260
            self.placed_positions.append((x, y))
        else:
            self.lives -= 1
            self.feedback_color = COLORS["danger"]
        self.feedback_text = f"{reason} {explanation}"
        self.feedback_until_ms = pygame.time.get_ticks() + 1450

        if self.lives <= 0:
            self.state = "game_over"
            self.game_over_reason = "No lives remaining."
            return

        self.question_index += 1
        level = self.levels[self.level_index]
        if self.question_index >= level["questions_to_clear"]:
            self.level_index += 1
            if self.level_index >= len(self.levels):
                self.state = "victory"
                return
            self._start_level()
            return
        self._start_question()

    def _draw(self, now_ms: int) -> None:
        self.screen.fill(COLORS["bg"])
        draw_stars(self.screen, self.stars, color=(129, 145, 189))
        pygame.draw.rect(self.screen, COLORS["panel"], (24, 20, SCREEN_WIDTH - 48, SCREEN_HEIGHT - 40), border_radius=20)
        self._draw_header(now_ms)

        if self.state == "instructions":
            draw_instruction_block(
                self.screen,
                self.font_title,
                self.font_body,
                self.font_small,
                self.spec["title"],
                self.spec["theme"],
                self.spec["instructions"],
                accent=COLORS["accent"],
                text=COLORS["text"],
                subtle=COLORS["subtle"],
            )
        elif self.state == "playing":
            self._draw_playfield(now_ms)
        elif self.state == "victory":
            self._draw_end_screen(True)
        elif self.state == "game_over":
            self._draw_end_screen(False)

    def _draw_header(self, now_ms: int) -> None:
        title = self.font_heading.render(self.title, True, COLORS["text"])
        self.screen.blit(title, (50, 42))
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions}"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (50, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 162
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        canvas = pygame.Rect(80, 230, SCREEN_WIDTH - 160, 250)
        pygame.draw.rect(self.screen, COLORS["canvas"], canvas, border_radius=16)
        pygame.draw.rect(self.screen, (86, 110, 158), canvas, width=2, border_radius=16)

        for idx, text in enumerate(self.placed_tiles):
            x, y = self.placed_positions[idx]
            rect = pygame.Rect(x - 85, y - 30, 170, 62)
            pygame.draw.rect(self.screen, COLORS["placed"], rect, border_radius=10)
            pygame.draw.rect(self.screen, COLORS["text"], rect, width=2, border_radius=10)
            tx = rect.y + 10
            for line in wrap_text(text, self.font_small, rect.width - 16)[:2]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (rect.centerx - row.get_width() // 2, tx))
                tx += 20
            if idx > 0:
                px, py = self.placed_positions[idx - 1]
                pygame.draw.line(self.screen, COLORS["accent"], (px + 85, py), (x - 85, y), 3)

        for idx, option in enumerate(self.options):
            bg = COLORS["tile"]
            if idx == self.selected_idx:
                bg = (80, 104, 157)
            pygame.draw.rect(self.screen, bg, option.rect, border_radius=12)
            border = COLORS["selected"] if idx == self.selected_idx else (107, 129, 171)
            pygame.draw.rect(self.screen, border, option.rect, width=3 if idx == self.selected_idx else 2, border_radius=12)
            ty = option.rect.y + 18
            for line in wrap_text(option.text, self.font_small, option.rect.width - 20)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (option.rect.centerx - row.get_width() // 2, ty))
                ty += 20

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Select: LEFT/RIGHT or A/D | SPACE place | Click tile", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Blueprint Complete!" if victory else "Blueprint Failed"
        color = COLORS["success"] if victory else COLORS["danger"]
        h = self.font_title.render(heading, True, color)
        self.screen.blit(h, (SCREEN_WIDTH // 2 - h.get_width() // 2, 214))

        score = self.font_heading.render(f"Final Score: {self.correct_answers}/{self.total_questions}", True, COLORS["text"])
        self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, 304))

        if not victory and self.game_over_reason:
            reason = self.font_body.render(self.game_over_reason, True, COLORS["subtle"])
            self.screen.blit(reason, (SCREEN_WIDTH // 2 - reason.get_width() // 2, 354))

        prompt = self.font_body.render("Press R or Left Click to restart, ESC to exit", True, COLORS["subtle"])
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 434))

    def _restart(self) -> None:
        self.level_index = 0
        self.question_index = 0
        self.correct_answers = 0
        self.lives = MAX_LIVES
        self.state = "instructions"
        self.feedback_text = ""
        self.feedback_until_ms = 0
        self.banner_until_ms = 0
        self.game_over_reason = ""
        self.placed_tiles = []
        self.placed_positions = []
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = BlueprintBuilderGame(spec or {})
    return game.run()
