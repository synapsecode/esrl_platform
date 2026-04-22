import unittest

from cartridge_builder import (
    build_cartridge_game_code,
    cartridge_catalog_for_prompt,
    extract_json_payload,
    select_best_cartridge,
)
from cartridges.catalog import list_cartridges
from quality_harness import GameQualityHarness


class GenerationQualityTests(unittest.TestCase):
    def test_extract_json_payload_from_embedded_block(self):
        raw = "Here is output:\n```json\n{\"title\":\"T\",\"levels\":[]}\n```"
        parsed = extract_json_payload(raw)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("title"), "T")

    def test_catalog_contains_at_least_ten_cartridges(self):
        self.assertGreaterEqual(len(list_cartridges()), 10)

    def test_build_cartridge_game_code_contains_dynamic_runtime_import(self):
        code = build_cartridge_game_code({"title": "Demo", "levels": []})
        self.assertIn("from cartridges.quiz_runner import run_game_from_spec", code)
        self.assertIn("Auto-generated eSRL PyGame.", code)

        lane_code = build_cartridge_game_code({"title": "Demo", "levels": []}, cartridge_name="lane_sort_lab_v1")
        self.assertIn("from cartridges.lane_sort_runner import run_game_from_spec", lane_code)

    def test_selector_falls_back_to_none_for_low_signal(self):
        selection = select_best_cartridge(
            study_notes="abstract narrative with no clear educational structure",
            game_design="minimal concept",
            level_design="",
            llm_selection={"selected_cartridge": "none", "confidence": 0.1, "reason": "low fit"},
        )
        self.assertIn("selected_cartridge", selection)
        self.assertIn(selection["selected_cartridge"], {"none", "concept_sprint_v2"})

    def test_selector_accepts_high_confidence_llm_recommendation(self):
        selection = select_best_cartridge(
            study_notes="proof theorem derivation constraint",
            game_design="formal rule checks",
            level_design="",
            llm_selection={"selected_cartridge": "theorem_turret_v1", "confidence": 0.91, "reason": "strong fit"},
        )
        self.assertEqual(selection["selected_cartridge"], "theorem_turret_v1")
        self.assertEqual(selection["selection_mode"], "llm")

    def test_catalog_for_prompt_has_prompt_hint(self):
        catalog = cartridge_catalog_for_prompt()
        self.assertGreaterEqual(len(catalog), 10)
        self.assertTrue(all("prompt_hint" in item for item in catalog))

    def test_quality_harness_static_checks_pass_for_cartridge_wrapper(self):
        harness = GameQualityHarness()
        code = build_cartridge_game_code(
            {
                "title": "Demo",
                "instructions": ["Move", "Catch right option", "Avoid wrong option"],
                "levels": [
                    {
                        "name": "L1",
                        "learning_goal": "Goal",
                        "speed": 2.0,
                        "questions_to_clear": 1,
                        "question_pool": [
                            {
                                "prompt": "Q1",
                                "correct": "A",
                                "distractors": ["B", "C"],
                                "explanation": "A is correct.",
                            }
                        ],
                    }
                ],
            }
        )
        report = harness.run(
            code=code,
            game_file="pygames/_unit_test_game.py",
            run_runtime=False,
        )
        report_dict = report.to_dict()
        self.assertTrue(report_dict.get("passed"))
        failed = [check for check in report_dict.get("checks", []) if not check.get("passed")]
        self.assertEqual(failed, [])

    def test_quality_harness_loads_non_default_cartridge_source(self):
        harness = GameQualityHarness()
        code = build_cartridge_game_code({"title": "Lane", "levels": []}, cartridge_name="lane_sort_lab_v1")
        report = harness.run(code=code, game_file="pygames/_unit_test_lane.py", run_runtime=False).to_dict()
        self.assertTrue(report.get("passed"))
        names = [check.get("name") for check in report.get("checks", [])]
        self.assertIn("cartridge_source_loaded", names)


if __name__ == "__main__":
    unittest.main()
