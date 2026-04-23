"""
The Wave cartridge.

Mechanic:
- Move across landscape left/right.
- Resonance meter rises near correct beacon and drains near wrong beacons.
- Reach goal with sufficient resonance.
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
TARGET_RESONANCE = 68

COLORS = {
    "bg": (11, 15, 24),
    "panel": (20, 29, 46),
    "text": (242, 247, 255),
    "subtle": (164, 178, 211),
    "accent": (118, 206, 255),
    "success": (110, 230, 160),
    "danger": (244, 124, 136),
    "warning": (255, 206, 122),
    "player": (255, 238, 154),
    "correct": (97, 217, 148),
    "wrong": (237, 108, 126),
    "goal": (132, 215, 255),
}

DEFAULT_SPEC = {
    "title": "The Wave",
    "theme": "Maintain conceptual resonance by staying near valid ideas and away from noisy ones.",
    "style_variant": "wave_resonance_v1",
    "instructions": [
        "Move with LEFT/RIGHT or A/D.",
        "Stand near correct beacon to fill resonance.",
        "Reach goal zone with resonance above threshold.",
    ],
    "levels": [
        {
            "name": "Resonance Field",
            "learning_goal": "Use proximity-based evaluation of concept quality",
            "speed": 2.2,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which nearby statement should you resonate with?",
                    "correct": "Evidence supports this conclusion",
                    "distractors": ["Conclusion without evidence", "Unrelated claim"],
                    "explanation": "Resonate with evidence-based reasoning.",
                },
                {
                    "prompt": "Which operation keeps equation balance?",
                    "correct": "Apply same operation to both sides",
                    "distractors": ["Alter one side only", "Drop constants randomly"],
                    "explanation": "Balanced transformations preserve equality.",
                },
                {
                    "prompt": "Which study strategy is most durable?",
                    "correct": "Spaced retrieval over time",
                    "distractors": ["Single intense cram", "Passive rereading only"],
                    "explanation": "Spacing plus retrieval improves long-term learning.",
                },
            ],
        }
    ],
}


@dataclass
class Beacon:
    x: float
    text: str
    is_correct: bool


class WaveResonanceGame:
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
        self.player_x = 110.0
        self.player_speed = 6.8
        self.resonance = 55.0
        self.beacons: List[Beacon] = []

        self.stars = make_stars(95, seed=sum(ord(ch) for ch in self.title) + 9011)
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
            self.player_x -= self.player_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_x += self.player_speed
        self.player_x = max(70, min(SCREEN_WIDTH - 70, self.player_x))

        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Resonance run timed out.")
            return

        delta = 0.0
        for beacon in self.beacons:
            dist = abs(self.player_x - beacon.x)
            if dist < 120:
                strength = (120 - dist) / 120
                if beacon.is_correct:
                    delta += 0.56 * strength
                else:
                    delta -= 0.82 * strength
        self.resonance += delta
        self.resonance = max(0.0, min(100.0, self.resonance))

        if self.player_x >= SCREEN_WIDTH - 105:
            if self.resonance >= TARGET_RESONANCE:
                self._apply_result(True, "Resonance stable at destination.")
            else:
                self._apply_result(False, "Goal reached with low resonance.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: tune to valid concepts."
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
        positions = [320, 560, 760]
        random.shuffle(positions)
        self.beacons = [Beacon(x=float(positions[i]), text=t, is_correct=c) for i, (t, c) in enumerate(options)]

        self.player_x = 120.0
        self.resonance = 55.0
        self.player_speed = max(5.5, level["speed"] * 2.8)
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
        draw_stars(self.screen, self.stars, color=(115, 142, 194))
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
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        ground = pygame.Rect(70, 510, SCREEN_WIDTH - 140, 90)
        pygame.draw.rect(self.screen, (36, 57, 94), ground, border_radius=16)
        pygame.draw.rect(self.screen, (88, 121, 181), ground, width=2, border_radius=16)

        goal = pygame.Rect(SCREEN_WIDTH - 130, 450, 34, 150)
        pygame.draw.rect(self.screen, COLORS["goal"], goal, border_radius=6)

        for beacon in self.beacons:
            color = COLORS["correct"] if beacon.is_correct else COLORS["wrong"]
            pygame.draw.circle(self.screen, color, (int(beacon.x), 468), 34)
            pygame.draw.circle(self.screen, COLORS["text"], (int(beacon.x), 468), 34, width=2)
            ty = 510
            for line in wrap_text(beacon.text, self.font_small, 190)[:2]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (int(beacon.x - row.get_width() / 2), ty))
                ty += 20

        player = pygame.Rect(int(self.player_x - 24), 474, 48, 36)
        pygame.draw.rect(self.screen, COLORS["player"], player, border_radius=8)
        pygame.draw.rect(self.screen, (82, 74, 33), player, width=2, border_radius=8)

        meter_x, meter_y, meter_w = 90, 620, SCREEN_WIDTH - 180
        pygame.draw.rect(self.screen, (51, 65, 98), (meter_x, meter_y, meter_w, 20), border_radius=8)
        fill_w = int(meter_w * (self.resonance / 100.0))
        fill_color = COLORS["success"] if self.resonance >= TARGET_RESONANCE else COLORS["warning"]
        pygame.draw.rect(self.screen, fill_color, (meter_x, meter_y, fill_w, 20), border_radius=8)
        pygame.draw.rect(self.screen, COLORS["text"], (meter_x, meter_y, meter_w, 20), width=2, border_radius=8)
        label = self.font_small.render(f"Resonance: {int(self.resonance)} / {TARGET_RESONANCE}+ needed", True, COLORS["text"])
        self.screen.blit(label, (meter_x, meter_y - 24))

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 114))
        else:
            controls = self.font_small.render("Move: LEFT/RIGHT or A/D | Stay near correct beacon | Reach goal on right", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 114))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Wave Aligned!" if victory else "Wave Collapsed"
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
        self.player_x = 110.0
        self.resonance = 55.0
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = WaveResonanceGame(spec or {})
    return game.run()
