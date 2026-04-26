"""
Local Claude Code CLI client for eSRL agents.

Spawns the user's installed `claude` binary in headless print mode so the
existing Claude Code login is reused -- no ANTHROPIC_API_KEY needed.
"""

import os
import subprocess
import tempfile
import threading
import time
from typing import Optional


class ClaudeCLIClient:
    """Wrapper around the local `claude` CLI matching GeminiClient.generate()."""

    def __init__(
        self,
        model_name: str = "claude-opus-4-7",
        cli_path: Optional[str] = None,
        timeout: int = 1200,
    ):
        self.model_name = model_name
        self.cli_path = cli_path or os.getenv("CLAUDE_CLI_PATH", "claude")
        self.timeout = timeout

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        cmd = [
            self.cli_path,
            "-p",
            "--model", self.model_name,
            "--output-format", "text",
            # Skip user/project/local settings so per-machine hooks, memory
            # paths, and CLAUDE.md auto-discovery don't leak into the call.
            # (Cannot use --bare: it also disables OAuth/keychain reads,
            # which breaks authentication when the user is logged in via
            # `claude /login` rather than ANTHROPIC_API_KEY.)
            "--setting-sources", "",
            "--tools", "",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--permission-mode", "bypassPermissions",
        ]
        if system_instruction:
            cmd += ["--system-prompt", system_instruction]

        # Run with a heartbeat so long generations don't look frozen.
        stop_heartbeat = threading.Event()

        def _heartbeat():
            start = time.monotonic()
            # First tick after 15s, then every 15s.
            while not stop_heartbeat.wait(15):
                elapsed = int(time.monotonic() - start)
                print(
                    f"   ⏳ claude CLI working... {elapsed}s elapsed",
                    flush=True,
                )

        hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        hb_thread.start()

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                # Neutral cwd so the subprocess never picks up this repo's
                # CLAUDE.md (belt-and-suspenders alongside --setting-sources "").
                cwd=tempfile.gettempdir(),
            )
        except FileNotFoundError as exc:
            stop_heartbeat.set()
            raise RuntimeError(
                f"claude CLI not found at '{self.cli_path}'. "
                "Install Claude Code or set CLAUDE_CLI_PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            stop_heartbeat.set()
            raise RuntimeError(
                f"claude CLI timed out after {self.timeout}s"
            ) from exc
        finally:
            stop_heartbeat.set()
            hb_thread.join(timeout=1)

        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        return result.stdout
