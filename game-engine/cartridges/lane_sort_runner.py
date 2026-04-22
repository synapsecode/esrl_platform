"""
Lane Sort cartridge.

Mechanic:
- Player switches among 3 lanes.
- Option gates descend toward the player.
- Survive by aligning with the correct gate.
"""

from __future__ import annotations

import os
import random
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
LANE_COUNT = 3
ROW_HEIGHT = 132
PLAYER_SPEED = 10
MAX_LIVES = 3

COLORS = {
    "bg": (12, 16, 26),
    "panel": (18, 28, 45),
    "text": (241, 246, 255),
    "subtle": (165, 181, 220),
    "accent": (90, 188, 255),
    "warning": (255, 201, 106),
    "success": (104, 224, 143),
    "danger": (242, 119, 126),
    "lane": (33, 48, 77),
    "lane_border": (54, 77, 120),
    "player": (255, 235, 148),
}

DEFAULT_SPEC = {
    "title": "Lane Sort Lab",
    "theme": "Sort through concept lanes and route through the correct answer gate.",
    "style_variant": "lane_sort_lab_v1",
    "instructions": [
        "Move across lanes with LEFT/RIGHT or A/D.",
        "Pass through the gate containing the correct answer.",
        "Wrong gate or timeout costs one life.",
    ],
    "levels": [
        {
            "name": "Foundations",
            "learning_goal": "Recognize core concepts",
            "speed": 2.6,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which study behavior improves retention?",
                    "correct": "Active recall with spaced practice",
                    "distractors": ["Passive rereading only", "Skipping feedback entirely"],
                    "explanation": "Active recall and spacing improve long-term retention.",
                },
                {
                    "prompt": "Which statement is accurate?",
                    "correct": "A hypothesis should be testable",
                    "distractors": ["A hypothesis is never revised", "A hypothesis must be a final fact"],
                    "explanation": "Good hypotheses are testable and revisable.",
                },
                {
                    "prompt": "What helps solve misconceptions?",
                    "correct": "Immediate corrective feedback",
                    "distractors": ["Ignoring errors", "Memorizing without reflection"],
                    "explanation": "Corrective feedback targets misunderstandings early.",
                },
            ],
        }
    ],
}


