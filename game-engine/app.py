import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents import (
    cartridge_spec_agent,
    cartridge_selection_agent,
    code_generation_agent,
    code_repair_agent,
    game_design_agent,
    level_design_agent,
)
from cartridge_builder import (
    build_cartridge_game_code,
    cartridge_catalog_for_prompt,
    build_design_summary,
    build_level_summary,
    extract_json_payload,
    select_best_cartridge,
)
from cartridges.catalog import get_cartridge
from quality_harness import GameQualityHarness, sanitize_generated_code

app = FastAPI(title="eSRL Game Generator")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

generation_status: Dict[str, Dict] = {}
status_lock = threading.Lock()
MAX_TASK_HISTORY = int(os.getenv("MAX_TASK_HISTORY", "200"))
MAX_CODE_ATTEMPTS = int(os.getenv("MAX_CODE_ATTEMPTS", "3"))
SMOKE_TEST_TIMEOUT_SEC = int(os.getenv("SMOKE_TEST_TIMEOUT_SEC", "8"))
ENABLE_CARTRIDGE_PIPELINE = os.getenv("ENABLE_CARTRIDGE_PIPELINE", "1") != "0"
ENABLE_RUNTIME_SMOKE_TEST = os.getenv("ENABLE_RUNTIME_SMOKE_TEST", "1") != "0"

class GameRequest(BaseModel):
    study_notes: str


def _set_task(task_id: str, **updates):
    with status_lock:
        if task_id in generation_status:
            generation_status[task_id].update(updates)


def _get_task(task_id: str) -> Optional[Dict]:
    with status_lock:
        task = generation_status.get(task_id)
        return dict(task) if task else None


def _put_task(task_id: str, payload: Dict):
    with status_lock:
        generation_status[task_id] = payload


def _task_items_snapshot():
    with status_lock:
        return list(generation_status.items())


def _prune_history():
    with status_lock:
        if len(generation_status) <= MAX_TASK_HISTORY:
            return
        ordered = sorted(
            generation_status.items(),
            key=lambda item: (item[1].get("created_at") or "", item[0]),
            reverse=True,
        )
        retained = dict(ordered[:MAX_TASK_HISTORY])
        generation_status.clear()
        generation_status.update(retained)


def _resolve_python_path() -> str:
    venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
    return venv_python if os.path.exists(venv_python) else sys.executable


