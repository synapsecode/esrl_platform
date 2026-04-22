"""
Cartridge catalog and heuristic ranking logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CartridgeDefinition:
    cartridge_id: str
    display_name: str
    module: str
    mechanic: str
    summary: str
    keywords: List[str]
    best_for: List[str]
    prompt_hint: str

    def to_dict(self) -> Dict:
        return asdict(self)


CATALOG: List[CartridgeDefinition] = [
    CartridgeDefinition(
        cartridge_id="concept_sprint_v2",
        display_name="Concept Sprint",
        module="quiz_runner",
        mechanic="falling catch",
        summary="Catch the correct answer orb while avoiding misconceptions.",
        keywords=["definition", "recall", "terminology", "vocabulary", "concept", "meaning"],
        best_for=["foundational recall", "term-definition mapping", "quick concept checks"],
        prompt_hint="Generate concise options with clear contrasts between correct and incorrect ideas.",
    ),
    CartridgeDefinition(
        cartridge_id="misconception_meteor_v1",
        display_name="Misconception Meteor",
        module="quiz_runner",
        mechanic="falling catch",
        summary="Fast-paced misconception filtering with stronger distractors.",
        keywords=["misconception", "myth", "common mistake", "error", "pitfall", "wrong"],
        best_for=["misconception correction", "error spotting", "exam prep traps"],
        prompt_hint="Use distractors that resemble common mistakes and add short corrective explanations.",
    ),
    CartridgeDefinition(
        cartridge_id="lane_sort_lab_v1",
        display_name="Lane Sort Lab",
        module="lane_sort_runner",
        mechanic="lane routing",
        summary="Route through correct answer lanes under time pressure.",
        keywords=["classify", "categorize", "taxonomy", "group", "type", "bucket"],
        best_for=["classification tasks", "binary/ternary sorting", "category learning"],
        prompt_hint="Questions should emphasize choosing the right category among plausible alternatives.",
    ),
    CartridgeDefinition(
        cartridge_id="category_cascade_v1",
        display_name="Category Cascade",
        module="lane_sort_runner",
        mechanic="lane routing",
        summary="High-tempo category gates with progressive difficulty.",
        keywords=["classification", "sorting", "identify", "label", "distinguish", "compare"],
        best_for=["distinguishing similar concepts", "rapid categorization", "pattern recognition"],
        prompt_hint="Include close alternatives so category boundaries become explicit.",
    ),
    CartridgeDefinition(
        cartridge_id="orbit_hunt_v1",
        display_name="Orbit Hunt",
        module="orbit_hunt_runner",
        mechanic="cursor targeting",
        summary="Track moving concept nodes and lock onto the valid answer.",
        keywords=["cycle", "orbit", "rotation", "process", "dynamic", "motion"],
        best_for=["cyclic processes", "dynamic systems", "tracking relationships"],
        prompt_hint="Use action-oriented prompts with compact options that are easy to parse quickly.",
    ),
    CartridgeDefinition(
        cartridge_id="signal_chase_v1",
        display_name="Signal Chase",
        module="orbit_hunt_runner",
        mechanic="cursor targeting",
        summary="Precision targeting of correct conceptual signals.",
        keywords=["signal", "noise", "detection", "identify", "filter", "selection"],
        best_for=["signal-vs-noise training", "critical reading", "evidence selection"],
        prompt_hint="Create one strong evidence-backed option and two tempting but flawed options.",
    ),
    CartridgeDefinition(
        cartridge_id="memory_matrix_v1",
        display_name="Memory Matrix",
        module="memory_matrix_runner",
        mechanic="grid reveal",
        summary="Navigate a card matrix to reveal the correct concept.",
        keywords=["memory", "recall", "flashcard", "remember", "fact", "association"],
        best_for=["retrieval practice", "vocabulary reinforcement", "concept association"],
        prompt_hint="Keep options short and memorable for rapid matrix scanning.",
    ),
    CartridgeDefinition(
        cartridge_id="flash_grid_v1",
        display_name="Flash Grid",
        module="memory_matrix_runner",
        mechanic="grid reveal",
        summary="Fast card reveal game focused on conceptual precision.",
        keywords=["flash", "drill", "practice", "repeat", "quick check", "retention"],
        best_for=["drill sessions", "high-frequency reinforcement", "short study bursts"],
        prompt_hint="Use high-value facts and concise contrasts suitable for repeated practice.",
    ),
    CartridgeDefinition(
        cartridge_id="concept_defense_v1",
        display_name="Concept Defense",
        module="concept_defense_runner",
        mechanic="turret defense",
        summary="Defend a knowledge core by intercepting correct concept nodes.",
        keywords=["theory", "law", "principle", "proof", "equation", "formula"],
        best_for=["STEM concepts", "law/principle recall", "high-pressure identification"],
        prompt_hint="Prompts should test exactness of principles and precision of language.",
    ),
    CartridgeDefinition(
        cartridge_id="sequence_sprint_v1",
        display_name="Sequence Sprint",
        module="sequence_sprint_runner",
        mechanic="sliding decision cards",
        summary="Choose the best next step in fast-moving conceptual sequences.",
        keywords=["sequence", "steps", "workflow", "pipeline", "procedure", "lifecycle"],
        best_for=["procedural understanding", "order-of-operations", "process reasoning"],
        prompt_hint="Focus prompts on next-best-step reasoning with realistic process distractors.",
    ),
    CartridgeDefinition(
        cartridge_id="theorem_turret_v1",
        display_name="Theorem Turret",
        module="concept_defense_runner",
        mechanic="turret defense",
        summary="Precision defense variant tuned for theorem/law statement accuracy.",
        keywords=["theorem", "axiom", "lemma", "proof", "derivation", "constraint"],
        best_for=["formal math/logic", "statement validation", "proof vocabulary"],
        prompt_hint="Use exact theorem and condition phrasing; distractors should be subtly incorrect.",
    ),
]


def list_cartridges() -> List[CartridgeDefinition]:
    return list(CATALOG)


def list_cartridges_dict() -> List[Dict]:
    return [item.to_dict() for item in CATALOG]


def get_cartridge(cartridge_id: str) -> Optional[CartridgeDefinition]:
    for item in CATALOG:
        if item.cartridge_id == cartridge_id:
            return item
    return None


def heuristic_rank_cartridges(study_notes: str, game_design: str = "", level_design: str = "") -> List[Dict]:
    text = " ".join([study_notes or "", game_design or "", level_design or ""]).lower()
    ranks: List[Dict] = []
    for item in CATALOG:
        score = 0.15
        for keyword in item.keywords:
            if keyword in text:
                score += 0.14
        if item.cartridge_id.endswith("_v1") and "beginner" in text:
            score += 0.04
        if "timeline" in text and "sequence" in item.keywords:
            score += 0.10
        if "formula" in text and item.module == "concept_defense_runner":
            score += 0.08
        if "classification" in text and item.module == "lane_sort_runner":
            score += 0.08
        if "memory" in text and item.module == "memory_matrix_runner":
            score += 0.08
        score = min(0.98, score)
        ranks.append(
            {
                "cartridge_id": item.cartridge_id,
                "score": round(score, 4),
                "mechanic": item.mechanic,
                "reason": f"Keyword alignment for {item.display_name}",
            }
        )
    ranks.sort(key=lambda row: row["score"], reverse=True)
    return ranks

