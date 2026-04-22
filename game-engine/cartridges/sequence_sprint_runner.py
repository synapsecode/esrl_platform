"""
Sequence Sprint cartridge.

Mechanic:
- Options slide into decision slots.
- Move selector with LEFT/RIGHT (or A/D).
- Confirm with SPACE or left click.
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


QUESTION_TIME_LIMIT_MS = 11000
MAX_LIVES = 3

COLORS = {
    "bg": (15, 14, 28),
    "panel": (24, 25, 48),
    "text": (245, 246, 255),
    "subtle": (176, 182, 219),
    "accent": (255, 174, 109),
    "success": (109, 227, 152),
    "danger": (247, 124, 134),
    "warning": (255, 209, 123),
    "slot": (52, 59, 105),
    "selector": (255, 236, 159),
}

DEFAULT_SPEC = {
    "title": "Sequence Sprint",
    "theme": "Read quickly, choose the best next concept, and keep your streak alive.",
    "style_variant": "sequence_sprint_v1",
    "instructions": [
        "Move selector with LEFT/RIGHT or A/D.",
        "Press SPACE to lock your chosen option.",
        "Left click an option card to select instantly.",
    ],
    "levels": [
        {
            "name": "Flow Basics",
            "learning_goal": "Understand process order and conceptual sequence",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "In a scientific workflow, what comes after hypothesis?",
                    "correct": "Design and run an experiment",
                    "distractors": ["Skip directly to conclusion", "Ignore data collection"],
                    "explanation": "Hypotheses are tested through experiments.",
                },
                {
                    "prompt": "When debugging, what should happen before rewriting everything?",
                    "correct": "Reproduce the issue and inspect evidence",
                    "distractors": ["Delete modules immediately", "Assume random environment bug"],
                    "explanation": "Reproducible evidence guides efficient fixes.",
                },
                {
                    "prompt": "After solving a problem, what is a strong next step?",
                    "correct": "Reflect on why the solution works",
                    "distractors": ["Forget the method right away", "Avoid documenting key insights"],
                    "explanation": "Reflection improves transfer to future tasks.",
                },
            ],
        }
    ],
}


@dataclass
class OptionCard:
    text: str
    is_correct: bool
    x: float
    y: float
    target_x: float
    width: int = 280
    height: int = 136


class SequenceSprintGame:
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
        self.streak = 0
        self.lives = MAX_LIVES
        self.state = "instructions"

        self.feedback_text = ""
        self.feedback_color = COLORS["text"]
        self.feedback_until_ms = 0
        self.banner_until_ms = 0
        self.question_started_ms = 0
        self.game_over_reason = ""

        self.current_question: Dict = {}
        self.cards: List[OptionCard] = []
        self.selected_idx = 1
        self.slide_speed = 14.0

        self.stars = make_stars(90, seed=sum(ord(ch) for ch in self.title) + 145)
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
            self.selected_idx = min(len(self.cards) - 1, self.selected_idx + 1)
        elif key == pygame.K_SPACE:
            self._confirm_selection(self.selected_idx)
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
        for idx, card in enumerate(self.cards):
            rect = pygame.Rect(int(card.x), int(card.y), card.width, card.height)
            if rect.collidepoint((x, y)):
                self.selected_idx = idx
                self._confirm_selection(idx)
                return

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return

        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Decision timeout.")
            return

        for card in self.cards:
            if card.x > card.target_x:
                card.x = max(card.target_x, card.x - self.slide_speed)

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: choose with speed and accuracy."
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

        y = 352
        targets = [118, 400, 682]
        self.cards = []
        for idx, (text, is_correct) in enumerate(options):
            self.cards.append(
                OptionCard(
                    text=text,
                    is_correct=is_correct,
                    x=float(SCREEN_WIDTH + idx * 140),
                    y=float(y),
                    target_x=float(targets[idx]),
                )
            )
        self.selected_idx = 1
        self.slide_speed = max(8.0, level["speed"] * 5.0)
        self.question_started_ms = pygame.time.get_ticks()

    def _confirm_selection(self, idx: int) -> None:
        if not (0 <= idx < len(self.cards)):
            return
        card = self.cards[idx]
        self._apply_result(card.is_correct, "Great choice." if card.is_correct else "That choice misses the concept.")

    def _apply_result(self, correct: bool, reason: str) -> None:
        explanation = self.current_question.get("explanation", "")
        if correct:
            self.correct_answers += 1
            self.streak += 1
            self.feedback_color = COLORS["success"]
        else:
            self.lives -= 1
            self.streak = 0
            self.feedback_color = COLORS["danger"]
        self.feedback_text = f"{reason} {explanation}"
        self.feedback_until_ms = pygame.time.get_ticks() + 1400

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
        draw_stars(self.screen, self.stars, color=(140, 136, 192))
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
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions} | Streak {self.streak}"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (52, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 166
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        track = pygame.Rect(86, 304, SCREEN_WIDTH - 172, 220)
        pygame.draw.rect(self.screen, (31, 33, 66), track, border_radius=18)
        pygame.draw.rect(self.screen, (76, 83, 155), track, width=2, border_radius=18)

        for idx, card in enumerate(self.cards):
            rect = pygame.Rect(int(card.x), int(card.y), card.width, card.height)
            base = COLORS["slot"]
            if idx == self.selected_idx:
                base = (74, 84, 150)
            pygame.draw.rect(self.screen, base, rect, border_radius=14)
            pygame.draw.rect(
                self.screen,
                COLORS["selector"] if idx == self.selected_idx else (104, 112, 188),
                rect,
                width=3 if idx == self.selected_idx else 2,
                border_radius=14,
            )
            ty = rect.y + 20
            for line in wrap_text(card.text, self.font_small, rect.width - 24)[:4]:
                txt = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(txt, (rect.centerx - txt.get_width() // 2, ty))
                ty += 20

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 74))
        else:
            controls = self.font_small.render("Move: LEFT/RIGHT or A/D | SPACE confirm | Left click option", True, COLORS["subtle"])
            self.screen.blit(controls, (76, SCREEN_HEIGHT - 74))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Sprint Complete!" if victory else "Sprint Failed"
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
        self.streak = 0
        self.lives = MAX_LIVES
        self.state = "instructions"
        self.feedback_text = ""
        self.feedback_until_ms = 0
        self.banner_until_ms = 0
        self.game_over_reason = ""
        self.cards = []
        self.selected_idx = 1
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = SequenceSprintGame(spec or {})
    return game.run()

