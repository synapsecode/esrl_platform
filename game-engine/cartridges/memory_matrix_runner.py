"""
Memory Matrix cartridge.

Mechanic:
- Navigate a card matrix with Arrow keys / WASD.
- Reveal cards with SPACE or left click.
- Find the card that matches the prompt.
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
MAX_LIVES = 3
GRID_COLS = 3
GRID_ROWS = 2
CARD_W = 250
CARD_H = 132

COLORS = {
    "bg": (13, 16, 27),
    "panel": (21, 30, 46),
    "text": (241, 246, 255),
    "subtle": (167, 182, 214),
    "accent": (137, 214, 255),
    "success": (108, 234, 162),
    "danger": (246, 129, 136),
    "warning": (255, 206, 119),
    "card_back": (50, 67, 104),
    "card_front": (28, 42, 68),
    "cursor": (255, 238, 145),
}

DEFAULT_SPEC = {
    "title": "Memory Matrix",
    "theme": "Scan the matrix and reveal the concept that best matches each prompt.",
    "style_variant": "memory_matrix_v1",
    "instructions": [
        "Move across cards with Arrow keys or WASD.",
        "Press SPACE to reveal the selected card.",
        "Find the correct concept quickly before the timer expires.",
    ],
    "levels": [
        {
            "name": "Pattern Recall",
            "learning_goal": "Strengthen term-definition mapping",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which statement describes correlation correctly?",
                    "correct": "Correlation shows association, not guaranteed causation",
                    "distractors": ["Correlation always proves causation", "Correlation means random noise only"],
                    "explanation": "Correlation indicates relationship, not automatic cause.",
                },
                {
                    "prompt": "What is a control group for?",
                    "correct": "A baseline for comparison in experiments",
                    "distractors": ["A group that receives every variable", "A final summary paragraph"],
                    "explanation": "Control groups provide baseline comparison.",
                },
                {
                    "prompt": "What improves conceptual understanding?",
                    "correct": "Explaining ideas in your own words",
                    "distractors": ["Memorizing without checking meaning", "Ignoring mistakes during review"],
                    "explanation": "Reframing concepts in your own words deepens understanding.",
                },
            ],
        }
    ],
}


@dataclass
class Card:
    text: str
    is_correct: bool
    revealed: bool = False


class MemoryMatrixGame:
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

        self.stars = make_stars(100, seed=sum(ord(ch) for ch in self.title) + 101)
        self.cards: List[Card] = []
        self.current_question: Dict = {}
        self.cursor_idx = 0

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
            if self.cursor_idx % GRID_COLS > 0:
                self.cursor_idx -= 1
        elif key in (pygame.K_RIGHT, pygame.K_d):
            if self.cursor_idx % GRID_COLS < GRID_COLS - 1:
                self.cursor_idx += 1
        elif key in (pygame.K_UP, pygame.K_w):
            if self.cursor_idx >= GRID_COLS:
                self.cursor_idx -= GRID_COLS
        elif key in (pygame.K_DOWN, pygame.K_s):
            if self.cursor_idx < GRID_COLS:
                self.cursor_idx += GRID_COLS
        elif key == pygame.K_SPACE:
            self._reveal_card(self.cursor_idx)
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

        grid_x = 132
        grid_y = 246
        gap_x = 26
        gap_y = 22
        for idx in range(GRID_COLS * GRID_ROWS):
            col = idx % GRID_COLS
            row = idx // GRID_COLS
            rect = pygame.Rect(
                grid_x + col * (CARD_W + gap_x),
                grid_y + row * (CARD_H + gap_y),
                CARD_W,
                CARD_H,
            )
            if rect.collidepoint(pos):
                self.cursor_idx = idx
                self._reveal_card(idx)
                break

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Time expired.")

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: scan and recall."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        question = pick_question(level, self.question_index)
        self.current_question = question

        filler_pool = [
            "Example without evidence",
            "Random unsupported claim",
            "Conclusion before analysis",
            "Memorization without understanding",
            "Irrelevant detail",
            "Unverified assumption",
        ]
        options = [question["correct"], question["distractors"][0], question["distractors"][1]]
        while len(options) < GRID_COLS * GRID_ROWS:
            options.append(random.choice(filler_pool))
        random.shuffle(options)

        self.cards = [Card(text=option, is_correct=(option == question["correct"])) for option in options[: GRID_COLS * GRID_ROWS]]
        self.cursor_idx = 0
        self.question_started_ms = pygame.time.get_ticks()

    def _reveal_card(self, idx: int) -> None:
        if self.state != "playing" or not (0 <= idx < len(self.cards)):
            return
        card = self.cards[idx]
        card.revealed = True
        if card.is_correct:
            self._apply_result(True, "Correct reveal.")
        else:
            self._apply_result(False, "Wrong card.")

    def _apply_result(self, correct: bool, reason: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
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
        draw_stars(self.screen, self.stars, color=(122, 140, 189))
        pygame.draw.rect(self.screen, COLORS["panel"], (26, 24, SCREEN_WIDTH - 52, SCREEN_HEIGHT - 48), border_radius=20)
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
        self.screen.blit(title, (52, 42))
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions}"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (52, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        prompt_y = 152
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, prompt_y))
            prompt_y += 30

        grid_x = 132
        grid_y = 246
        gap_x = 26
        gap_y = 22
        for idx, card in enumerate(self.cards):
            col = idx % GRID_COLS
            row = idx // GRID_COLS
            rect = pygame.Rect(
                grid_x + col * (CARD_W + gap_x),
                grid_y + row * (CARD_H + gap_y),
                CARD_W,
                CARD_H,
            )
            is_selected = idx == self.cursor_idx
            bg = COLORS["card_front"] if card.revealed else COLORS["card_back"]
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            border_color = COLORS["cursor"] if is_selected else (78, 104, 158)
            pygame.draw.rect(self.screen, border_color, rect, width=3 if is_selected else 2, border_radius=14)

            if card.revealed:
                content = card.text
            else:
                content = "REVEAL"
            ty = rect.y + 18
            for line in wrap_text(content, self.font_small, rect.width - 24)[:4]:
                row_surface = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row_surface, (rect.centerx - row_surface.get_width() // 2, ty))
                ty += 20

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Move: Arrow keys/WASD | SPACE reveal | Left click card", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Matrix Solved!" if victory else "Matrix Failed"
        color = COLORS["success"] if victory else COLORS["danger"]
        h = self.font_title.render(heading, True, color)
        self.screen.blit(h, (SCREEN_WIDTH // 2 - h.get_width() // 2, 216))

        score = self.font_heading.render(f"Final Score: {self.correct_answers}/{self.total_questions}", True, COLORS["text"])
        self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, 306))

        if not victory and self.game_over_reason:
            reason = self.font_body.render(self.game_over_reason, True, COLORS["subtle"])
            self.screen.blit(reason, (SCREEN_WIDTH // 2 - reason.get_width() // 2, 356))

        prompt = self.font_body.render("Press R or Left Click to restart, ESC to exit", True, COLORS["subtle"])
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 436))

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
        self.cursor_idx = 0
        self.cards = []
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = MemoryMatrixGame(spec or {})
    return game.run()