def _write_game_file(path: str, code: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(code)


def _complete_task(
    task_id: str,
    game_file: str,
    code: str,
    game_design: str,
    level_design: str,
    generation_mode: str,
    quality_report: dict,
    validation_history: list,
    fallback_reason: str = "",
    selected_cartridge: str = "",
    cartridge_selection: Optional[dict] = None,
) -> None:
    _set_task(
        task_id,
        status="completed",
        phase="Complete",
        game_file=game_file,
        code=code,
        game_design=game_design,
        level_design=level_design,
        generation_mode=generation_mode,
        selected_cartridge=selected_cartridge,
        cartridge_selection=cartridge_selection or {},
        quality_report=quality_report,
        validation_history=validation_history,
        fallback_reason=fallback_reason,
        completed_at=datetime.now().isoformat(),
    )


def _error_summary(report: dict) -> str:
    checks = report.get("checks") if isinstance(report, dict) else []
    failed = [check for check in checks if not check.get("passed")]
    if not failed:
        return "validation failed with unknown reason"
    first = failed[0]
    return f"{first.get('name')}: {first.get('details')}"


def run_game_generation(task_id: str, study_notes: str):
    try:
        harness = GameQualityHarness()
        python_path = _resolve_python_path()
        os.makedirs("pygames", exist_ok=True)
        game_file = f"pygames/game_{task_id}.py"

        _set_task(task_id, status="generating_design", phase="Game Design (1/8)")
        game_design = game_design_agent.run(study_notes)
        _set_task(task_id, game_design=game_design)

        _set_task(task_id, status="generating_levels", phase="Level Design (2/8)")
        level_design = level_design_agent.run(game_design)
        _set_task(task_id, level_design=level_design)

        validation_history = []
        fallback_reason = ""
        selected_cartridge = ""
        cartridge_selection: Dict = {}

        if ENABLE_CARTRIDGE_PIPELINE:
            catalog = cartridge_catalog_for_prompt()
            _set_task(
                task_id,
                status="selecting_cartridge",
                phase="Cartridge Selection (3/8)",
                available_cartridges=len(catalog),
            )

            llm_selection = {}
            try:
                raw_selection = cartridge_selection_agent.run(study_notes, game_design, level_design, catalog)
                llm_selection = extract_json_payload(raw_selection) or {}
            except Exception as selection_error:
                llm_selection = {
                    "selected_cartridge": "none",
                    "confidence": 0.0,
                    "reason": f"Selection model unavailable: {selection_error}",
                }

            cartridge_selection = select_best_cartridge(
                study_notes=study_notes,
                game_design=game_design,
                level_design=level_design,
                llm_selection=llm_selection,
            )
            selected_cartridge = cartridge_selection.get("selected_cartridge") or ""
            _set_task(
                task_id,
                cartridge_selection=cartridge_selection,
                selected_cartridge=selected_cartridge,
            )

            if selected_cartridge and selected_cartridge != "none":
                cartridge_profile = get_cartridge(selected_cartridge)
                if not cartridge_profile:
                    fallback_reason = f"Selected cartridge '{selected_cartridge}' not found."
                else:
                    _set_task(task_id, status="generating_cartridge_spec", phase="Cartridge Spec (4/8)")
                    try:
                        raw_spec = cartridge_spec_agent.run(
                            study_notes=study_notes,
                            game_design=game_design,
                            level_design=level_design,
                            cartridge_profile=cartridge_profile.to_dict(),
                        )
                        parsed_spec = extract_json_payload(raw_spec)
                    except Exception as spec_error:
                        parsed_spec = None
                        fallback_reason = f"Cartridge spec generation failed: {spec_error}"

                    if parsed_spec:
                        parsed_spec["style_variant"] = selected_cartridge
                        cartridge_game_design = build_design_summary(parsed_spec, selected_cartridge)
                        cartridge_level_design = build_level_summary(parsed_spec)
                        _set_task(
                            task_id,
                            status="building_cartridge",
                            phase="Building Cartridge Game (5/8)",
                            game_design=cartridge_game_design,
                            level_design=cartridge_level_design,
                            cartridge=selected_cartridge,
                            cartridge_spec=parsed_spec,
                        )
                        cartridge_code = build_cartridge_game_code(parsed_spec, selected_cartridge)
                        _write_game_file(game_file, cartridge_code)

                        _set_task(task_id, status="validating", phase="Quality Validation (6/8)")
                        cartridge_report = harness.run(
                            code=cartridge_code,
                            game_file=game_file,
                            python_path=python_path,
                            runtime_timeout_sec=SMOKE_TEST_TIMEOUT_SEC,
                            run_runtime=ENABLE_RUNTIME_SMOKE_TEST,
                        )
                        cartridge_report_dict = cartridge_report.to_dict()
                        cartridge_report_dict["attempt"] = 1
                        cartridge_report_dict["mode"] = "cartridge"
                        validation_history.append(cartridge_report_dict)

                        if cartridge_report.passed:
                            _complete_task(
                                task_id=task_id,
                                game_file=game_file,
                                code=cartridge_code,
                                game_design=cartridge_game_design,
                                level_design=cartridge_level_design,
                                generation_mode="cartridge",
                                quality_report=cartridge_report_dict,
                                validation_history=validation_history,
                                selected_cartridge=selected_cartridge,
                                cartridge_selection=cartridge_selection,
                            )
                            return
                        fallback_reason = f"Cartridge quality check failed: {_error_summary(cartridge_report_dict)}"
                    elif not fallback_reason:
                        fallback_reason = "Cartridge spec generation did not return valid JSON."
            else:
                fallback_reason = cartridge_selection.get("reason") or "No cartridge matched."

        _set_task(task_id, status="generating_code", phase="Custom Code Generation (fallback) (7/8)")
        generated_code = ""
        for attempt in range(1, MAX_CODE_ATTEMPTS + 1):
            if attempt == 1:
                generated_code = code_generation_agent.run(game_design, level_design)
            else:
                _set_task(
                    task_id,
                    status="repairing_code",
                    phase=f"Repairing Code ({attempt}/{MAX_CODE_ATTEMPTS})",
                )
                generated_code = code_repair_agent.run(
                    game_design=game_design,
                    level_design=level_design,
                    failed_code=generated_code,
                    validation_report=validation_history[-1],
                    attempt_number=attempt,
                )

            generated_code = sanitize_generated_code(generated_code)
            _write_game_file(game_file, generated_code)

            _set_task(task_id, status="validating", phase=f"Quality Validation ({attempt}/{MAX_CODE_ATTEMPTS})")
            report = harness.run(
                code=generated_code,
                game_file=game_file,
                python_path=python_path,
                runtime_timeout_sec=SMOKE_TEST_TIMEOUT_SEC,
                run_runtime=ENABLE_RUNTIME_SMOKE_TEST,
            )
            report_dict = report.to_dict()
            report_dict["attempt"] = attempt
            report_dict["mode"] = "freeform"
            validation_history.append(report_dict)

            if report.passed:
                _complete_task(
                    task_id=task_id,
                    game_file=game_file,
                    code=generated_code,
                    game_design=game_design,
                    level_design=level_design,
                    generation_mode="freeform",
                    quality_report=report_dict,
                    validation_history=validation_history,
                    fallback_reason=fallback_reason,
                    selected_cartridge=selected_cartridge,
                    cartridge_selection=cartridge_selection,
                )
                return

        final_failure = _error_summary(validation_history[-1]) if validation_history else "unknown validation error"
        raise RuntimeError(f"Generation failed all quality checks: {final_failure}")
    except Exception as e:
        _set_task(
            task_id,
            status="failed",
            error=str(e),
            phase="Failed",
            failed_at=datetime.now().isoformat(),
        )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    checks = _health_checks()
    status = "ok" if all(checks.values()) else "degraded"
    return {
        "status": status,
        "service": "game-engine",
        "tasks": len(_task_items_snapshot()),
        "checks": checks,
    }


@app.get("/health/live")
async def health_live():
    return {"status": "ok", "service": "game-engine"}


@app.get("/health/ready")
async def health_ready():
    checks = _health_checks()
    ready = all(checks.values())
    return {"status": "ready" if ready else "not_ready", "checks": checks}


def _health_checks() -> Dict[str, bool]:
    google_api_key_set = bool(os.getenv("GOOGLE_API_KEY"))
    python_path_exists = os.path.exists(_resolve_python_path())
    pygames_dir_writable = False
    pygame_import_ok = False

    try:
        os.makedirs("pygames", exist_ok=True)
        pygames_dir_writable = os.access("pygames", os.W_OK)
    except Exception:
        pygames_dir_writable = False

    try:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame  # noqa: F401

        pygame_import_ok = True
    except Exception:
        pygame_import_ok = False

    return {
        "google_api_key_set": google_api_key_set,
        "python_path_resolved": python_path_exists,
        "pygames_dir_writable": pygames_dir_writable,
        "pygame_import_ok": pygame_import_ok,
    }

@app.post("/api/generate")
async def generate_game(game_request: GameRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    text = (game_request.study_notes or "").strip()
    if not text:
        return JSONResponse({"error": "study_notes cannot be empty"}, status_code=400)

    _put_task(task_id, {
        "status": "queued",
        "phase": "Initializing...",
        "created_at": datetime.now().isoformat(),
        "study_notes": text[:12000],
        "validation_history": [],
        "generation_mode": "pending",
        "selected_cartridge": "",
        "cartridge_selection": {},
    })
    _prune_history()

    background_tasks.add_task(run_game_generation, task_id, text)

    return {"task_id": task_id, "status": "queued"}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    task = _get_task(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    return task

@app.post("/api/launch/{task_id}")
async def launch_game(task_id: str):
    status = _get_task(task_id)
    if not status:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    if status.get("status") != "completed":
        return JSONResponse({"error": "Game not ready"}, status_code=400)

    game_file = status.get("game_file")
    if not game_file or not os.path.exists(game_file):
        return JSONResponse({"error": "Game file not found"}, status_code=404)

    try:
        python_path = _resolve_python_path()
        subprocess.Popen([python_path, game_file])
        return {"message": "Game launched successfully", "python_path": python_path}
    except Exception as e:
        return JSONResponse({"error": f"Failed to launch game: {str(e)}"}, status_code=500)

@app.get("/api/history")
async def get_history():
    history = []
    for task_id, data in _task_items_snapshot():
        history.append({
            "task_id": task_id,
            "status": data.get("status"),
            "phase": data.get("phase"),
            "created_at": data.get("created_at"),
            "completed_at": data.get("completed_at"),
            "generation_mode": data.get("generation_mode"),
            "selected_cartridge": data.get("selected_cartridge"),
        })

    history.sort(key=lambda x: x["created_at"], reverse=True)
    return history[:10]


@app.get("/api/cartridges")
async def get_cartridges():
    return {
        "count": len(cartridge_catalog_for_prompt()),
        "cartridges": cartridge_catalog_for_prompt(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
