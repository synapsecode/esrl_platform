"""
Quality harness for generated PyGame scripts.

This module provides deterministic checks so generation can fail fast when
output is not runnable or misses basic gameplay/runtime requirements.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class HarnessCheck:
    name: str
    passed: bool
    details: str
    critical: bool = False


@dataclass
class HarnessReport:
    passed: bool
    score: int
    checks: List[HarnessCheck]
    runtime: dict

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "checks": [asdict(check) for check in self.checks],
            "runtime": self.runtime,
        }


def sanitize_generated_code(code: str) -> str:
    """
    Remove markdown wrappers from model output and normalize whitespace.
    """
    cleaned = (code or "").replace("```python", "").replace("```", "").strip()
    if cleaned.startswith("python\n"):
        cleaned = cleaned[len("python\n") :]
    return cleaned


class GameQualityHarness:
    """
    Validates generated game scripts using static checks and runtime smoke tests.
    """

    STATIC_PATTERNS = [
        ("imports_pygame", re.compile(r"(^|\n)\s*(import pygame|from pygame)", re.MULTILINE), True),
        ("calls_pygame_init", re.compile(r"pygame\.init\s*\("), True),
        ("creates_display", re.compile(r"pygame\.display\.set_mode\s*\("), True),
        ("processes_events", re.compile(r"pygame\.event\.get\s*\("), True),
        ("handles_quit", re.compile(r"event\.type\s*==\s*pygame\.QUIT"), True),
        ("fps_control", re.compile(r"(pygame\.time\.Clock\s*\(|\.tick\s*\()"), True),
        ("has_instructional_ui", re.compile(r"(instruction|controls|press|how to play)", re.IGNORECASE), False),
        ("uses_allowed_input", re.compile(r"(K_LEFT|K_RIGHT|K_UP|K_DOWN|K_SPACE|K_w|K_a|K_s|K_d|MOUSEBUTTONDOWN)"), False),
    ]

    def run(
        self,
        code: str,
        game_file: str,
        python_path: Optional[str] = None,
        runtime_timeout_sec: int = 8,
        run_runtime: bool = True,
    ) -> HarnessReport:
        checks: List[HarnessCheck] = []
        runtime_report = {"executed": False}
        script = sanitize_generated_code(code)
        analysis_code = script

        cartridge_module = self._extract_cartridge_module(script)
        if cartridge_module:
            cartridge_code = self._load_cartridge_source(f"{cartridge_module}.py")
            if cartridge_code:
                analysis_code = f"{script}\n\n# cartridge_source\n{cartridge_code}"
                checks.append(
                    HarnessCheck(
                        name="cartridge_source_loaded",
                        passed=True,
                        details=f"Loaded shared cartridge source ({cartridge_module}) for static checks",
                        critical=False,
                    )
                )
            else:
                checks.append(
                    HarnessCheck(
                        name="cartridge_source_loaded",
                        passed=False,
                        details=f"Cartridge wrapper detected but source ({cartridge_module}) could not be loaded",
                        critical=True,
                    )
                )

        checks.append(self._syntax_check(script, game_file))
        checks.extend(self._static_checks(analysis_code))
        checks.extend(self._size_checks(analysis_code))

        if run_runtime:
            runtime_report = self._runtime_smoke_test(
                game_file=game_file,
                python_path=python_path,
                timeout_sec=runtime_timeout_sec,
            )
            checks.append(
                HarnessCheck(
                    name="runtime_smoke_test",
                    passed=runtime_report.get("passed", False),
                    details=runtime_report.get("details", "Runtime test not executed"),
                    critical=True,
                )
            )

        score = self._score(checks)
        all_critical_passed = all(check.passed for check in checks if check.critical)
        passed = all_critical_passed and score >= 70
        return HarnessReport(passed=passed, score=score, checks=checks, runtime=runtime_report)

    def _syntax_check(self, code: str, game_file: str) -> HarnessCheck:
        try:
            ast.parse(code, filename=game_file)
            compile(code, game_file, "exec")
            return HarnessCheck(
                name="syntax_compile",
                passed=True,
                details="Python AST parse and compile succeeded",
                critical=True,
            )
        except Exception as exc:  # pragma: no cover - defensive, surfaced in report
            return HarnessCheck(
                name="syntax_compile",
                passed=False,
                details=f"Syntax/compile failed: {exc}",
                critical=True,
            )

    def _static_checks(self, code: str) -> List[HarnessCheck]:
        static_checks: List[HarnessCheck] = []
        for name, pattern, critical in self.STATIC_PATTERNS:
            matched = bool(pattern.search(code))
            static_checks.append(
                HarnessCheck(
                    name=name,
                    passed=matched,
                    details="Found required pattern" if matched else "Required pattern missing",
                    critical=critical,
                )
            )
        return static_checks

    def _size_checks(self, code: str) -> List[HarnessCheck]:
        lines = code.count("\n") + 1
        checks = [
            HarnessCheck(
                name="line_count_minimum",
                passed=lines >= 80,
                details=f"Line count: {lines} (expected at least 80 for playable game)",
                critical=False,
            ),
            HarnessCheck(
                name="line_count_maximum",
                passed=lines <= 1500,
                details=f"Line count: {lines} (expected <= 1500 for maintainability)",
                critical=False,
            ),
        ]
        return checks

    def _runtime_smoke_test(self, game_file: str, python_path: Optional[str], timeout_sec: int) -> dict:
        runtime_report = {
            "executed": True,
            "passed": False,
            "details": "",
            "exit_code": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "timeout_sec": timeout_sec,
        }

        executable = os.path.abspath(python_path) if python_path else sys.executable
        abs_game_file = os.path.abspath(game_file)
        env = os.environ.copy()
        env["SDL_VIDEODRIVER"] = env.get("SDL_VIDEODRIVER", "dummy")
        env["SDL_AUDIODRIVER"] = env.get("SDL_AUDIODRIVER", "dummy")
        env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        env["ESRL_SMOKE_TEST_MODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            [executable, abs_game_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(abs_game_file),
            env=env,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
            runtime_report["exit_code"] = process.returncode
            runtime_report["stdout_tail"] = _last_lines(stdout)
            runtime_report["stderr_tail"] = _last_lines(stderr)
            if process.returncode == 0:
                runtime_report["passed"] = True
                runtime_report["details"] = "Game exited cleanly during smoke window"
            else:
                runtime_report["details"] = f"Game crashed with exit code {process.returncode}"
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            runtime_report["stdout_tail"] = _last_lines(stdout)
            runtime_report["stderr_tail"] = _last_lines(stderr)
            runtime_report["passed"] = True
            runtime_report["details"] = "Game stayed alive through smoke window"
        except Exception as exc:  # pragma: no cover - defensive
            runtime_report["details"] = f"Runtime smoke test failed to execute: {exc}"

        return runtime_report

    def _score(self, checks: List[HarnessCheck]) -> int:
        score = 100
        for check in checks:
            if check.passed:
                continue
            score -= 25 if check.critical else 10
        return max(0, min(100, score))

    def _load_cartridge_source(self, filename: str) -> Optional[str]:
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(module_dir, "cartridges", filename)
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception:
            return None

    def _extract_cartridge_module(self, code: str) -> Optional[str]:
        match = re.search(r"from\s+cartridges\.([a-zA-Z0-9_]+)\s+import\s+run_game_from_spec", code)
        if not match:
            return None
        return match.group(1)


def _last_lines(text: str, keep: int = 10) -> str:
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-keep:])
