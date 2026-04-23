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
        cartridge_id="orbit_attract_v1",
        display_name="Orbit & Attract",
        module="orbit_attract_runner",
        mechanic="gravity routing",
        summary="Move a gravity cursor to pull correct concepts into a target zone and repel wrong ones.",
        keywords=["sorting", "matching", "categorization", "gravity", "attract", "repel", "space"],
        best_for=["category learning", "signal routing", "dynamic discrimination"],
        prompt_hint="Use concise contrasting options with one precise target concept and two misleading alternatives.",
    ),
    CartridgeDefinition(
        cartridge_id="conveyor_rush_v1",
        display_name="Conveyor Rush",
        module="conveyor_rush_runner",
        mechanic="real-time sorting",
        summary="Sort incoming items into bins under speed pressure.",
        keywords=["grammar", "classification", "era", "species", "operation", "sort", "bin"],
        best_for=["rule application", "classification drills", "rapid sorting"],
        prompt_hint="Make bin options explicit categories and prompts short enough for quick decisions.",
    ),
    CartridgeDefinition(
        cartridge_id="blueprint_builder_v1",
        display_name="Blueprint Builder",
        module="blueprint_builder_runner",
        mechanic="system reconstruction",
        summary="Place and connect concept tiles to reconstruct a coherent system.",
        keywords=["system", "timeline", "chain", "circuit", "structure", "connect", "reconstruct"],
        best_for=["concept mapping", "systems thinking", "structured reasoning"],
        prompt_hint="Design each step as a structural decision where only one tile keeps the model coherent.",
    ),
    CartridgeDefinition(
        cartridge_id="the_dig_v1",
        display_name="The Dig",
        module="dig_grid_runner",
        mechanic="grid excavation",
        summary="Excavate tiles to uncover the key concept fragment.",
        keywords=["map", "process", "story", "fragment", "discover", "grid", "excavate"],
        best_for=["discovery learning", "process reconstruction", "detail identification"],
        prompt_hint="Frame options as plausible fragments, with one key fragment that unlocks understanding.",
    ),
    CartridgeDefinition(
        cartridge_id="signal_noise_v1",
        display_name="Signal & Noise",
        module="signal_noise_runner",
        mechanic="filter beam",
        summary="Hold filter to capture valid items while letting noise pass.",
        keywords=["pattern", "exception", "filter", "noise", "signal", "recognition", "stream"],
        best_for=["pattern recognition", "exception handling", "precision filtering"],
        prompt_hint="Use one valid pattern item and two near-miss distractors that tempt over-filtering.",
    ),
    CartridgeDefinition(
        cartridge_id="territory_wars_v1",
        display_name="Territory Wars",
        module="territory_wars_runner",
        mechanic="turn-based grid control",
        summary="Answer correctly to claim territory on a strategic grid.",
        keywords=["strategy", "territory", "grid", "turn", "competition", "claim", "control"],
        best_for=["reasoning under pressure", "turn-based learning", "competitive review"],
        prompt_hint="Make each turn decision meaningful; incorrect reasoning should clearly lose strategic ground.",
    ),
    CartridgeDefinition(
        cartridge_id="chain_reaction_v1",
        display_name="Chain Reaction",
        module="chain_reaction_runner",
        mechanic="causal redirect",
        summary="Redirect a spreading chain before it hits faulty nodes.",
        keywords=["cause", "effect", "sequence", "logic", "flow", "dependency", "pipeline"],
        best_for=["causal reasoning", "algorithmic flow", "process logic"],
        prompt_hint="Set up clear cause-effect branches where one path preserves validity and others break it.",
    ),
    CartridgeDefinition(
        cartridge_id="negotiation_floor_v1",
        display_name="Negotiation Floor",
        module="negotiation_floor_runner",
        mechanic="relational pairing",
        summary="Match relational pairs across two changing columns.",
        keywords=["pair", "bond", "match", "cause-effect", "equation", "vocab", "relation"],
        best_for=["relational thinking", "matching tasks", "association building"],
        prompt_hint="Pairs should require semantic relation, not superficial text matching.",
    ),
    CartridgeDefinition(
        cartridge_id="pressure_drop_v1",
        display_name="Pressure Drop",
        module="pressure_drop_runner",
        mechanic="catch and dodge",
        summary="Catch valid falling items and dodge invalid ones.",
        keywords=["catch", "prime", "tense", "operation", "drop", "platform", "dodge"],
        best_for=["fast rule checks", "accuracy under pressure", "timed retrieval"],
        prompt_hint="Use compact labels that can be parsed mid-fall, with sharply contrasted distractors.",
    ),
    CartridgeDefinition(
        cartridge_id="fault_lines_v1",
        display_name="Fault Lines",
        module="fault_lines_runner",
        mechanic="error localization",
        summary="Identify the exact segment containing the error or logic break.",
        keywords=["debug", "grammar", "proof", "argument", "error", "fault", "segment"],
        best_for=["debugging", "error spotting", "critical reading"],
        prompt_hint="Construct segment sets with one precise fault and two plausible non-fault alternatives.",
    ),
    CartridgeDefinition(
        cartridge_id="wave_resonance_v1",
        display_name="The Wave",
        module="wave_resonance_runner",
        mechanic="proximity resonance",
        summary="Resonance fills near correct concepts and drains near wrong ones while moving to goal.",
        keywords=["resonance", "proximity", "landscape", "meter", "signal", "distance", "field"],
        best_for=["concept affinity", "subtle discrimination", "context sensitivity"],
        prompt_hint="Provide beacons with nuanced distinctions so proximity choice reflects true understanding.",
    ),
    CartridgeDefinition(
        cartridge_id="stack_collapse_v1",
        display_name="Stack & Collapse",
        module="stack_collapse_runner",
        mechanic="column stability",
        summary="Place falling blocks into correct semantic columns to avoid structural collapse.",
        keywords=["stack", "hierarchy", "equation", "sentence", "structure", "collapse", "placement"],
        best_for=["hierarchical organization", "structural reasoning", "column classification"],
        prompt_hint="Each placement should represent a structural decision with clear stability consequences.",
    ),
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
        score = 0.08
        for keyword in item.keywords:
            if keyword in text:
                score += 0.13

        if item.cartridge_id.endswith("_v1") and "beginner" in text:
            score += 0.03
        if "timeline" in text and "sequence" in item.keywords:
            score += 0.12
        if "proof" in text and item.module in {"concept_defense_runner", "fault_lines_runner"}:
            score += 0.10
        if "classification" in text and item.module in {"lane_sort_runner", "conveyor_rush_runner"}:
            score += 0.10
        if "map" in text and item.module in {"blueprint_builder_runner", "dig_grid_runner"}:
            score += 0.10
        if "debug" in text and item.module in {"fault_lines_runner", "chain_reaction_runner"}:
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
