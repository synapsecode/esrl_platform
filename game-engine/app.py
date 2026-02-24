from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import subprocess
import os
import uuid
from datetime import datetime
from typing import Dict, Optional
from agents import game_design_agent, level_design_agent, code_generation_agent

app = FastAPI(title="eSRL Game Generator")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

generation_status: Dict[str, Dict] = {}

class GameRequest(BaseModel):
    study_notes: str

def run_game_generation(task_id: str, study_notes: str):
    try:
        generation_status[task_id]["status"] = "generating_design"
        generation_status[task_id]["phase"] = "Game Design (1/3)"

        game_design = game_design_agent.run(study_notes)
        generation_status[task_id]["game_design"] = game_design

        generation_status[task_id]["status"] = "generating_levels"
        generation_status[task_id]["phase"] = "Level Design (2/3)"

        level_design = level_design_agent.run(game_design)
        generation_status[task_id]["level_design"] = level_design

        generation_status[task_id]["status"] = "generating_code"
        generation_status[task_id]["phase"] = "Code Generation (3/3)"

        code = code_generation_agent.run(game_design, level_design)
        code = code.replace('```python', '').replace('```', '').strip()

        os.makedirs("pygames", exist_ok=True)
        game_file = f"pygames/game_{task_id}.py"

        with open(game_file, "w", encoding="utf-8") as f:
            f.write(code)

        generation_status[task_id]["status"] = "completed"
        generation_status[task_id]["phase"] = "Complete"
        generation_status[task_id]["game_file"] = game_file
        generation_status[task_id]["code"] = code
        generation_status[task_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        generation_status[task_id]["status"] = "failed"
        generation_status[task_id]["error"] = str(e)
        generation_status[task_id]["phase"] = "Failed"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/generate")
async def generate_game(game_request: GameRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())

    generation_status[task_id] = {
        "status": "queued",
        "phase": "Initializing...",
        "created_at": datetime.now().isoformat(),
        "study_notes": game_request.study_notes
    }

    background_tasks.add_task(run_game_generation, task_id, game_request.study_notes)

    return {"task_id": task_id, "status": "queued"}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in generation_status:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    return generation_status[task_id]

@app.post("/api/launch/{task_id}")
async def launch_game(task_id: str):
    if task_id not in generation_status:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    status = generation_status[task_id]

    if status.get("status") != "completed":
        return JSONResponse({"error": "Game not ready"}, status_code=400)

    game_file = status.get("game_file")
    if not game_file or not os.path.exists(game_file):
        return JSONResponse({"error": "Game file not found"}, status_code=404)

    try:
        python_path = os.path.join(os.getcwd(), "venv", "bin", "python")
        subprocess.Popen([python_path, game_file])
        return {"message": "Game launched successfully"}
    except Exception as e:
        return JSONResponse({"error": f"Failed to launch game: {str(e)}"}, status_code=500)

@app.get("/api/history")
async def get_history():
    history = []
    for task_id, data in generation_status.items():
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
