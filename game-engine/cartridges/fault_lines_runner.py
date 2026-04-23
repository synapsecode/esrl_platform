"""
Fault Lines cartridge.

Mechanic:
- Statement appears as segmented strips.
- Click the segment that contains the fault.
- Useful for grammar, logic, proof, and code reasoning.
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
    "bg": (14, 14, 22),
    "panel": (30, 30, 44),
    "text": (244, 246, 255),
    "subtle": (174, 181, 210),
    "accent": (255, 189, 132),
    "success": (118, 232, 164),
    "danger": (245, 127, 139),
    "warning": (255, 208, 124),
    "segment": (63, 74, 104),
    "fault": (132, 62, 78),
    "selected": (255, 237, 153),
}

DEFAULT_SPEC = {
    "title": "Fault Lines",
    "theme": "Inspect segmented statements and identify the exact faulty segment.",
    "style_variant": "fault_lines_v1",
    "instructions": [
        "Read the segmented statement carefully.",
        "Click the segment containing the logical or factual fault.",
        "Use LEFT/RIGHT + SPACE to select without mouse.",
    ],
    "levels": [
        {
            "name": "Error Hunt",
            "learning_goal": "Pinpoint exact location of conceptual error",
            "speed": 2.0,
            "questions_to_clear": 4,
            "question_pool": [
                {
                    "prompt": "Spot the flawed segment in this argument sequence.",
                    "correct": "Therefore correlation proves direct causation",
                    "distractors": ["Data shows two variables move together", "Further testing is required to confirm cause"],
                    "explanation": "Correlation alone does not prove causation.",
                },
                {
                    "prompt": "Find the faulty mathematical step.",
                    "correct": "Divide by zero to simplify",
                    "distractors": ["Factor common terms", "Check domain constraints"],
                    "explanation": "Division by zero is undefined and invalid.",
                },
                {
                    "prompt": "Which segment breaks grammar logic?",
                    "correct": "The results has significant impact",
                    "distractors": ["The experiment was repeated", "The evidence supports the claim"],
                    "explanation": "Subject-verb agreement should be 'results have'.",
                },
                {
                    "prompt": "Locate the broken debugging assumption.",
                    "correct": "Assume output is correct without test",
                    "distractors": ["Reproduce issue with clear steps", "Inspect logs for edge cases"],
                    "explanation": "Unverified assumptions create hidden bugs.",
                },
            ],
        }
    ],
}


@dataclass
class Segment:
    text: str
    is_fault: bool
    rect: pygame.Rect


class FaultLinesGame:
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
        self.segments: List[Segment] = []
        self.selected_idx = 0

        self.stars = make_stars(70, seed=sum(ord(ch) for ch in self.title) + 4073)
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
            self.selected_idx = min(len(self.segments) - 1, self.selected_idx + 1)
        elif key == pygame.K_SPACE:
            self._choose(self.selected_idx)
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

        for idx, seg in enumerate(self.segments):
            if seg.rect.collidepoint(pos):
                self.selected_idx = idx
                self._choose(idx)
                break

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Inspection timed out.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: isolate the break point."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q

        parts = [q["distractors"][0], q["correct"], q["distractors"][1]]
        random.shuffle(parts)
        self.segments = []
        for idx, text in enumerate(parts):
            rect = pygame.Rect(100 + idx * 320, 350, 300, 150)
            self.segments.append(Segment(text=text, is_fault=(text == q["correct"]), rect=rect))
        self.selected_idx = 1
        self.question_started_ms = pygame.time.get_ticks()

    def _choose(self, idx: int) -> None:
        if not (0 <= idx < len(self.segments)):
            return
        seg = self.segments[idx]
        self._apply_result(seg.is_fault, "Fault correctly identified." if seg.is_fault else "That segment is not the fault.")

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
        draw_stars(self.screen, self.stars, color=(134, 137, 177))
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

        for idx, seg in enumerate(self.segments):
            base = COLORS["fault"] if seg.is_fault else COLORS["segment"]
            pygame.draw.rect(self.screen, base, seg.rect, border_radius=12)
            border = COLORS["selected"] if idx == self.selected_idx else (103, 118, 161)
            pygame.draw.rect(self.screen, border, seg.rect, width=3 if idx == self.selected_idx else 2, border_radius=12)
            ty = seg.rect.y + 18
            for line in wrap_text(seg.text, self.font_small, seg.rect.width - 20)[:5]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (seg.rect.centerx - row.get_width() // 2, ty))
                ty += 20

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Select segment: LEFT/RIGHT or A/D | SPACE choose | Click segment", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Faults Isolated!" if victory else "Inspection Failed"
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
    game = FaultLinesGame(spec or {})
    return game.run()
