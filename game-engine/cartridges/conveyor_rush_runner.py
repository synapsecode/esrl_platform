"""
Conveyor Rush cartridge.

Mechanic:
- Item travels along a conveyor.
- Player chooses target bin with LEFT/RIGHT (or A/D).
- Space pauses briefly for inspection.
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


QUESTION_TIME_LIMIT_MS = 12000
MAX_LIVES = 3

COLORS = {
    "bg": (11, 14, 24),
    "panel": (22, 30, 46),
    "text": (240, 246, 255),
    "subtle": (164, 179, 210),
    "accent": (255, 180, 113),
    "success": (112, 230, 161),
    "danger": (246, 126, 137),
    "warning": (255, 206, 121),
    "belt": (63, 75, 106),
    "belt_line": (108, 126, 171),
    "item": (132, 198, 255),
    "bin": (53, 67, 103),
    "selector": (255, 238, 151),
}

DEFAULT_SPEC = {
    "title": "Conveyor Rush",
    "theme": "Sort incoming concepts into the right bin before they pass the gate.",
    "style_variant": "conveyor_rush_v1",
    "instructions": [
        "Move active bin with LEFT/RIGHT or A/D.",
        "Incoming concept reaches the gate quickly.",
        "Press SPACE to briefly pause and inspect.",
    ],
    "levels": [
        {
            "name": "Sorting Line",
            "learning_goal": "Apply rules by selecting the right category quickly",
            "speed": 2.2,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which sentence is in past tense?",
                    "correct": "She walked to school",
                    "distractors": ["She walks to school", "She will walk to school"],
                    "explanation": "Past tense is marked by completed action phrasing.",
                },
                {
                    "prompt": "Which value is prime?",
                    "correct": "13",
                    "distractors": ["15", "21"],
                    "explanation": "13 has exactly two divisors: 1 and 13.",
                },
                {
                    "prompt": "Which organism is a mammal?",
                    "correct": "Dolphin",
                    "distractors": ["Shark", "Octopus"],
                    "explanation": "Dolphins are warm-blooded mammals, not fish.",
                },
            ],
        }
    ],
}


@dataclass
class BeltItem:
    label: str
    x: float
    y: float


class ConveyorRushGame:
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
        self.pause_until_ms = 0
        self.game_over_reason = ""

        self.current_question: Dict = {}
        self.option_labels: List[str] = []
        self.correct_bin_idx = 0
        self.active_bin_idx = 1
        self.item = BeltItem(label="", x=120.0, y=370.0)
        self.item_speed = 4.2

        self.stars = make_stars(80, seed=sum(ord(ch) for ch in self.title) + 501)
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
            self.active_bin_idx = max(0, self.active_bin_idx - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.active_bin_idx = min(2, self.active_bin_idx + 1)
        elif key == pygame.K_SPACE:
            self.pause_until_ms = pygame.time.get_ticks() + 1000
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
        if 520 <= y <= 640:
            if x < 360:
                self.active_bin_idx = 0
            elif x < 720:
                self.active_bin_idx = 1
            else:
                self.active_bin_idx = 2

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        elapsed = now_ms - self.question_started_ms
        if elapsed > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Conveyor timed out.")
            return

        if now_ms >= self.pause_until_ms:
            self.item.x += self.item_speed

        if self.item.x >= 760:
            is_correct = self.active_bin_idx == self.correct_bin_idx
            self._apply_result(is_correct, "Correct sort." if is_correct else "Mis-sorted item.")

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: keep the line accurate."
        self.feedback_color = COLORS["accent"]
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
        self.option_labels = options
        self.correct_bin_idx = options.index(q["correct"])
        self.active_bin_idx = 1

        self.item = BeltItem(label=q["prompt"], x=140.0, y=370.0)
        self.item_speed = max(3.2, level["speed"] * 2.0)
        self.pause_until_ms = 0
        self.question_started_ms = pygame.time.get_ticks()

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
        draw_stars(self.screen, self.stars, color=(141, 145, 188))
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
        y = 164
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 30

        belt_rect = pygame.Rect(84, 332, 910, 84)
        pygame.draw.rect(self.screen, COLORS["belt"], belt_rect, border_radius=14)
        pygame.draw.rect(self.screen, COLORS["belt_line"], belt_rect, width=3, border_radius=14)
        for x in range(100, 960, 60):
            pygame.draw.line(self.screen, COLORS["belt_line"], (x + int(self.item.x * 0.08) % 50, 340), (x + int(self.item.x * 0.08) % 50, 408), 2)

        item_rect = pygame.Rect(int(self.item.x), int(self.item.y), 170, 54)
        pygame.draw.rect(self.screen, COLORS["item"], item_rect, border_radius=10)
        pygame.draw.rect(self.screen, COLORS["text"], item_rect, width=2, border_radius=10)
        label = self.font_small.render("ITEM", True, (16, 24, 40))
        self.screen.blit(label, (item_rect.centerx - label.get_width() // 2, item_rect.y + 16))

        for idx in range(3):
            bin_rect = pygame.Rect(110 + idx * 320, 500, 280, 120)
            pygame.draw.rect(self.screen, COLORS["bin"], bin_rect, border_radius=12)
            border = COLORS["selector"] if idx == self.active_bin_idx else (100, 116, 161)
            pygame.draw.rect(self.screen, border, bin_rect, width=3 if idx == self.active_bin_idx else 2, border_radius=12)
            ty = bin_rect.y + 18
            for line in wrap_text(self.option_labels[idx], self.font_small, bin_rect.width - 24)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (bin_rect.centerx - row.get_width() // 2, ty))
                ty += 20

        gate_text = self.font_small.render("GATE", True, COLORS["warning"])
        self.screen.blit(gate_text, (760, 318))

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Select bin: LEFT/RIGHT or A/D | SPACE pause inspect | Click bin", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Conveyor Mastered!" if victory else "Sorting Breakdown"
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
    game = ConveyorRushGame(spec or {})
    return game.run()
