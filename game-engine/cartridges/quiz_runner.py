"""
Quiz Runner cartridge.

Deterministic, reusable PyGame gameplay loop. Generated games only need to
provide JSON content/spec instead of full custom code.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List

import pygame


SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 720
FPS = 60
PLAYER_SPEED = 8
BUBBLE_RADIUS = 42
QUESTION_TIME_LIMIT_MS = 13000
MAX_LEVELS = 3
MAX_QUESTIONS_PER_LEVEL = 6

COLORS = {
    "bg": (15, 20, 32),
    "panel": (24, 32, 50),
    "panel_alt": (35, 46, 70),
    "text": (242, 245, 252),
    "subtle": (170, 180, 205),
    "accent": (89, 180, 255),
    "success": (90, 220, 130),
    "danger": (240, 100, 100),
    "warning": (246, 190, 80),
    "player": (255, 225, 120),
    "correct": (95, 212, 132),
    "wrong": (233, 111, 111),
}

DEFAULT_SPEC = {
    "title": "Concept Sprint",
    "theme": "Collect the correct answers and avoid wrong ones.",
    "instructions": [
        "Move left/right with Arrow keys or A/D.",
        "Catch the correct answer bubble for each prompt.",
        "Wrong catches and timeouts cost a life.",
    ],
    "levels": [
        {
            "name": "Warmup",
            "learning_goal": "Understand the base topic terms",
            "speed": 2.1,
            "questions_to_clear": 3,
            "question_pool": [
                {
                    "prompt": "Which statement is true?",
                    "correct": "A definition explains a concept clearly.",
                    "distractors": [
                        "A definition is always a random guess.",
                        "Definitions are unrelated to learning.",
                    ],
                    "explanation": "Correct. Good definitions make concepts clear.",
                },
                {
                    "prompt": "What helps memory most?",
                    "correct": "Active recall and repeated practice.",
                    "distractors": [
                        "Never checking understanding.",
                        "Reading once without practice.",
                    ],
                    "explanation": "Practice plus recall builds durable memory.",
                },
                {
                    "prompt": "How should you use feedback?",
                    "correct": "Use it to adjust your next attempt.",
                    "distractors": [
                        "Ignore it after one mistake.",
                        "Treat it as unrelated noise.",
                    ],
                    "explanation": "Feedback is most useful when applied quickly.",
                },
            ],
        }
    ],
}


@dataclass
class Bubble:
    text: str
    is_correct: bool
    x: float
    y: float
    speed: float
    wobble_seed: float

    @property
    def rect(self) -> pygame.Rect:
        diameter = BUBBLE_RADIUS * 2
        return pygame.Rect(int(self.x - BUBBLE_RADIUS), int(self.y - BUBBLE_RADIUS), diameter, diameter)

    def move(self, frame_count: int) -> None:
        self.y += self.speed
        self.x += math.sin((frame_count + self.wobble_seed) * 0.05) * 0.9


class QuizRunnerGame:
    def __init__(self, raw_spec: dict):
        self.spec = normalize_spec(raw_spec)
        self.title = self.spec["title"]
        random.seed(self.title)

        pygame.init()
        pygame.display.set_caption(self.title)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("arial", 46, bold=True)
        self.font_heading = pygame.font.SysFont("arial", 34, bold=True)
        self.font_body = pygame.font.SysFont("arial", 24)
        self.font_small = pygame.font.SysFont("arial", 20)

        self.levels = self.spec["levels"]
        self.total_questions = sum(level["questions_to_clear"] for level in self.levels)
        self.level_index = 0
        self.question_index = 0
        self.correct_answers = 0
        self.lives = 3
        self.frame_count = 0

        self.state = "instructions"
        self.feedback_text = ""
        self.feedback_color = COLORS["text"]
        self.feedback_until_ms = 0
        self.level_banner_until_ms = 0
        self.question_started_ms = 0
        self.game_over_reason = ""

        self.player = pygame.Rect(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT - 90, 100, 26)
        self.bubbles: List[Bubble] = []
        self.current_question: Dict = {}
        self.smoke_mode = os.getenv("ESRL_SMOKE_TEST_MODE") == "1"
        self.smoke_started_ms = pygame.time.get_ticks()

        self._start_level()

    def run(self) -> int:
        running = True
        while running:
            self.frame_count += 1
            now_ms = pygame.time.get_ticks()

            if self.smoke_mode and now_ms - self.smoke_started_ms > 2200:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
            if key == pygame.K_ESCAPE:
                self.state = "finished"
        elif self.state in ("victory", "game_over"):
            if key == pygame.K_r:
                self._restart()
            if key == pygame.K_ESCAPE:
                self.state = "finished"
        elif self.state == "playing":
            if key == pygame.K_ESCAPE:
                self.state = "game_over"
                self.game_over_reason = "Session ended early."

    def _handle_click(self) -> None:
        if self.state == "instructions":
            self.state = "playing"
            self._start_question()
        elif self.state in ("victory", "game_over"):
            self._restart()

    def _update(self, now_ms: int) -> None:
        if self.state not in ("playing",):
            return

        keys = pygame.key.get_pressed()
        moving_left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        moving_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if moving_left:
            self.player.x -= PLAYER_SPEED
        if moving_right:
            self.player.x += PLAYER_SPEED
        self.player.x = max(20, min(self.player.x, SCREEN_WIDTH - self.player.width - 20))

        if now_ms < self.level_banner_until_ms:
            return

        if now_ms < self.feedback_until_ms:
            return

        timeout = now_ms - self.question_started_ms > QUESTION_TIME_LIMIT_MS
        if timeout:
            self._apply_result(correct=False, reason="Time up!", explanation=self.current_question["explanation"])
            return

        active_bubbles: List[Bubble] = []
        for bubble in self.bubbles:
            bubble.move(self.frame_count)
            bubble_rect = bubble.rect

            if bubble_rect.colliderect(self.player):
                if bubble.is_correct:
                    self._apply_result(correct=True, reason="Correct!", explanation=self.current_question["explanation"])
                    return
                self._apply_result(correct=False, reason="Wrong answer!", explanation=self.current_question["explanation"])
                return

            if bubble.y - BUBBLE_RADIUS <= SCREEN_HEIGHT:
                active_bubbles.append(bubble)

        self.bubbles = active_bubbles

        if not self.bubbles:
            self._apply_result(correct=False, reason="Missed all options!", explanation=self.current_question["explanation"])

    def _apply_result(self, correct: bool, reason: str, explanation: str) -> None:
        if correct:
            self.correct_answers += 1
            self.feedback_color = COLORS["success"]
        else:
            self.lives -= 1
            self.feedback_color = COLORS["danger"]

        self.feedback_text = f"{reason} {explanation}"
        self.feedback_until_ms = pygame.time.get_ticks() + 1700

        if self.lives <= 0:
            self.state = "game_over"
            self.game_over_reason = "You ran out of lives."
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

    def _start_level(self) -> None:
        self.question_index = 0
        level_name = self.levels[self.level_index]["name"]
        self.feedback_text = f"{level_name} begins. Stay focused."
        self.feedback_color = COLORS["accent"]
        now_ms = pygame.time.get_ticks()
        self.feedback_until_ms = now_ms + 1300
        self.level_banner_until_ms = now_ms + 1300
        self._start_question()

    def _start_question(self) -> None:
        level = self.levels[self.level_index]
        question = level["question_pool"][self.question_index % len(level["question_pool"])]
        self.current_question = question

        options = [
            {"text": question["correct"], "is_correct": True},
            {"text": question["distractors"][0], "is_correct": False},
            {"text": question["distractors"][1], "is_correct": False},
        ]
        random.shuffle(options)

        spawn_y = 190
        lanes = [200, SCREEN_WIDTH // 2, SCREEN_WIDTH - 200]
        random.shuffle(lanes)
        base_speed = level["speed"]
        self.bubbles = []
        for idx, option in enumerate(options):
            self.bubbles.append(
                Bubble(
                    text=option["text"],
                    is_correct=option["is_correct"],
                    x=float(lanes[idx]),
                    y=float(spawn_y),
                    speed=base_speed + idx * 0.25,
                    wobble_seed=random.randint(0, 400),
                )
            )
        self.question_started_ms = pygame.time.get_ticks()

    def _draw(self, now_ms: int) -> None:
        self.screen.fill(COLORS["bg"])
        self._draw_background_panels()
        self._draw_header(now_ms)

        if self.state == "instructions":
            self._draw_instructions()
        elif self.state == "playing":
            self._draw_playfield(now_ms)
        elif self.state == "victory":
            self._draw_end_screen(True)
        elif self.state == "game_over":
            self._draw_end_screen(False)

    def _draw_background_panels(self) -> None:
        pygame.draw.rect(self.screen, COLORS["panel"], (16, 16, SCREEN_WIDTH - 32, SCREEN_HEIGHT - 32), border_radius=18)
        pygame.draw.rect(self.screen, COLORS["panel_alt"], (24, 24, SCREEN_WIDTH - 48, 120), border_radius=14)

    def _draw_header(self, now_ms: int) -> None:
        title = self.font_heading.render(self.title, True, COLORS["text"])
        self.screen.blit(title, (36, 36))

        progress = f"Level {min(self.level_index + 1, len(self.levels))}/{len(self.levels)}  |  Score {self.correct_answers}/{self.total_questions}"
        progress_surface = self.font_body.render(progress, True, COLORS["subtle"])
        self.screen.blit(progress_surface, (36, 74))

        lives_surface = self.font_body.render(f"Lives: {self.lives}", True, COLORS["warning"])
        self.screen.blit(lives_surface, (SCREEN_WIDTH - 190, 74))

        if self.state == "playing":
            elapsed = now_ms - self.question_started_ms
            remaining_ms = max(0, QUESTION_TIME_LIMIT_MS - elapsed)
            seconds = remaining_ms // 1000 + 1
            timer_surface = self.font_small.render(f"Timer: {seconds}s", True, COLORS["text"])
            self.screen.blit(timer_surface, (SCREEN_WIDTH - 170, 40))

    def _draw_instructions(self) -> None:
        heading = self.font_title.render("How To Play", True, COLORS["accent"])
        self.screen.blit(heading, (SCREEN_WIDTH // 2 - heading.get_width() // 2, 190))

        y = 280
        theme = self.font_body.render(self.spec["theme"], True, COLORS["text"])
        self.screen.blit(theme, (SCREEN_WIDTH // 2 - theme.get_width() // 2, y))
        y += 58

        for instruction in self.spec["instructions"]:
            for line in wrap_text(instruction, self.font_body, 860):
                text = self.font_body.render(f"- {line}", True, COLORS["subtle"])
                self.screen.blit(text, (130, y))
                y += 34
            y += 6

        prompt = self.font_body.render("Press SPACE / ENTER or Left Click to start", True, COLORS["success"])
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT - 120))

    def _draw_playfield(self, now_ms: int) -> None:
        field_top = 150
        pygame.draw.rect(self.screen, (18, 24, 38), (48, field_top, SCREEN_WIDTH - 96, SCREEN_HEIGHT - 220), border_radius=14)

        prompt = self.current_question.get("prompt", "")
        y = 170
        for line in wrap_text(prompt, self.font_body, 920):
            text = self.font_body.render(line, True, COLORS["text"])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 30

        if now_ms < self.feedback_until_ms:
            feedback_lines = wrap_text(self.feedback_text, self.font_small, 900)
            fy = y + 8
            for line in feedback_lines[:2]:
                text = self.font_small.render(line, True, self.feedback_color)
                self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, fy))
                fy += 24

        for bubble in self.bubbles:
            color = COLORS["correct"] if bubble.is_correct else COLORS["wrong"]
            pygame.draw.circle(self.screen, color, (int(bubble.x), int(bubble.y)), BUBBLE_RADIUS)
            pygame.draw.circle(self.screen, COLORS["text"], (int(bubble.x), int(bubble.y)), BUBBLE_RADIUS, width=2)
            lines = wrap_text(bubble.text, self.font_small, 140)
            text_y = int(bubble.y - (len(lines) * 16) / 2)
            for line in lines[:3]:
                text_surface = self.font_small.render(line, True, COLORS["bg"])
                self.screen.blit(text_surface, (int(bubble.x - text_surface.get_width() / 2), text_y))
                text_y += 16

        pygame.draw.rect(self.screen, COLORS["player"], self.player, border_radius=9)
        player_text = self.font_small.render("YOU", True, COLORS["bg"])
        self.screen.blit(
            player_text,
            (self.player.centerx - player_text.get_width() // 2, self.player.centery - player_text.get_height() // 2),
        )

        controls = self.font_small.render("Move: Arrow keys or A/D | ESC: End game", True, COLORS["subtle"])
        self.screen.blit(controls, (58, SCREEN_HEIGHT - 44))

    def _draw_end_screen(self, is_victory: bool) -> None:
        heading_text = "Level Mastered!" if is_victory else "Game Over"
        heading_color = COLORS["success"] if is_victory else COLORS["danger"]
        heading = self.font_title.render(heading_text, True, heading_color)
        self.screen.blit(heading, (SCREEN_WIDTH // 2 - heading.get_width() // 2, 210))

        summary = f"Final Score: {self.correct_answers}/{self.total_questions}"
        summary_surface = self.font_heading.render(summary, True, COLORS["text"])
        self.screen.blit(summary_surface, (SCREEN_WIDTH // 2 - summary_surface.get_width() // 2, 300))

        if not is_victory and self.game_over_reason:
            reason = self.font_body.render(self.game_over_reason, True, COLORS["subtle"])
            self.screen.blit(reason, (SCREEN_WIDTH // 2 - reason.get_width() // 2, 350))

        prompt = self.font_body.render("Press R or Left Click to restart, ESC to exit", True, COLORS["subtle"])
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 430))

    def _restart(self) -> None:
        self.level_index = 0
        self.question_index = 0
        self.correct_answers = 0
        self.lives = 3
        self.state = "instructions"
        self.feedback_text = ""
        self.feedback_until_ms = 0
        self.level_banner_until_ms = 0
        self.game_over_reason = ""
        self._start_level()


def normalize_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        spec = {}

    merged = dict(DEFAULT_SPEC)
    merged["title"] = clip_text(spec.get("title") or DEFAULT_SPEC["title"], 80)
    merged["theme"] = clip_text(spec.get("theme") or DEFAULT_SPEC["theme"], 200)

    instructions = spec.get("instructions") or DEFAULT_SPEC["instructions"]
    if not isinstance(instructions, list):
        instructions = DEFAULT_SPEC["instructions"]
    merged["instructions"] = [clip_text(str(item), 140) for item in instructions[:5] if str(item).strip()]
    if len(merged["instructions"]) < 3:
        merged["instructions"] = DEFAULT_SPEC["instructions"]

    levels = _normalize_levels(spec.get("levels"))
    merged["levels"] = levels[:MAX_LEVELS] if levels else DEFAULT_SPEC["levels"]
    return merged


def _normalize_levels(raw_levels) -> List[dict]:
    if not isinstance(raw_levels, list):
        return []
    normalized = []
    for idx, raw_level in enumerate(raw_levels[:MAX_LEVELS], start=1):
        if not isinstance(raw_level, dict):
            continue
        questions = _normalize_questions(raw_level.get("question_pool") or raw_level.get("questions"))
        if not questions:
            continue

        name = clip_text(raw_level.get("name") or f"Level {idx}", 42)
        goal = clip_text(raw_level.get("learning_goal") or "Strengthen concept recall.", 120)
        speed = safe_float(raw_level.get("speed"), default=2.0 + idx * 0.5, low=1.5, high=4.5)
        to_clear = safe_int(raw_level.get("questions_to_clear"), default=min(len(questions), 4), low=1, high=len(questions))

        normalized.append(
            {
                "name": name,
                "learning_goal": goal,
                "speed": speed,
                "questions_to_clear": min(to_clear, MAX_QUESTIONS_PER_LEVEL),
                "question_pool": questions[:MAX_QUESTIONS_PER_LEVEL],
            }
        )
    return normalized


def _normalize_questions(raw_questions) -> List[dict]:
    if not isinstance(raw_questions, list):
        return []
    out = []
    for raw in raw_questions:
        if not isinstance(raw, dict):
            continue
        prompt = clip_text(raw.get("prompt") or "", 120)
        correct = clip_text(raw.get("correct") or "", 60)
        distractors = raw.get("distractors") if isinstance(raw.get("distractors"), list) else []
        cleaned = [clip_text(str(item), 60) for item in distractors if str(item).strip()]
        cleaned = [item for item in cleaned if item.lower() != correct.lower()]
        while len(cleaned) < 2:
            cleaned.append(f"Incorrect option {len(cleaned) + 1}")
        explanation = clip_text(raw.get("explanation") or f"The correct answer is: {correct}.", 140)
        if prompt and correct:
            out.append(
                {
                    "prompt": prompt,
                    "correct": correct,
                    "distractors": cleaned[:2],
                    "explanation": explanation,
                }
            )
    return out


def clip_text(value, max_len: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def safe_int(value, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def safe_float(value, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def run_game_from_spec(spec: dict) -> int:
    game = QuizRunnerGame(spec or {})
    return game.run()
