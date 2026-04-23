"""
Stack & Collapse cartridge.

Mechanic:
- Falling blocks, no rotation.
- Move active block left/right into one of three semantic columns.
- Correct placements stabilize stack; wrong placements increase collapse risk.
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


QUESTION_TIME_LIMIT_MS = 13000
MAX_LIVES = 3

COLORS = {
    "bg": (12, 12, 21),
    "panel": (24, 26, 42),
    "text": (243, 247, 255),
    "subtle": (170, 177, 208),
    "accent": (161, 206, 255),
    "success": (113, 231, 161),
    "danger": (245, 126, 138),
    "warning": (255, 207, 123),
    "column": (56, 71, 107),
    "active": (255, 238, 154),
    "correct": (100, 219, 150),
    "wrong": (238, 108, 126),
}

DEFAULT_SPEC = {
    "title": "Stack & Collapse",
    "theme": "Place falling concept blocks into valid structure columns before instability builds.",
    "style_variant": "stack_collapse_v1",
    "instructions": [
        "Move falling block with LEFT/RIGHT or A/D.",
        "Drop into the column that matches the correct concept.",
        "Wrong placements increase instability and collapse risk.",
    ],
    "levels": [
        {
            "name": "Stability Phase",
            "learning_goal": "Build valid structure by repeated correct placements",
            "speed": 2.2,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Place the block under the valid grammar option.",
                    "correct": "Subject-verb agreement holds",
                    "distractors": ["Verb mismatches subject", "Tense shifts randomly"],
                    "explanation": "Stable sentence structure needs agreement and consistency.",
                },
                {
                    "prompt": "Place under balanced equation transformation.",
                    "correct": "Same operation both sides",
                    "distractors": ["Only one side changed", "Terms removed without rule"],
                    "explanation": "Balanced operations preserve equation truth.",
                },
                {
                    "prompt": "Place under strongest scientific method step.",
                    "correct": "Testable prediction and measurement",
                    "distractors": ["Conclusion before testing", "No observable criteria"],
                    "explanation": "Scientific rigor requires measurable testing.",
                },
            ],
        }
    ],
}


@dataclass
class FallingBlock:
    text: str
    is_correct: bool
    x: float
    y: float
    vy: float


class StackCollapseGame:
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
        self.column_labels: List[str] = []
        self.correct_col = 1
        self.active_col = 1
        self.block: FallingBlock = FallingBlock("", True, 0.0, 0.0, 4.0)
        self.stack_heights = [0, 0, 0]
        self.instability = 0

        self.stars = make_stars(90, seed=sum(ord(ch) for ch in self.title) + 10007)
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
            self.active_col = max(0, self.active_col - 1)
            self.block.x = self._col_x(self.active_col)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.active_col = min(2, self.active_col + 1)
            self.block.x = self._col_x(self.active_col)
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

        x, _ = pos
        if x < 360:
            self.active_col = 0
        elif x < 720:
            self.active_col = 1
        else:
            self.active_col = 2
        self.block.x = self._col_x(self.active_col)

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Block timed out before placement.")
            return

        self.block.y += self.block.vy
        ground_y = 560 - self.stack_heights[self.active_col] * 26
        if self.block.y >= ground_y:
            is_correct = self.active_col == self.correct_col
            self._apply_result(is_correct, "Stable placement." if is_correct else "Unstable placement.")

    def _col_x(self, col: int) -> float:
        return 220.0 + col * 320.0

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: stack for structural integrity."
        self.feedback_color = COLORS["accent"]
        self.stack_heights = [0, 0, 0]
        self.instability = 0
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q

        options = [q["correct"], q["distractors"][0], q["distractors"][1]]
        random.shuffle(options)
        self.column_labels = options
        self.correct_col = options.index(q["correct"])

        self.active_col = 1
        self.block = FallingBlock(
            text=q["prompt"],
            is_correct=True,
            x=self._col_x(self.active_col),
            y=190.0,
            vy=max(3.2, level["speed"] * 1.8),
        )
        self.question_started_ms = pygame.time.get_ticks()

    def _apply_result(self, correct: bool, reason: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
            self.stack_heights[self.active_col] = min(9, self.stack_heights[self.active_col] + 1)
            self.instability = max(0, self.instability - 1)
        else:
            self.lives -= 1
            self.feedback_color = COLORS["danger"]
            self.instability += 1
            self.stack_heights[self.active_col] = max(0, self.stack_heights[self.active_col] - 1)

        self.feedback_text = f"{reason} {explanation}"
        self.feedback_until_ms = pygame.time.get_ticks() + 1450

        if self.lives <= 0 or self.instability >= 4:
            self.state = "game_over"
            self.game_over_reason = "Structure collapsed due to instability."
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
        draw_stars(self.screen, self.stars, color=(131, 137, 192))
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
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions} | Instability {self.instability}/4"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (50, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 160
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        for col in range(3):
            rect = pygame.Rect(120 + col * 320, 260, 260, 320)
            pygame.draw.rect(self.screen, COLORS["column"], rect, border_radius=12)
            border = COLORS["active"] if col == self.active_col else (102, 120, 164)
            pygame.draw.rect(self.screen, border, rect, width=3 if col == self.active_col else 2, border_radius=12)

            for i in range(self.stack_heights[col]):
                block_rect = pygame.Rect(rect.x + 30, rect.bottom - 30 - i * 26, 200, 22)
                color = COLORS["correct"] if i % 2 == 0 else (84, 186, 136)
                pygame.draw.rect(self.screen, color, block_rect, border_radius=5)

            ty = rect.y + 14
            for line in wrap_text(self.column_labels[col], self.font_small, rect.width - 18)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (rect.centerx - row.get_width() // 2, ty))
                ty += 20

        active_rect = pygame.Rect(int(self.block.x - 110), int(self.block.y), 220, 36)
        pygame.draw.rect(self.screen, COLORS["active"], active_rect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 80, 35), active_rect, width=2, border_radius=8)
        label = self.font_small.render("FALLING BLOCK", True, (45, 41, 20))
        self.screen.blit(label, (active_rect.centerx - label.get_width() // 2, active_rect.y + 9))

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Move block: LEFT/RIGHT or A/D | Place in correct semantic column", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Structure Stable!" if victory else "Structure Collapse"
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
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = StackCollapseGame(spec or {})
    return game.run()
