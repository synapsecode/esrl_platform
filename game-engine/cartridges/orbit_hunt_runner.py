"""
Orbit Hunt cartridge.

Mechanic:
- Three answer orbs orbit the arena center.
- Move crosshair with arrow keys / WASD.
- Confirm with SPACE or left click when over a target.
"""

from __future__ import annotations

import math
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
CURSOR_SPEED = 7
ORB_RADIUS = 42
ORBIT_RADIUS = 176

COLORS = {
    "bg": (10, 12, 24),
    "panel": (16, 24, 44),
    "text": (244, 247, 255),
    "subtle": (166, 182, 224),
    "accent": (126, 200, 255),
    "success": (110, 231, 149),
    "danger": (247, 125, 131),
    "warning": (255, 209, 120),
    "cursor": (255, 238, 149),
}

DEFAULT_SPEC = {
    "title": "Orbit Hunt",
    "theme": "Track rotating concept orbs and lock onto the correct idea.",
    "style_variant": "orbit_hunt_v1",
    "instructions": [
        "Move crosshair with Arrow keys or WASD.",
        "Press SPACE when your crosshair overlaps your chosen orb.",
        "Left click on an orb to select directly.",
    ],
    "levels": [
        {
            "name": "Target Tracking",
            "learning_goal": "Recognize key terms quickly",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "What is a valid scientific model?",
                    "correct": "A simplified representation used to explain phenomena",
                    "distractors": ["A model can never change", "A model ignores evidence"],
                    "explanation": "Models explain patterns and are refined with evidence.",
                },
                {
                    "prompt": "What defines a variable?",
                    "correct": "A factor that can change in an experiment",
                    "distractors": ["A value that is always fixed", "A result with no measurement"],
                    "explanation": "Variables are measurable factors that can vary.",
                },
                {
                    "prompt": "What makes data reliable?",
                    "correct": "Consistent measurement and repeatable results",
                    "distractors": ["Single guess without checks", "Random values without method"],
                    "explanation": "Reliability needs consistent and repeatable methods.",
                },
            ],
        }
    ],
}


@dataclass
class Orb:
    text: str
    is_correct: bool
    base_angle: float
    speed: float
    radius: float = ORB_RADIUS

    x: float = SCREEN_WIDTH / 2
    y: float = SCREEN_HEIGHT / 2

    def update(self, time_factor: float, center_x: float, center_y: float) -> None:
        angle = self.base_angle + time_factor * self.speed
        self.x = center_x + math.cos(angle) * ORBIT_RADIUS
        self.y = center_y + math.sin(angle) * (ORBIT_RADIUS * 0.72)

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.radius), int(self.y - self.radius), int(self.radius * 2), int(self.radius * 2))


