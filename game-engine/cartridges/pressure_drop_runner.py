"""
Pressure Drop cartridge.

Mechanic:
- Move platform left/right.
- Catch correct falling labels.
- Dodge wrong labels.
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


QUESTION_TIME_LIMIT_MS = 12500
MAX_LIVES = 3

COLORS = {
    "bg": (10, 12, 20),
    "panel": (20, 27, 41),
    "text": (241, 246, 255),
    "subtle": (165, 179, 210),
    "accent": (118, 202, 255),
    "success": (106, 228, 158),
    "danger": (244, 124, 136),
    "warning": (255, 207, 122),
    "correct": (98, 216, 148),
    "wrong": (238, 108, 125),
    "platform": (255, 237, 153),
}

DEFAULT_SPEC = {
    "title": "Pressure Drop",
    "theme": "Under pressure, catch only rule-matching items and avoid distractors.",
    "style_variant": "pressure_drop_v1",
    "instructions": [
        "Move platform with LEFT/RIGHT or A/D.",
        "Catch correct labels for each prompt.",
        "Avoid wrong labels or lose stability.",
    ],
    "levels": [
        {
            "name": "Drop Zone",
            "learning_goal": "Rapidly apply concept rules under time pressure",
            "speed": 2.4,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Catch the prime number.",
                    "correct": "17",
                    "distractors": ["18", "21"],
                    "explanation": "17 is prime with exactly two factors.",
                },
                {
                    "prompt": "Catch the sentence in past tense.",
                    "correct": "They completed the task",
                    "distractors": ["They complete the task", "They will complete the task"],
                    "explanation": "Completed indicates past-tense action.",
                },
                {
                    "prompt": "Catch the valid experimental control action.",
                    "correct": "Keep constants unchanged",
                    "distractors": ["Change all variables", "Ignore baseline"],
                    "explanation": "Controls stabilize comparisons.",
                },
            ],
        }
    ],
}


@dataclass
class Drop:
    text: str
    is_correct: bool
    x: float
    y: float
    vy: float


class PressureDropGame:
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
        self.drops: List[Drop] = []
        self.last_spawn_ms = 0
        self.player_x = SCREEN_WIDTH / 2

        self.stars = make_stars(100, seed=sum(ord(ch) for ch in self.title) + 8003)
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
            self._apply_result(False, "No stable catch achieved in time.")
            return

        if now_ms - self.last_spawn_ms > 760:
            self._spawn_drop()
            self.last_spawn_ms = now_ms

        platform = pygame.Rect(int(self.player_x - 70), SCREEN_HEIGHT - 86, 140, 22)

        active: List[Drop] = []
        for drop in self.drops:
            drop.y += drop.vy
            drop_rect = pygame.Rect(int(drop.x - 48), int(drop.y - 24), 96, 48)
            if drop_rect.colliderect(platform):
                if drop.is_correct:
                    self._apply_result(True, "Correct catch under pressure.")
                    return
                self._apply_result(False, "Wrong catch destabilized platform.")
                return
            if drop.y > SCREEN_HEIGHT - 50:
                if drop.is_correct:
                    self._apply_result(False, "Correct item missed.")
                    return
                continue
            active.append(drop)
        self.drops = active

    def _spawn_drop(self) -> None:
        q = self.current_question
        choices = [
            (q["correct"], True),
            (q["distractors"][0], False),
            (q["distractors"][1], False),
        ]
        text, good = random.choice(choices)
        self.drops.append(Drop(text=text, is_correct=good, x=random.uniform(90, SCREEN_WIDTH - 90), y=165.0, vy=random.uniform(3.0, 4.6)))

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: keep composure under pressure."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        self.current_question = pick_question(level, self.question_index)
        self.drops = []
        self.last_spawn_ms = pygame.time.get_ticks() - 800
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
        draw_stars(self.screen, self.stars, color=(115, 141, 191))
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
        y = 160
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        for drop in self.drops:
            color = COLORS["correct"] if drop.is_correct else COLORS["wrong"]
            rect = pygame.Rect(int(drop.x - 50), int(drop.y - 25), 100, 50)
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            pygame.draw.rect(self.screen, COLORS["text"], rect, width=2, border_radius=10)
            ty = rect.y + 12
            for line in wrap_text(drop.text, self.font_small, rect.width - 12)[:2]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (rect.centerx - row.get_width() // 2, ty))
                ty += 18

        platform = pygame.Rect(int(self.player_x - 70), SCREEN_HEIGHT - 86, 140, 22)
        pygame.draw.rect(self.screen, COLORS["platform"], platform, border_radius=9)
        pygame.draw.rect(self.screen, (83, 77, 34), platform, width=2, border_radius=9)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 114))
        else:
            controls = self.font_small.render("Move: LEFT/RIGHT or A/D | Catch correct, dodge wrong | Left click reposition", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 114))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Pressure Managed!" if victory else "Pressure Break"
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
    game = PressureDropGame(spec or {})
    return game.run()
