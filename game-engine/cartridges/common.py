"""
Shared helpers for deterministic educational cartridges.
"""

from __future__ import annotations

import random
from typing import Dict, List

import pygame


SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 720
FPS = 60
MAX_LEVELS = 3
MAX_QUESTIONS_PER_LEVEL = 6


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


def normalize_questions(raw_questions) -> List[dict]:
    if not isinstance(raw_questions, list):
        return []
    out = []
    for raw in raw_questions:
        if not isinstance(raw, dict):
            continue
        prompt = clip_text(raw.get("prompt") or "", 120)
        correct = clip_text(raw.get("correct") or "", 70)
        distractors = raw.get("distractors") if isinstance(raw.get("distractors"), list) else []
        cleaned = [clip_text(str(item), 70) for item in distractors if str(item).strip()]
        cleaned = [item for item in cleaned if item.lower() != correct.lower()]
        while len(cleaned) < 2:
            cleaned.append(f"Incorrect option {len(cleaned) + 1}")
        explanation = clip_text(raw.get("explanation") or f"The correct answer is: {correct}.", 160)
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


def normalize_levels(raw_levels) -> List[dict]:
    if not isinstance(raw_levels, list):
        return []
    normalized = []
    for idx, raw_level in enumerate(raw_levels[:MAX_LEVELS], start=1):
        if not isinstance(raw_level, dict):
            continue
        questions = normalize_questions(raw_level.get("question_pool") or raw_level.get("questions"))
        if not questions:
            continue

        name = clip_text(raw_level.get("name") or f"Level {idx}", 44)
        goal = clip_text(raw_level.get("learning_goal") or "Strengthen concept recall.", 140)
        speed = safe_float(raw_level.get("speed"), default=2.0 + idx * 0.45, low=1.2, high=6.0)
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


def normalize_spec(spec: dict, default_spec: dict) -> dict:
    if not isinstance(spec, dict):
        spec = {}

    merged = dict(default_spec)
    merged["title"] = clip_text(spec.get("title") or default_spec.get("title") or "Learning Challenge", 88)
    merged["theme"] = clip_text(spec.get("theme") or default_spec.get("theme") or "", 220)
    merged["style_variant"] = clip_text(spec.get("style_variant") or default_spec.get("style_variant") or "default", 40)

    instructions = spec.get("instructions") or default_spec.get("instructions") or []
    if not isinstance(instructions, list):
        instructions = default_spec.get("instructions") or []
    merged["instructions"] = [clip_text(item, 150) for item in instructions[:6] if clip_text(item, 150)]
    if len(merged["instructions"]) < 3:
        merged["instructions"] = list(default_spec.get("instructions") or [])

    levels = normalize_levels(spec.get("levels"))
    merged["levels"] = levels[:MAX_LEVELS] if levels else list(default_spec.get("levels") or [])

    return merged


def pick_question(level: Dict, index: int) -> Dict:
    pool = level.get("question_pool") if isinstance(level.get("question_pool"), list) else []
    if not pool:
        return {
            "prompt": "Placeholder prompt",
            "correct": "Correct",
            "distractors": ["Wrong A", "Wrong B"],
            "explanation": "No question data found in this level.",
        }
    return pool[index % len(pool)]


def make_stars(count: int, seed: int = 42) -> List[dict]:
    random.seed(seed)
    stars = []
    for _ in range(count):
        stars.append(
            {
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(0, SCREEN_HEIGHT),
                "radius": random.uniform(0.8, 2.4),
                "speed": random.uniform(0.2, 1.2),
            }
        )
    return stars


def draw_stars(surface: pygame.Surface, stars: List[dict], color=(180, 198, 240)) -> None:
    for star in stars:
        pygame.draw.circle(surface, color, (int(star["x"]), int(star["y"])), int(star["radius"]))
        star["y"] += star["speed"]
        if star["y"] > SCREEN_HEIGHT + 2:
            star["y"] = -2
            star["x"] = random.uniform(0, SCREEN_WIDTH)


def draw_instruction_block(
    screen: pygame.Surface,
    font_title: pygame.font.Font,
    font_body: pygame.font.Font,
    font_small: pygame.font.Font,
    title: str,
    theme: str,
    instructions: List[str],
    accent=(96, 184, 255),
    text=(236, 241, 252),
    subtle=(161, 174, 209),
) -> None:
    heading = font_title.render("How To Play", True, accent)
    screen.blit(heading, (SCREEN_WIDTH // 2 - heading.get_width() // 2, 164))

    topic = font_body.render(title, True, text)
    screen.blit(topic, (SCREEN_WIDTH // 2 - topic.get_width() // 2, 226))

    y = 274
    for line in wrap_text(theme, font_body, 880):
        text_surface = font_body.render(line, True, subtle)
        screen.blit(text_surface, (SCREEN_WIDTH // 2 - text_surface.get_width() // 2, y))
        y += 30

    y += 20
    for instruction in instructions:
        for row in wrap_text(instruction, font_small, 860):
            row_surface = font_small.render(f"- {row}", True, text)
            screen.blit(row_surface, (120, y))
            y += 30
        y += 4

    prompt = font_body.render("Press SPACE / ENTER or Left Click to start", True, accent)
    screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT - 96))