class OrbitHuntGame:
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

        self.cursor_x = SCREEN_WIDTH / 2
        self.cursor_y = SCREEN_HEIGHT / 2 + 140
        self.current_question: Dict = {}
        self.orbs: List[Orb] = []

        self.stars = make_stars(110, seed=sum(ord(ch) for ch in self.title) + 31)
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

        if key == pygame.K_SPACE:
            self._confirm_orb_selection()
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

        for orb in self.orbs:
            if orb.rect().collidepoint(pos):
                self._apply_result(orb.is_correct, orb.text)
                return

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return

        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cursor_x -= CURSOR_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cursor_x += CURSOR_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cursor_y -= CURSOR_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.cursor_y += CURSOR_SPEED
        self.cursor_x = max(90, min(SCREEN_WIDTH - 90, self.cursor_x))
        self.cursor_y = max(180, min(SCREEN_HEIGHT - 90, self.cursor_y))

        elapsed = now_ms - self.question_started_ms
        if elapsed > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "")
            return

        time_factor = elapsed / 1100.0
        center_x, center_y = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 430 * 215
        for orb in self.orbs:
            orb.update(time_factor, center_x, center_y)

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: lock and decide."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        question = pick_question(level, self.question_index)
        self.current_question = question

        options = [
            (question["correct"], True),
            (question["distractors"][0], False),
            (question["distractors"][1], False),
        ]
        random.shuffle(options)

        self.orbs = []
        base = random.uniform(0, math.pi)
        level_speed = level["speed"] * 0.75
        for idx, (text, is_correct) in enumerate(options):
            self.orbs.append(
                Orb(
                    text=text,
                    is_correct=is_correct,
                    base_angle=base + idx * (2 * math.pi / 3),
                    speed=level_speed + idx * 0.12,
                )
            )
        self.question_started_ms = pygame.time.get_ticks()

    def _confirm_orb_selection(self) -> None:
        if not self.orbs:
            return
        chosen = min(self.orbs, key=lambda orb: (orb.x - self.cursor_x) ** 2 + (orb.y - self.cursor_y) ** 2)
        distance = math.sqrt((chosen.x - self.cursor_x) ** 2 + (chosen.y - self.cursor_y) ** 2)
        if distance <= ORB_RADIUS + 24:
            self._apply_result(chosen.is_correct, chosen.text)
        else:
            self._apply_result(False, "")

    def _apply_result(self, correct: bool, chosen_text: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
            self.feedback_text = f"Correct lock. {explanation}"
        else:
            self.lives -= 1
            self.feedback_color = COLORS["danger"]
            if chosen_text:
                self.feedback_text = f"Not this one: {chosen_text}. {explanation}"
            else:
                self.feedback_text = f"Missed lock. {explanation}"
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
        draw_stars(self.screen, self.stars, color=(120, 144, 201))
        pygame.draw.rect(self.screen, COLORS["panel"], (24, 22, SCREEN_WIDTH - 48, SCREEN_HEIGHT - 44), border_radius=20)
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
        progress_surface = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(progress_surface, (52, 78))

        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))

        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        arena = pygame.Rect(64, 150, SCREEN_WIDTH - 128, SCREEN_HEIGHT - 240)
        pygame.draw.rect(self.screen, (12, 18, 35), arena, border_radius=18)
        pygame.draw.rect(self.screen, (66, 92, 152), arena, width=2, border_radius=18)

        y = 166
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 30

        center = (SCREEN_WIDTH // 2, 404)
        pygame.draw.circle(self.screen, (33, 49, 84), center, 186, width=2)
        pygame.draw.circle(self.screen, (52, 78, 124), center, 128, width=1)

        for orb in self.orbs:
            color = (62, 124, 91) if orb.is_correct else (133, 69, 76)
            pygame.draw.circle(self.screen, color, (int(orb.x), int(orb.y)), ORB_RADIUS)
            pygame.draw.circle(self.screen, COLORS["text"], (int(orb.x), int(orb.y)), ORB_RADIUS, width=2)
            text_y = int(orb.y - 18)
            for line in wrap_text(orb.text, self.font_small, 132)[:3]:
                txt = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(txt, (int(orb.x - txt.get_width() / 2), text_y))
                text_y += 16

        pygame.draw.circle(self.screen, COLORS["cursor"], (int(self.cursor_x), int(self.cursor_y)), 15, width=3)
        pygame.draw.line(self.screen, COLORS["cursor"], (int(self.cursor_x) - 18, int(self.cursor_y)), (int(self.cursor_x) + 18, int(self.cursor_y)), 2)
        pygame.draw.line(self.screen, COLORS["cursor"], (int(self.cursor_x), int(self.cursor_y) - 18), (int(self.cursor_x), int(self.cursor_y) + 18), 2)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Move: Arrow keys/WASD | SPACE lock | Left click select", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Orb Mastery Achieved!" if victory else "Orbit Lost"
        color = COLORS["success"] if victory else COLORS["danger"]
        head = self.font_title.render(heading, True, color)
        self.screen.blit(head, (SCREEN_WIDTH // 2 - head.get_width() // 2, 214))

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
        self.cursor_x = SCREEN_WIDTH / 2
        self.cursor_y = SCREEN_HEIGHT / 2 + 140
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = OrbitHuntGame(spec or {})
    return game.run()

