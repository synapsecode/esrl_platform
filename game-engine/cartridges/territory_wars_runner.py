"""
Territory Wars cartridge.

Mechanic:
- Turn-based grid control.
- Answer correctly to claim territory.
- Wrong answers hand tiles to opponent.
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


QUESTION_TIME_LIMIT_MS = 15000
GRID_COLS = 8
GRID_ROWS = 5
MAX_LIVES = 3

COLORS = {
    "bg": (12, 16, 24),
    "panel": (25, 32, 45),
    "text": (241, 246, 255),
    "subtle": (165, 180, 212),
    "accent": (123, 199, 255),
    "success": (109, 230, 158),
    "danger": (246, 126, 134),
    "warning": (255, 205, 122),
    "neutral": (58, 72, 105),
    "player": (97, 196, 141),
    "enemy": (191, 90, 100),
    "selected": (255, 238, 154),
}

DEFAULT_SPEC = {
    "title": "Territory Wars",
    "theme": "Capture more territory than your rival by choosing correct concepts each turn.",
    "style_variant": "territory_wars_v1",
    "instructions": [
        "Choose answer with LEFT/RIGHT or A/D.",
        "Press SPACE to confirm your move.",
        "Correct moves claim tiles; wrong moves lose tiles.",
    ],
    "levels": [
        {
            "name": "Frontline",
            "learning_goal": "Apply reasoning accurately under strategic pressure",
            "speed": 2.0,
            "questions_to_clear": 4,
            "question_pool": [
                {
                    "prompt": "Which claim is best supported by evidence?",
                    "correct": "A claim linked to measured data",
                    "distractors": ["A claim based on certainty alone", "A claim repeated often"],
                    "explanation": "Evidence-backed claims are strongest in reasoning tasks.",
                },
                {
                    "prompt": "Which expression is equivalent to 3(x + 2)?",
                    "correct": "3x + 6",
                    "distractors": ["3x + 2", "x + 6"],
                    "explanation": "Distribute multiplication across both terms.",
                },
                {
                    "prompt": "Which sentence uses active voice?",
                    "correct": "The student solved the problem",
                    "distractors": ["The problem was solved by the student", "The solution was being found"],
                    "explanation": "Active voice places subject as direct actor.",
                },
                {
                    "prompt": "What best defines independent variable?",
                    "correct": "The factor intentionally changed",
                    "distractors": ["The measured outcome", "The constant condition"],
                    "explanation": "Independent variable is manipulated in experiments.",
                },
            ],
        }
    ],
}


@dataclass
class Option:
    text: str
    is_correct: bool


class TerritoryWarsGame:
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
        self.options: List[Option] = []
        self.selected_idx = 1

        self.grid = [0] * (GRID_COLS * GRID_ROWS)  # 0 neutral, 1 player, 2 enemy
        self.stars = make_stars(70, seed=sum(ord(ch) for ch in self.title) + 3031)
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
            self._resolve_turn()
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

        x, y = pos
        if 540 <= y <= 670:
            if x < 360:
                self.selected_idx = 0
            elif x < 720:
                self.selected_idx = 1
            else:
                self.selected_idx = 2
            self._resolve_turn()

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Turn timed out.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: secure strategic control."
        self.feedback_color = COLORS["accent"]
        if self.level_index == 0:
            self.grid = [0] * (GRID_COLS * GRID_ROWS)
            for idx in random.sample(range(len(self.grid)), 6):
                self.grid[idx] = 1
            for idx in random.sample([i for i, v in enumerate(self.grid) if v == 0], 6):
                self.grid[idx] = 2
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
        self.options = [Option(text=t, is_correct=c) for t, c in options]
        self.selected_idx = 1
        self.question_started_ms = pygame.time.get_ticks()

    def _resolve_turn(self) -> None:
        if not self.options:
            return
        picked = self.options[self.selected_idx]
        if picked.is_correct:
            self._apply_result(True, "You claimed territory.")
        else:
            self._apply_result(False, "Opponent counter-claimed.")

    def _claim_tile(self, owner: int) -> None:
        if owner == 1:
            candidates = [i for i, v in enumerate(self.grid) if v != 1]
        else:
            candidates = [i for i, v in enumerate(self.grid) if v != 2]
        if not candidates:
            return
        self.grid[random.choice(candidates)] = owner

    def _apply_result(self, correct: bool, reason: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
            self._claim_tile(1)
        else:
            self.lives -= 1
            self.feedback_color = COLORS["danger"]
            self._claim_tile(2)

        self.feedback_text = f"{reason} {explanation}"
        self.feedback_until_ms = pygame.time.get_ticks() + 1450

        if self.lives <= 0:
            self.state = "game_over"
            self.game_over_reason = "No lives remaining."
            return

        self.question_index += 1
        level = self.levels[self.level_index]
        if self.question_index >= level["questions_to_clear"]:
            player_tiles = sum(1 for v in self.grid if v == 1)
            enemy_tiles = sum(1 for v in self.grid if v == 2)
            if player_tiles <= enemy_tiles:
                self.lives -= 1
                self.feedback_text = "Round tied/lost on territory pressure."
                if self.lives <= 0:
                    self.state = "game_over"
                    self.game_over_reason = "Opponent controls the board."
                    return

            self.level_index += 1
            if self.level_index >= len(self.levels):
                self.state = "victory"
                return
            self._start_level()
            return
        self._start_question()

    def _draw(self, now_ms: int) -> None:
        self.screen.fill(COLORS["bg"])
        draw_stars(self.screen, self.stars, color=(124, 145, 183))
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
        player_tiles = sum(1 for v in self.grid if v == 1)
        enemy_tiles = sum(1 for v in self.grid if v == 2)
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Player {player_tiles} vs Enemy {enemy_tiles}"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (50, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Turn: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 158
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        grid_x, grid_y = 130, 250
        cell_w, cell_h, gap = 100, 54, 8
        for idx, owner in enumerate(self.grid):
            col = idx % GRID_COLS
            row = idx // GRID_COLS
            rect = pygame.Rect(grid_x + col * (cell_w + gap), grid_y + row * (cell_h + gap), cell_w, cell_h)
            color = COLORS["neutral"] if owner == 0 else COLORS["player"] if owner == 1 else COLORS["enemy"]
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            pygame.draw.rect(self.screen, (38, 47, 69), rect, width=1, border_radius=6)

        for idx, option in enumerate(self.options):
            rect = pygame.Rect(90 + idx * 330, 540, 300, 126)
            pygame.draw.rect(self.screen, (58, 74, 111), rect, border_radius=12)
            border = COLORS["selected"] if idx == self.selected_idx else (104, 123, 167)
            pygame.draw.rect(self.screen, border, rect, width=3 if idx == self.selected_idx else 2, border_radius=12)
            ty = rect.y + 18
            for line in wrap_text(option.text, self.font_small, rect.width - 20)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (rect.centerx - row.get_width() // 2, ty))
                ty += 20

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Choose: LEFT/RIGHT or A/D | SPACE confirm | Click option", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Territory Secured!" if victory else "Territory Lost"
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
        self.grid = [0] * (GRID_COLS * GRID_ROWS)
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = TerritoryWarsGame(spec or {})
    return game.run()
