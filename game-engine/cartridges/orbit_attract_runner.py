"""
Orbit & Attract cartridge.

Mechanic:
- Move gravity cursor with WASD/Arrow keys.
- Correct objects are attracted toward the cursor and target zone.
- Wrong objects are repelled and should be kept away from the target zone.
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


QUESTION_TIME_LIMIT_MS = 14000
MAX_LIVES = 3
TARGET_ZONE = pygame.Rect(SCREEN_WIDTH // 2 - 110, SCREEN_HEIGHT - 118, 220, 70)

COLORS = {
    "bg": (8, 12, 24),
    "panel": (16, 24, 40),
    "text": (241, 246, 255),
    "subtle": (162, 176, 211),
    "accent": (125, 214, 255),
    "success": (116, 232, 164),
    "danger": (244, 124, 137),
    "warning": (255, 206, 122),
    "target": (87, 160, 255),
    "cursor": (255, 236, 154),
    "correct": (102, 221, 151),
    "wrong": (238, 104, 122),
}

DEFAULT_SPEC = {
    "title": "Orbit & Attract",
    "theme": "Use a gravity cursor to guide correct concepts into a stable target zone.",
    "style_variant": "orbit_attract_v1",
    "instructions": [
        "Move gravity cursor with Arrow keys or WASD.",
        "Correct concepts are pulled toward your cursor.",
        "Keep wrong concepts away from the target zone.",
    ],
    "levels": [
        {
            "name": "Attraction Basics",
            "learning_goal": "Differentiate correct concepts from close distractors",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which practice best strengthens memory over time?",
                    "correct": "Spaced retrieval practice",
                    "distractors": ["Single cram session", "Passive rereading only"],
                    "explanation": "Spacing plus retrieval improves long-term retention.",
                },
                {
                    "prompt": "Which claim is scientifically valid?",
                    "correct": "Hypotheses should be testable",
                    "distractors": ["Hypotheses are final truths", "Evidence is optional"],
                    "explanation": "Scientific hypotheses need testable predictions.",
                },
                {
                    "prompt": "What should follow corrective feedback?",
                    "correct": "Apply it in the next attempt",
                    "distractors": ["Ignore it to save time", "Treat all feedback as equal"],
                    "explanation": "Applying feedback immediately improves performance.",
                },
            ],
        }
    ],
}


@dataclass
class Drifter:
    text: str
    is_correct: bool
    x: float
    y: float
    vx: float
    vy: float
    radius: float = 40.0


class OrbitAttractGame:
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
        self.drifters: List[Drifter] = []
        self.cursor_x = SCREEN_WIDTH / 2
        self.cursor_y = SCREEN_HEIGHT / 2
        self.cursor_speed = 7.5

        self.stars = make_stars(120, seed=sum(ord(ch) for ch in self.title) + 1003)
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
            self.cursor_x, self.cursor_y = pos

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cursor_x -= self.cursor_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cursor_x += self.cursor_speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cursor_y -= self.cursor_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.cursor_y += self.cursor_speed
        self.cursor_x = max(70, min(SCREEN_WIDTH - 70, self.cursor_x))
        self.cursor_y = max(160, min(SCREEN_HEIGHT - 70, self.cursor_y))

        elapsed = now_ms - self.question_started_ms
        if elapsed > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Time window expired.")
            return

        for orb in self.drifters:
            dx = self.cursor_x - orb.x
            dy = self.cursor_y - orb.y
            dist = max(22.0, math.sqrt(dx * dx + dy * dy))
            ux, uy = dx / dist, dy / dist
            force = 0.75 / max(1.0, dist / 120)
            if orb.is_correct:
                orb.vx += ux * force
                orb.vy += uy * force
            else:
                orb.vx -= ux * force * 0.9
                orb.vy -= uy * force * 0.9

            orb.vx *= 0.985
            orb.vy *= 0.985
            orb.x += orb.vx
            orb.y += orb.vy

            if orb.x < 42 or orb.x > SCREEN_WIDTH - 42:
                orb.vx *= -0.75
                orb.x = max(42, min(SCREEN_WIDTH - 42, orb.x))
            if orb.y < 166 or orb.y > SCREEN_HEIGHT - 40:
                orb.vy *= -0.75
                orb.y = max(166, min(SCREEN_HEIGHT - 40, orb.y))

            if TARGET_ZONE.collidepoint(int(orb.x), int(orb.y)):
                self._apply_result(orb.is_correct, "Target stabilized." if orb.is_correct else "Noise reached target.")
                return

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: control attraction and repulsion."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1300
        self.banner_until_ms = now + 1300
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q

        options = [(q["correct"], True), (q["distractors"][0], False), (q["distractors"][1], False)]
        random.shuffle(options)
        self.drifters = []
        seeds = [(250, 230), (SCREEN_WIDTH // 2, 250), (SCREEN_WIDTH - 250, 230)]
        random.shuffle(seeds)
        speed = max(1.6, level["speed"] * 0.7)
        for idx, (text, correct) in enumerate(options):
            x, y = seeds[idx]
            self.drifters.append(
                Drifter(
                    text=text,
                    is_correct=correct,
                    x=float(x),
                    y=float(y),
                    vx=random.uniform(-speed, speed),
                    vy=random.uniform(-speed, speed),
                )
            )
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
        self.feedback_until_ms = pygame.time.get_ticks() + 1500

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
        draw_stars(self.screen, self.stars, color=(113, 144, 210))
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
        arena = pygame.Rect(62, 150, SCREEN_WIDTH - 124, SCREEN_HEIGHT - 236)
        pygame.draw.rect(self.screen, (9, 15, 32), arena, border_radius=18)
        pygame.draw.rect(self.screen, (58, 87, 146), arena, width=2, border_radius=18)

        y = 164
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 30

        pygame.draw.rect(self.screen, COLORS["target"], TARGET_ZONE, border_radius=12)
        pygame.draw.rect(self.screen, COLORS["text"], TARGET_ZONE, width=2, border_radius=12)
        zone_text = self.font_small.render("TARGET ZONE", True, COLORS["text"])
        self.screen.blit(zone_text, (TARGET_ZONE.centerx - zone_text.get_width() // 2, TARGET_ZONE.y + 25))

        for orb in self.drifters:
            color = COLORS["correct"] if orb.is_correct else COLORS["wrong"]
            pygame.draw.circle(self.screen, color, (int(orb.x), int(orb.y)), int(orb.radius))
            pygame.draw.circle(self.screen, COLORS["text"], (int(orb.x), int(orb.y)), int(orb.radius), width=2)
            ty = int(orb.y - 18)
            for line in wrap_text(orb.text, self.font_small, 132)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (int(orb.x - row.get_width() / 2), ty))
                ty += 16

        pygame.draw.circle(self.screen, COLORS["cursor"], (int(self.cursor_x), int(self.cursor_y)), 16, width=3)
        pygame.draw.line(self.screen, COLORS["cursor"], (int(self.cursor_x) - 18, int(self.cursor_y)), (int(self.cursor_x) + 18, int(self.cursor_y)), 2)
        pygame.draw.line(self.screen, COLORS["cursor"], (int(self.cursor_x), int(self.cursor_y) - 18), (int(self.cursor_x), int(self.cursor_y) + 18), 2)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Move cursor: Arrow keys/WASD | Left click to reposition", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Orbit Stabilized!" if victory else "Orbit Collapse"
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
        self.cursor_x = SCREEN_WIDTH / 2
        self.cursor_y = SCREEN_HEIGHT / 2
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = OrbitAttractGame(spec or {})
    return game.run()