class LaneSortGame:
    def __init__(self, raw_spec: dict):
        self.spec = normalize_spec(raw_spec, DEFAULT_SPEC)
        self.title = self.spec["title"]
        random.seed(self.title)

        pygame.init()
        pygame.display.set_caption(self.title)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("arial", 48, bold=True)
        self.font_heading = pygame.font.SysFont("arial", 32, bold=True)
        self.font_body = pygame.font.SysFont("arial", 24)
        self.font_small = pygame.font.SysFont("arial", 20)

        self.levels = self.spec["levels"]
        self.total_questions = sum(level["questions_to_clear"] for level in self.levels)
        self.level_index = 0
        self.question_index = 0
        self.correct_answers = 0
        self.lives = MAX_LIVES
        self.state = "instructions"
        self.feedback_text = ""
        self.feedback_color = COLORS["text"]
        self.feedback_until_ms = 0
        self.banner_until_ms = 0
        self.question_started_ms = 0
        self.game_over_reason = ""

        self.stars = make_stars(120, seed=sum(ord(ch) for ch in self.title))
        self.lane_width = (SCREEN_WIDTH - 140) // LANE_COUNT
        self.left_margin = 70
        self.player_lane = 1
        self.player_y = SCREEN_HEIGHT - 130

        self.current_question: Dict = {}
        self.current_options: List[str] = []
        self.correct_lane = 1
        self.row_y = -ROW_HEIGHT

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
                    self._handle_click()

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
            self.player_lane = max(0, self.player_lane - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.player_lane = min(LANE_COUNT - 1, self.player_lane + 1)
        elif key == pygame.K_ESCAPE:
            self.state = "game_over"
            self.game_over_reason = "Session ended by user."

    def _handle_click(self) -> None:
        if self.state == "instructions":
            self.state = "playing"
            self._start_question()
            return
        if self.state in ("victory", "game_over"):
            self._restart()
            return
        if self.state == "playing":
            x, _ = pygame.mouse.get_pos()
            lane = int((x - self.left_margin) / self.lane_width)
            if 0 <= lane < LANE_COUNT:
                self.player_lane = lane

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return

        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return

        elapsed = now_ms - self.question_started_ms
        if elapsed > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Too slow.", self.current_question["explanation"])
            return

        level = self.levels[self.level_index]
        self.row_y += max(2.4, level["speed"] * 1.8)
        if self.row_y + ROW_HEIGHT >= self.player_y:
            is_correct = self.player_lane == self.correct_lane
            reason = "Perfect lane!" if is_correct else "Wrong lane!"
            self._apply_result(is_correct, reason, self.current_question["explanation"])

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player_lane = max(0, self.player_lane - 1)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_lane = min(LANE_COUNT - 1, self.player_lane + 1)

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name} started. Route with precision."
        self.feedback_color = COLORS["accent"]
        now_ms = pygame.time.get_ticks()
        self.feedback_until_ms = now_ms + 1200
        self.banner_until_ms = now_ms + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        question = pick_question(level, self.question_index)
        self.current_question = question

        options = [question["correct"], question["distractors"][0], question["distractors"][1]]
        random.shuffle(options)
        self.current_options = options
        self.correct_lane = options.index(question["correct"])

        self.row_y = -ROW_HEIGHT - 10
        self.question_started_ms = pygame.time.get_ticks()

    def _apply_result(self, correct: bool, reason: str, explanation: str) -> None:
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
        current_level = self.levels[self.level_index]
        if self.question_index >= current_level["questions_to_clear"]:
            self.level_index += 1
            if self.level_index >= len(self.levels):
                self.state = "victory"
                return
            self._start_level()
            return
        self._start_question()

    def _draw(self, now_ms: int) -> None:
        self.screen.fill(COLORS["bg"])
        draw_stars(self.screen, self.stars, color=(120, 146, 196))
        pygame.draw.rect(self.screen, COLORS["panel"], (28, 24, SCREEN_WIDTH - 56, SCREEN_HEIGHT - 48), border_radius=20)
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
        self.screen.blit(title, (56, 44))

        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions}"
        progress_surface = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(progress_surface, (56, 80))

        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 80))

        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 48))

    def _draw_playfield(self, now_ms: int) -> None:
        top = 150
        height = SCREEN_HEIGHT - 240
        pygame.draw.rect(self.screen, (14, 20, 33), (46, top, SCREEN_WIDTH - 92, height), border_radius=18)

        prompt_y = top + 16
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 900):
            prompt_surface = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(prompt_surface, (SCREEN_WIDTH // 2 - prompt_surface.get_width() // 2, prompt_y))
            prompt_y += 30

        lanes_top = top + 92
        lane_height = height - 150
        for lane in range(LANE_COUNT):
            x = self.left_margin + lane * self.lane_width
            rect = pygame.Rect(x, lanes_top, self.lane_width - 8, lane_height)
            pygame.draw.rect(self.screen, COLORS["lane"], rect, border_radius=12)
            pygame.draw.rect(self.screen, COLORS["lane_border"], rect, width=2, border_radius=12)

        row_rect = pygame.Rect(self.left_margin, int(self.row_y + lanes_top), self.lane_width * LANE_COUNT, ROW_HEIGHT)
        pygame.draw.rect(self.screen, (44, 63, 101), row_rect, border_radius=14)
        pygame.draw.rect(self.screen, (88, 118, 184), row_rect, width=2, border_radius=14)

        for lane, option in enumerate(self.current_options):
            x = self.left_margin + lane * self.lane_width + 12
            gate_rect = pygame.Rect(x, int(self.row_y + lanes_top) + 10, self.lane_width - 28, ROW_HEIGHT - 20)
            gate_color = (37, 64, 54) if lane == self.correct_lane else (70, 43, 46)
            pygame.draw.rect(self.screen, gate_color, gate_rect, border_radius=10)
            pygame.draw.rect(self.screen, COLORS["lane_border"], gate_rect, width=2, border_radius=10)
            ty = gate_rect.y + 16
            for line in wrap_text(option, self.font_small, gate_rect.width - 18)[:3]:
                txt = self.font_small.render(line, True, COLORS["text"])
                self.screen.blit(txt, (gate_rect.centerx - txt.get_width() // 2, ty))
                ty += 22

        px = self.left_margin + self.player_lane * self.lane_width + 12
        player_rect = pygame.Rect(px, self.player_y, self.lane_width - 28, 36)
        pygame.draw.rect(self.screen, COLORS["player"], player_rect, border_radius=10)
        pygame.draw.rect(self.screen, (72, 66, 31), player_rect, width=2, border_radius=10)
        player_text = self.font_small.render("ROUTER", True, COLORS["bg"])
        self.screen.blit(
            player_text,
            (player_rect.centerx - player_text.get_width() // 2, player_rect.y + 7),
        )

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 74))
        else:
            controls = self.font_small.render("Controls: LEFT/RIGHT or A/D | Click lane to reposition", True, COLORS["subtle"])
            self.screen.blit(controls, (54, SCREEN_HEIGHT - 74))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Lane Mastered!" if victory else "Route Failed"
        color = COLORS["success"] if victory else COLORS["danger"]
        heading_surface = self.font_title.render(heading, True, color)
        self.screen.blit(heading_surface, (SCREEN_WIDTH // 2 - heading_surface.get_width() // 2, 214))

        score = self.font_heading.render(
            f"Final Score: {self.correct_answers}/{self.total_questions}",
            True,
            COLORS["text"],
        )
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
        self.player_lane = 1
        self._start_level()


def run_game_from_spec(spec: dict) -> int:
    game = LaneSortGame(spec or {})
    return game.run()

