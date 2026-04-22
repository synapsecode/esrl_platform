import unittest

from cartridge_builder import build_cartridge_game_code, extract_json_payload
from quality_harness import GameQualityHarness


class GenerationQualityTests(unittest.TestCase):
    def test_extract_json_payload_from_embedded_block(self):
        raw = "Here is output:\n```json\n{\"title\":\"T\",\"levels\":[]}\n```"
        parsed = extract_json_payload(raw)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("title"), "T")

    def test_build_cartridge_game_code_contains_shared_runtime_import(self):
        code = build_cartridge_game_code({"title": "Demo", "levels": []})
        self.assertIn("from cartridges.quiz_runner import run_game_from_spec", code)
        self.assertIn("Auto-generated eSRL PyGame.", code)

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


if __name__ == "__main__":
    unittest.main()

