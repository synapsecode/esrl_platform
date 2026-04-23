"""
The Dig cartridge.

Mechanic:
- Move excavator cursor on a grid using WASD/Arrows.
- Press SPACE or click to excavate tile.
- Find the correct concept fragment before attempts run out.
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


QUESTION_TIME_LIMIT_MS = 18000
MAX_LIVES = 3
GRID_COLS = 6
GRID_ROWS = 4
CELL_W = 130
CELL_H = 88

COLORS = {
    "bg": (14, 12, 20),
    "panel": (30, 24, 36),
    "text": (246, 244, 240),
    "subtle": (198, 191, 180),
    "accent": (244, 186, 121),
    "success": (126, 218, 157),
    "danger": (236, 131, 124),
    "warning": (255, 212, 133),
    "soil": (86, 65, 46),
    "soil_line": (126, 94, 68),
    "dug": (160, 133, 103),
    "cursor": (255, 235, 156),
}

DEFAULT_SPEC = {
    "title": "The Dig",
    "theme": "Excavate concept fragments and uncover the key piece that completes understanding.",
    "style_variant": "the_dig_v1",
    "instructions": [
        "Move excavator with Arrow keys or WASD.",
        "Press SPACE to dig current tile.",
        "Find the correct fragment before attempts run out.",
    ],
    "levels": [
        {
            "name": "Excavation One",
            "learning_goal": "Identify the key concept among plausible fragments",
            "speed": 2.0,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which step reveals trend direction in data?",
                    "correct": "Plot and inspect the pattern",
                    "distractors": ["Skip visualization", "Use one random point"],
                    "explanation": "Patterns are easier to detect through structured visualization.",
                },
                {
                    "prompt": "Which factor is essential in fair tests?",
                    "correct": "Control variables consistently",
                    "distractors": ["Change all variables", "Ignore measurement setup"],
                    "explanation": "Controlled variables isolate causal signals.",
                },
                {
                    "prompt": "What improves argument reliability?",
                    "correct": "Evidence linked to reasoning",
                    "distractors": ["Confidence without support", "Repeating the claim"],
                    "explanation": "Reliable arguments tie claims to evidence and logic.",
                },
            ],
        }
    ],
}


@dataclass
class DigTile:
    label: str
    is_correct: bool
    dug: bool = False


class TheDigGame:
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
        self.tiles: List[DigTile] = []
        self.cursor_idx = 0
        self.digs_left = 4

        self.stars = make_stars(70, seed=sum(ord(ch) for ch in self.title) + 2033)
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

        col = self.cursor_idx % GRID_COLS
        row = self.cursor_idx // GRID_COLS
        if key in (pygame.K_LEFT, pygame.K_a) and col > 0:
            self.cursor_idx -= 1
        elif key in (pygame.K_RIGHT, pygame.K_d) and col < GRID_COLS - 1:
            self.cursor_idx += 1
        elif key in (pygame.K_UP, pygame.K_w) and row > 0:
            self.cursor_idx -= GRID_COLS
        elif key in (pygame.K_DOWN, pygame.K_s) and row < GRID_ROWS - 1:
            self.cursor_idx += GRID_COLS
        elif key == pygame.K_SPACE:
            self._dig(self.cursor_idx)
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
        gx, gy = 122, 250
        gap = 12
        for idx in range(GRID_COLS * GRID_ROWS):
            col = idx % GRID_COLS
            row = idx // GRID_COLS
            rect = pygame.Rect(gx + col * (CELL_W + gap), gy + row * (CELL_H + gap), CELL_W, CELL_H)
            if rect.collidepoint((x, y)):
                self.cursor_idx = idx
                self._dig(idx)
                break

    def _update(self, now_ms: int) -> None:
        if self.state != "playing":
            return
        if now_ms < self.banner_until_ms or now_ms < self.feedback_until_ms:
            return
        if now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS:
            self._apply_result(False, "Excavation timed out.")

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name}: excavate strategically."
        self.feedback_color = COLORS["accent"]
        now = pygame.time.get_ticks()
        self.feedback_until_ms = now + 1200
        self.banner_until_ms = now + 1200
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        q = pick_question(level, self.question_index)
        self.current_question = q

        pool = [q["correct"], q["distractors"][0], q["distractors"][1]]
        fillers = [
            "Irrelevant fragment",
            "Noise fragment",
            "Partial clue",
            "Unverified clue",
            "Surface artifact",
            "Background detail",
        ]
        while len(pool) < GRID_COLS * GRID_ROWS:
            pool.append(random.choice(fillers))
        random.shuffle(pool)

        self.tiles = [DigTile(label=item, is_correct=(item == q["correct"])) for item in pool[: GRID_COLS * GRID_ROWS]]
        self.cursor_idx = 0
        self.digs_left = 4
        self.question_started_ms = pygame.time.get_ticks()

    def _dig(self, idx: int) -> None:
        if not (0 <= idx < len(self.tiles)):
            return
        tile = self.tiles[idx]
        if tile.dug:
            return
        tile.dug = True

        if tile.is_correct:
            self._apply_result(True, "Key fragment uncovered.")
            return

        self.digs_left -= 1
        if self.digs_left <= 0:
            self._apply_result(False, "All digs spent.")
        else:
            self.feedback_color = COLORS["warning"]
            self.feedback_text = f"Not the key fragment. Digs left: {self.digs_left}"
            self.feedback_until_ms = pygame.time.get_ticks() + 900

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
        draw_stars(self.screen, self.stars, color=(145, 126, 102))
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
        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)} | Score {self.correct_answers}/{self.total_questions} | Digs {self.digs_left}"
        p = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(p, (50, 78))
        lives = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives, (SCREEN_WIDTH - 180, 78))
        if self.state == "playing":
            remaining = max(0, QUESTION_TIME_LIMIT_MS - (now_ms - self.question_started_ms))
            timer = self.font_small.render(f"Timer: {remaining // 1000 + 1}s", True, COLORS["text"])
            self.screen.blit(timer, (SCREEN_WIDTH - 180, 46))

    def _draw_playfield(self, now_ms: int) -> None:
        y = 162
        for line in wrap_text(self.current_question.get("prompt", ""), self.font_body, 920):
            row = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, y))
            y += 30

        gx, gy = 122, 250
        gap = 12
        for idx, tile in enumerate(self.tiles):
            col = idx % GRID_COLS
            row = idx // GRID_COLS
            rect = pygame.Rect(gx + col * (CELL_W + gap), gy + row * (CELL_H + gap), CELL_W, CELL_H)
            fill = COLORS["dug"] if tile.dug else COLORS["soil"]
            pygame.draw.rect(self.screen, fill, rect, border_radius=8)
            border = COLORS["cursor"] if idx == self.cursor_idx else COLORS["soil_line"]
            pygame.draw.rect(self.screen, border, rect, width=3 if idx == self.cursor_idx else 2, border_radius=8)

            if tile.dug:
                ty = rect.y + 12
                for line in wrap_text(tile.label, self.font_small, rect.width - 12)[:3]:
                    row_txt = self.font_small.render(line, True, (38, 32, 26))
                    self.screen.blit(row_txt, (rect.centerx - row_txt.get_width() // 2, ty))
                    ty += 18

        if now_ms < self.feedback_until_ms:
            feedback = self.font_small.render(self.feedback_text, True, self.feedback_color)
            self.screen.blit(feedback, (SCREEN_WIDTH // 2 - feedback.get_width() // 2, SCREEN_HEIGHT - 76))
        else:
            controls = self.font_small.render("Move: Arrow keys/WASD | SPACE dig | Click tile", True, COLORS["subtle"])
            self.screen.blit(controls, (76, SCREEN_HEIGHT - 76))

    def _draw_end_screen(self, victory: bool) -> None:
        heading = "Excavation Complete!" if victory else "Dig Site Lost"
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
    game = TheDigGame(spec or {})
    return game.run()
