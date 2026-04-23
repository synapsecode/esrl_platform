"""
Negotiation Floor cartridge.

Mechanic:
- Two columns of cards.
- Click one left card and one right card to form a match.
- Correct pair resolves the negotiation round.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

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


QUESTION_TIME_LIMIT_MS = 17000
MAX_LIVES = 3

COLORS = {
    "bg": (12, 13, 24),
    "panel": (24, 26, 44),
    "text": (243, 246, 255),
    "subtle": (172, 178, 209),
    "accent": (162, 214, 255),
    "success": (113, 231, 163),
    "danger": (244, 126, 139),
    "warning": (255, 206, 122),
    "left": (68, 84, 130),
    "right": (86, 72, 133),
    "selected": (255, 238, 154),
}

DEFAULT_SPEC = {
    "title": "Negotiation Floor",
    "theme": "Form correct relational matches while option availability keeps changing.",
    "style_variant": "negotiation_floor_v1",
    "instructions": [
        "Click one card from the left column and one from the right.",
        "Only a coherent pair resolves the round correctly.",
        "Use LEFT/RIGHT to move selection and SPACE to pair quickly.",
    ],
    "levels": [
        {
            "name": "Relational Logic",
            "learning_goal": "Build relational understanding between linked concepts",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Match the claim to the strongest support relation.",
                    "correct": "Evidence-backed claim",
                    "distractors": ["Speculative assertion", "Irrelevant statement"],
                    "explanation": "Strong arguments pair claims with direct evidence support.",
                },
                {
                    "prompt": "Match operation with valid algebraic effect.",
                    "correct": "Distribute over grouped terms",
                    "distractors": ["Ignore coefficient", "Collapse unlike terms"],
                    "explanation": "Distribution applies multiplication to each grouped term.",
                },
                {
                    "prompt": "Match historical cause with likely consequence.",
                    "correct": "Policy change shifts incentives",
                    "distractors": ["Unrelated event triggers outcome", "Timeline reverses cause"],
                    "explanation": "Causal links should preserve chronology and mechanism.",
                },
            ],
        }
    ],
}


@dataclass
class Card:
    text: str
    is_correct: bool
    rect: pygame.Rect


class NegotiationFloorGame:
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
        self.left_cards: List[Card] = []
        self.right_cards: List[Card] = []
        self.left_pick: Optional[int] = None
        self.right_pick: Optional[int] = None

        self.keyboard_idx = 0
        self.stars = make_stars(90, seed=sum(ord(ch) for ch in self.title) + 7021)
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

        total = len(self.left_cards) + len(self.right_cards)
        if key in (pygame.K_LEFT, pygame.K_a):
            self.keyboard_idx = max(0, self.keyboard_idx - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.keyboard_idx = min(total - 1, self.keyboard_idx + 1)
        elif key == pygame.K_SPACE:
            if self.keyboard_idx < len(self.left_cards):
                self.left_pick = self.keyboard_idx
            else:
                self.right_pick = self.keyboard_idx - len(self.left_cards)
            self._try_resolve_pair()
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

        for idx, card in enumerate(self.left_cards):
            if card.rect.collidepoint(pos):
                self.left_pick = idx
                self.keyboard_idx = idx
                self._try_resolve_pair()
                return
        for idx, card in enumerate(self.right_cards):
            if card.rect.collidepoint(pos):
                self.right_pick = idx
                self.keyboard_idx = len(self.left_cards) + idx
                self._try_resolve_pair()
                return

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Negotiation window expired.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: build precise pairings."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q

        left_opts = [(q["correct"], True), (q["distractors"][0], False), (q["distractors"][1], False)]
        random.shuffle(left_opts)
        right_opts = [
            (f"Supports: {q['correct']}", True),
            (f"Supports: {q['distractors'][0]}", False),
            (f"Supports: {q['distractors'][1]}", False),
        ]
        random.shuffle(right_opts)

        self.left_cards = []
        self.right_cards = []
        for idx, (text, good) in enumerate(left_opts):
            self.left_cards.append(Card(text=text, is_correct=good, rect=pygame.Rect(90, 270 + idx * 130, 390, 108)))
        for idx, (text, good) in enumerate(right_opts):
            self.right_cards.append(Card(text=text, is_correct=good, rect=pygame.Rect(600, 270 + idx * 130, 390, 108)))

        self.left_pick = None
        self.right_pick = None
        self.keyboard_idx = 0
        self.question_started_ms = pygame.time.get_ticks()

    def _try_resolve_pair(self) -> None:
        if self.left_pick is None or self.right_pick is None:
            return
        left = self.left_cards[self.left_pick]
        right = self.right_cards[self.right_pick]
        is_correct = left.is_correct and right.is_correct
        self._apply_result(is_correct, "Pair accepted." if is_correct else "Pair rejected.")

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
        draw_stars(self.screen, self.stars, color=(130, 139, 191))
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
            timer = self.font_small.render(f"Window: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 190, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 158
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        left_title = self.font_small.render("Positions", True, COLORS["accent"])
        right_title = self.font_small.render("Supports", True, COLORS["accent"])
        self.screen.blit(left_title, (245 - left_title.get_width() // 2, 238))
        self.screen.blit(right_title, (755 - right_title.get_width() // 2, 238))

        for idx, card in enumerate(self.left_cards):
            bg = COLORS["left"]
            if self.left_pick == idx:
                bg = (93, 113, 172)
            pygame.draw.rect(self.screen, bg, card.rect, border_radius=10)
            is_key_selected = self.keyboard_idx == idx
            border = COLORS["selected"] if is_key_selected else (112, 131, 178)
            pygame.draw.rect(self.screen, border, card.rect, width=3 if is_key_selected else 2, border_radius=10)
            ty = card.rect.y + 16
            for line in wrap_text(card.text, self.font_small, card.rect.width - 18)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (card.rect.centerx - row.get_width() // 2, ty))
                ty += 20

        for idx, card in enumerate(self.right_cards):
            bg = COLORS["right"]
            if self.right_pick == idx:
                bg = (110, 93, 173)
            pygame.draw.rect(self.screen, bg, card.rect, border_radius=10)
            is_key_selected = self.keyboard_idx == len(self.left_cards) + idx
            border = COLORS["selected"] if is_key_selected else (123, 112, 178)
            pygame.draw.rect(self.screen, border, card.rect, width=3 if is_key_selected else 2, border_radius=10)
            ty = card.rect.y + 16
            for line in wrap_text(card.text, self.font_small, card.rect.width - 18)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (card.rect.centerx - row.get_width() // 2, ty))
                ty += 20

        if self.left_pick is not None and self.right_pick is not None:
            a = self.left_cards[self.left_pick].rect.center
            b = self.right_cards[self.right_pick].rect.center
            pygame.draw.line(self.screen, COLORS["selected"], a, b, 3)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Click one left + one right card | Keyboard: LEFT/RIGHT + SPACE", True, COLORS["subtle"])
            self.screen.blit(controls, (74, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Negotiation Won!" if victory else "Negotiation Lost"
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
    game = NegotiationFloorGame(spec or {})
    return game.run()
