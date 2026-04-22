"""
Concept Defense cartridge.

Mechanic:
- Rotate a turret with LEFT/RIGHT (or A/D).
- Fire with SPACE or left click.
- Hit the correct incoming concept node before it reaches the core.
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


QUESTION_TIME_LIMIT_MS = 12000
MAX_LIVES = 3
TARGET_RADIUS = 44
BULLET_SPEED = 12.5

COLORS = {
    "bg": (11, 14, 26),
    "panel": (17, 25, 44),
    "text": (242, 247, 255),
    "subtle": (165, 180, 216),
    "accent": (139, 219, 255),
    "success": (104, 229, 154),
    "danger": (246, 124, 133),
    "warning": (255, 208, 123),
    "core": (255, 233, 146),
    "bullet": (255, 239, 160),
}

DEFAULT_SPEC = {
    "title": "Concept Defense",
    "theme": "Protect the knowledge core by intercepting the correct concept node.",
    "style_variant": "concept_defense_v1",
    "instructions": [
        "Rotate turret with LEFT/RIGHT or A/D.",
        "Press SPACE to fire at your selected target.",
        "Hit the correct node before any node reaches the core.",
    ],
    "levels": [
        {
            "name": "Core Integrity",
            "learning_goal": "Choose accurate concepts under pressure",
            "speed": 1.8,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which claim matches evidence-based reasoning?",
                    "correct": "Conclusions follow from observable evidence",
                    "distractors": ["Conclusions should ignore data", "Conclusions come before evidence"],
                    "explanation": "Evidence-based reasoning ties claims to observations.",
                },
                {
                    "prompt": "Which is a reliable study method?",
                    "correct": "Practice retrieval with spaced intervals",
                    "distractors": ["Cram once and never review", "Memorize without self-testing"],
                    "explanation": "Spacing and retrieval improve retention.",
                },
                {
                    "prompt": "What defines a valid experiment setup?",
                    "correct": "Controlled variables and clear measurement",
                    "distractors": ["No controls with changing methods", "Results before procedure"],
                    "explanation": "Controlled variables and clear measurement improve validity.",
                },
            ],
        }
    ],
}


@dataclass
class Target:
    x: float
    y: float
    vx: float
    vy: float
    text: str
    is_correct: bool
    radius: float = TARGET_RADIUS


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    ttl: int = 110


class ConceptDefenseGame:
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

        self.stars = make_stars(120, seed=sum(ord(ch) for ch in self.title) + 77)
        self.current_question: Dict = {}
        self.targets: List[Target] = []
        self.bullets: List[Bullet] = []

        self.core = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 140)
        self.turret_angle = -math.pi / 2
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
            self._spawn_bullet()
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
        mx, my = pos
        self.turret_angle = math.atan2(my - self.core[1], mx - self.core[0])
        self._spawn_bullet()

    def _spawn_bullet(self) -> None:
        tip_x = self.core[0] + math.cos(self.turret_angle) * 54
        tip_y = self.core[1] + math.sin(self.turret_angle) * 54
        self.bullets.append(
            Bullet(
                x=tip_x,
                y=tip_y,
                vx=math.cos(self.turret_angle) * BULLET_SPEED,
                vy=math.sin(self.turret_angle) * BULLET_SPEED,
            )
        )

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.turret_angle -= 0.045
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.turret_angle += 0.045
        self.turret_angle = max(-math.pi * 0.95, min(-0.05, self.turret_angle))

        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        elapsed = now_ms - self.question_started_ms
        if elapsed > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Target window expired.")
            return

        for target in self.targets:
            target.x += target.vx
            target.y += target.vy

        active_bullets: List[Bullet] = []
        for bullet in self.bullets:
            bullet.x += bullet.vx
            bullet.y += bullet.vy
            bullet.ttl -= 1
            if bullet.ttl > 0 and -20 <= bullet.x <= SCREEN_WIDTH + 20 and -20 <= bullet.y <= SCREEN_HEIGHT + 20:
                active_bullets.append(bullet)
        self.bullets = active_bullets

        for target in self.targets:
            if math.dist((target.x, target.y), self.core) <= target.radius + 30:
                self._apply_result(False, "Core breached.")
                return

        for bullet in list(self.bullets):
            for target in list(self.targets):
                if math.dist((bullet.x, bullet.y), (target.x, target.y)) <= target.radius + 8:
                    self._apply_result(target.is_correct, "Correct intercept." if target.is_correct else "Wrong intercept.")
                    return

    def _start_level(self) -> None:
        self.question_index = 0
        name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{name}: protect the core."
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
        speed = max(1.8, level["speed"] * 0.95)
        self.targets = []
        spawn_points = [(160, 184), (SCREEN_WIDTH // 2, 132), (SCREEN_WIDTH - 160, 184)]
        random.shuffle(spawn_points)
        for idx, (text, is_correct) in enumerate(options):
            sx, sy = spawn_points[idx]
            dx = self.core[0] - sx
            dy = self.core[1] - sy
            mag = max(1.0, math.sqrt(dx * dx + dy * dy))
            vx = dx / mag * speed * (1.0 + idx * 0.06)
            vy = dy / mag * speed * (1.0 + idx * 0.06)
            self.targets.append(Target(x=float(sx), y=float(sy), vx=vx, vy=vy, text=text, is_correct=is_correct))

        self.bullets = []
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
        draw_stars(self.screen, self.stars, color=(125, 145, 201))
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
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (52, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        arena = pygame.Rect(62, 150, SCREEN_WIDTH - 124, SCREEN_HEIGHT - 236)
        pygame.draw.rect(self.screen, (11, 17, 33), arena, border_radius=18)
        pygame.draw.rect(self.screen, (69, 95, 155), arena, width=2, border_radius=18)

        py = 166
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, py))
            py += 30

        pygame.draw.circle(self.screen, (68, 86, 125), self.core, 34)
        pygame.draw.circle(self.screen, COLORS["core"], self.core, 24)

        tip_x = self.core[0] + math.cos(self.turret_angle) * 64
        tip_y = self.core[1] + math.sin(self.turret_angle) * 64
        pygame.draw.line(self.screen, COLORS["core"], self.core, (int(tip_x), int(tip_y)), 7)

        for bullet in self.bullets:
            pygame.draw.circle(self.screen, COLORS["bullet"], (int(bullet.x), int(bullet.y)), 5)

        for target in self.targets:
            color = (62, 127, 93) if target.is_correct else (138, 70, 78)
            pygame.draw.circle(self.screen, color, (int(target.x), int(target.y)), int(target.radius))
            pygame.draw.circle(self.screen, COLORS["text"], (int(target.x), int(target.y)), int(target.radius), width=2)
            ty = int(target.y - 17)
            for line in wrap_text(target.text, self.font_small, 132)[:3]:
                txt = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(txt, (int(target.x - txt.get_width() / 2), ty))
                ty += 16

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 74))
        else:
            controls = self.font_small.render("Rotate: LEFT/RIGHT or A/D | SPACE fire | Left click aim+fire", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 74))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Core Secured!" if victory else "Core Lost"
        color = COLORS["success"] if victory else COLORS["danger"]
        h = self.font_title.render(heading, True, color)
        self.screen.blit(h, (SCREEN_WIDTH // 2 - h.get_width() // 2, 214))

        score = self.font_heading.render(f"Final Score: {self.correct_answers}/{self.total_questions}", True, COLORS["text"])
        self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, 304))

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
        self.targets = []
        self.bullets = []
        self.turret_angle = -math.pi / 2
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = ConceptDefenseGame(spec or {})
    return game.run()

