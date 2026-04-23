"""
Chain Reaction cartridge.

Mechanic:
- Reaction pulse travels toward a junction.
- Player selects redirect branch before impact.
- Correct redirect avoids faulty chain node.
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


QUESTION_TIME_LIMIT_MS = 9000
MAX_LIVES = 3

COLORS = {
    "bg": (11, 14, 22),
    "panel": (21, 28, 44),
    "text": (241, 246, 255),
    "subtle": (166, 180, 213),
    "accent": (136, 206, 255),
    "success": (110, 230, 160),
    "danger": (244, 124, 136),
    "warning": (255, 206, 121),
    "node": (64, 82, 126),
    "junction": (96, 118, 176),
    "pulse": (255, 236, 154),
    "selected": (255, 238, 154),
}

DEFAULT_SPEC = {
    "title": "Chain Reaction",
    "theme": "Redirect a spreading chain reaction toward valid conceptual outcomes.",
    "style_variant": "chain_reaction_v1",
    "instructions": [
        "Select redirect branch with LEFT/RIGHT or A/D.",
        "Press SPACE before pulse reaches the junction.",
        "Choose the branch carrying the correct concept.",
    ],
    "levels": [
        {
            "name": "Causal Flow",
            "learning_goal": "Map cause-effect and logical sequence accurately",
            "speed": 2.1,
            "questions_to_clear": 4,
            "question_pool": [
                {
                    "prompt": "Choose the branch that preserves valid reasoning.",
                    "correct": "Evidence supports the claim",
                    "distractors": ["Claim ignores evidence", "Conclusion before analysis"],
                    "explanation": "Valid chains preserve evidence-to-claim flow.",
                },
                {
                    "prompt": "Which branch is algorithmically correct next step?",
                    "correct": "Validate inputs before processing",
                    "distractors": ["Return output before compute", "Skip boundary checks"],
                    "explanation": "Input validation prevents downstream failures.",
                },
                {
                    "prompt": "Which biological chain link is valid?",
                    "correct": "Energy transfer to next trophic level",
                    "distractors": ["Energy creation from nothing", "Consumer feeds producer with sunlight"],
                    "explanation": "Energy transfers across trophic levels with losses.",
                },
                {
                    "prompt": "Which historical inference is strongest?",
                    "correct": "Corroborated sources imply consistent event sequence",
                    "distractors": ["Single rumor proves timeline", "Later myth rewrites all evidence"],
                    "explanation": "Corroboration strengthens sequence confidence.",
                },
            ],
        }
    ],
}


@dataclass
class Branch:
    text: str
    is_correct: bool


class ChainReactionGame:
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
        self.branches: List[Branch] = []
        self.selected_idx = 1
        self.pulse_progress = 0.0
        self.pulse_speed = 0.012
        self.committed = False

        self.stars = make_stars(85, seed=sum(ord(ch) for ch in self.title) + 6011)
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
            self.selected_idx = min(2, self.selected_idx + 1)
        elif key == pygame.K_SPACE:
            self.committed = True
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
        if 500 <= y <= 660:
            if x < 360:
                self.selected_idx = 0
            elif x < 720:
                self.selected_idx = 1
            else:
                self.selected_idx = 2
            self.committed = True

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Reaction outran redirect.")
            return

        self.pulse_progress += self.pulse_speed
        if self.pulse_progress >= 1.0:
            if self.committed:
                branch = self.branches[self.selected_idx]
                self._apply_result(branch.is_correct, "Redirect successful." if branch.is_correct else "Redirect to faulty node.")
            else:
                self._apply_result(False, "No redirect committed in time.")

    def _start_level(self) -> None:
        self.question_index = 0
        self.feedback_text = f"{self.levels[self.level_index]['name']}: reroute before impact."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        self.current_question = pick_question(level, self.question_index)
        options = [
            Branch(self.current_question["correct"], True),
            Branch(self.current_question["distractors"][0], False),
            Branch(self.current_question["distractors"][1], False),
        ]
        random.shuffle(options)
        self.branches = options
        self.selected_idx = 1
        self.pulse_progress = 0.0
        self.pulse_speed = max(0.0085, level["speed"] * 0.0048)
        self.committed = False
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
        draw_stars(self.screen, self.stars, color=(126, 145, 193))
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
        y = 160
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        source = (210, 340)
        junction = (500, 340)
        branches = [(820, 240), (820, 340), (820, 440)]

        pygame.draw.line(self.screen, (90, 114, 171), source, junction, 6)
        for p in branches:
            pygame.draw.line(self.screen, (90, 114, 171), junction, p, 5)

        pygame.draw.circle(self.screen, COLORS["node"], source, 32)
        pygame.draw.circle(self.screen, COLORS["junction"], junction, 36)
        for idx, p in enumerate(branches):
            color = COLORS["selected"] if idx == self.selected_idx else COLORS["node"]
            pygame.draw.circle(self.screen, color, p, 34)
            pygame.draw.circle(self.screen, COLORS["text"], p, 34, width=2)

            rect = pygame.Rect(p[0] - 145, p[1] + 45, 290, 115)
            pygame.draw.rect(self.screen, (56, 74, 113), rect, border_radius=10)
            border = COLORS["selected"] if idx == self.selected_idx else (101, 120, 166)
            pygame.draw.rect(self.screen, border, rect, width=3 if idx == self.selected_idx else 2, border_radius=10)
            ty = rect.y + 14
            for line in wrap_text(self.branches[idx].text, self.font_small, rect.width - 16)[:3]:
                row = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(row, (rect.centerx - row.get_width() // 2, ty))
                ty += 20

        if self.pulse_progress < 0.65:
            t = self.pulse_progress / 0.65
            x = source[0] + (junction[0] - source[0]) * t
            y = source[1]
        else:
            t = (self.pulse_progress - 0.65) / 0.35
            target = branches[self.selected_idx]
            x = junction[0] + (target[0] - junction[0]) * min(1.0, t)
            y = junction[1] + (target[1] - junction[1]) * min(1.0, t)
        pygame.draw.circle(self.screen, COLORS["pulse"], (int(x), int(y)), 14)

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Select branch: LEFT/RIGHT or A/D | SPACE commit | Click branch", True, COLORS["subtle"])
            self.screen.blit(controls, (72, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Chain Stabilized!" if victory else "Chain Failure"
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
    game = ChainReactionGame(spec or {})
    return game.run()
