"""
Signal & Noise cartridge.

Mechanic:
- Stream items fall from top.
- Hold SPACE to activate filter beam.
- Correct items should be captured; wrong items should pass through.
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


QUESTION_TIME_LIMIT_MS = 14000
MAX_LIVES = 3

COLORS = {
    "bg": (9, 12, 21),
    "panel": (18, 26, 42),
    "text": (242, 247, 255),
    "subtle": (162, 177, 210),
    "accent": (129, 212, 255),
    "success": (112, 232, 161),
    "danger": (244, 124, 137),
    "warning": (255, 206, 122),
    "beam": (96, 194, 255),
    "correct": (99, 220, 150),
    "wrong": (236, 108, 126),
    "player": (255, 237, 153),
}

DEFAULT_SPEC = {
    "title": "Signal & Noise",
    "theme": "Filter a falling stream to capture meaningful signals and ignore distracting noise.",
    "style_variant": "signal_noise_v1",
    "instructions": [
        "Move platform with LEFT/RIGHT or A/D.",
        "Hold SPACE to activate the filter beam.",
        "Capture correct signals and let noise pass.",
    ],
    "levels": [
        {
            "name": "Filtering",
            "learning_goal": "Distinguish rule-matching items from distractors",
            "speed": 2.2,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which statement reflects valid inference?",
                    "correct": "Conclusion follows from evidence",
                    "distractors": ["Conclusion ignores evidence", "Conclusion is a guess"],
                    "explanation": "Valid inference links evidence to conclusion.",
                },
                {
                    "prompt": "Which number is prime?",
                    "correct": "29",
                    "distractors": ["27", "35"],
                    "explanation": "29 has no divisors besides 1 and 29.",
                },
                {
                    "prompt": "Which sentence is grammatically correct?",
                    "correct": "The results are consistent",
                    "distractors": ["The results is consistent", "The result are consistent"],
                    "explanation": "Plural subject requires plural verb.",
                },
            ],
        }
    ],
}


@dataclass
class FallingItem:
    text: str
    is_correct: bool
    x: float
    y: float
    vy: float


class SignalNoiseGame:
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
        self.items: List[FallingItem] = []
        self.spawn_until_ms = 0
        self.last_spawn_ms = 0
        self.captured_correct = 0

        self.player_x = SCREEN_WIDTH / 2
        self.player_width = 130

        self.stars = make_stars(110, seed=sum(ord(ch) for ch in self.title) + 5059)
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

        if self.state == "playing" and key == pygame.K_ESCAPE:
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
        if self.state == "playing":
            self.player_x = pos[0]

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player_x -= 8
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_x += 8
        self.player_x = max(80, min(SCREEN_WIDTH - 80, self.player_x))

        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Filtering timed out.")
            return

        if now_ms < self.spawn_until_ms and now_ms - self.last_spawn_ms > 760:
            self._spawn_item()
            self.last_spawn_ms = now_ms

        beam_active = keys[pygame.K_SPACE]
        beam_rect = pygame.Rect(int(self.player_x - 56), 182, 112, SCREEN_HEIGHT - 240)

        active: List[FallingItem] = []
        for item in self.items:
            item.y += item.vy
            hit_beam = beam_rect.collidepoint(int(item.x), int(item.y)) and beam_active
            if hit_beam:
                if item.is_correct:
                    self.captured_correct += 1
                    if self.captured_correct >= 2:
                        self._apply_result(True, "Signal isolated successfully.")
                        return
                else:
                    self._apply_result(False, "Noise was captured.")
                    return
                continue

            if item.y > SCREEN_HEIGHT - 90:
                if item.is_correct:
                    self._apply_result(False, "Key signal was missed.")
                    return
                continue
            active.append(item)
        self.items = active

    def _spawn_item(self) -> None:
        q = self.current_question
        options = [
            (q["correct"], True),
            (q["distractors"][0], False),
            (q["distractors"][1], False),
        ]
        if random.random() < 0.45:
            text, correct = q["correct"], True
        else:
            text, correct = random.choice(options[1:])
        self.items.append(FallingItem(text=text, is_correct=correct, x=random.uniform(120, SCREEN_WIDTH - 120), y=170.0, vy=random.uniform(2.8, 4.4)))

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: discriminate signal from noise."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        self.current_question = pick_question(level, self.question_index)
        self.items = []
        self.captured_correct = 0
        now = pygame.time.get_ticks()
        self.spawn_until_ms = now + 11000
        self.last_spawn_ms = now - 800
        self.question_started_ms = now

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
        draw_stars(self.screen, self.stars, color=(117, 141, 196))
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
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions} | Captured {self.captured_correct}/2"
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

        keys = pygame.key.get_pressed()
        beam_active = keys[pygame.K_SPACE]
        beam_rect = pygame.Rect(int(self.player_x - 56), 182, 112, SCREEN_HEIGHT - 240)
        if beam_active:
            pygame.draw.rect(self.screen, COLORS["beam"], beam_rect, border_radius=10)

        for item in self.items:
            color = COLORS["correct"] if item.is_correct else COLORS["wrong"]
            pygame.draw.circle(self.screen, color, (int(item.x), int(item.y)), 34)
            pygame.draw.circle(self.screen, COLORS["text"], (int(item.x), int(item.y)), 34, width=2)
            ty = int(item.y - 12)
            for line in wrap_text(item.text, self.font_small, 120)[:2]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (int(item.x - row.get_width() / 2), ty))
                ty += 18

        platform = pygame.Rect(int(self.player_x - self.player_width / 2), SCREEN_HEIGHT - 72, self.player_width, 20)
        pygame.draw.rect(self.screen, COLORS["player"], platform, border_radius=8)
        pygame.draw.rect(self.screen, (88, 80, 35), platform, width=2, border_radius=8)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 108))
        else:
            controls = self.font_small.render("Move: LEFT/RIGHT or A/D | Hold SPACE to filter | Left click reposition", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 108))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Signal Locked!" if victory else "Signal Lost"
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
        self.player_x = SCREEN_WIDTH / 2
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = SignalNoiseGame(spec or {})
    return game.run()
