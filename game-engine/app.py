from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import subprocess
import os
import uuid
import sys
import threading
from datetime import datetime
from typing import Dict, Optional
from agents import game_design_agent, level_design_agent, code_generation_agent

app = FastAPI(title="eSRL Game Generator")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

generation_status: Dict[str, Dict] = {}
status_lock = threading.Lock()
MAX_TASK_HISTORY = int(os.getenv("MAX_TASK_HISTORY", "200"))

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

def run_game_generation(task_id: str, study_notes: str):
    try:
        _set_task(task_id, status="generating_design", phase="Game Design (1/3)")

        game_design = game_design_agent.run(study_notes)
        _set_task(task_id, game_design=game_design)

        _set_task(task_id, status="generating_levels", phase="Level Design (2/3)")

        level_design = level_design_agent.run(game_design)
        _set_task(task_id, level_design=level_design)

        _set_task(task_id, status="generating_code", phase="Code Generation (3/3)")

        code = code_generation_agent.run(game_design, level_design)
        code = code.replace('```python', '').replace('```', '').strip()

        os.makedirs("pygames", exist_ok=True)
        game_file = f"pygames/game_{task_id}.py"

        with open(game_file, "w", encoding="utf-8") as f:
            f.write(code)

        _set_task(
            task_id,
            status="completed",
            phase="Complete",
            game_file=game_file,
            code=code,
            completed_at=datetime.now().isoformat(),
        )

    except Exception as e:
        _set_task(task_id, status="failed", error=str(e), phase="Failed")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "game-engine", "tasks": len(_task_items_snapshot())}

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
        "study_notes": text[:12000]
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
        venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
        python_path = venv_python if os.path.exists(venv_python) else sys.executable
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
            "completed_at": data.get("completed_at")
        })

    history.sort(key=lambda x: x["created_at"], reverse=True)
    return history[:10]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
