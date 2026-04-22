# eSRL Game Generator

AI-powered PyGame mini-game creator that transforms study notes into interactive educational games.

## Features

- **10+ educational cartridges** spanning distinct mechanics (falling catch, lane routing, orbit targeting, matrix reveal, turret defense, sequence sprint)
- **Automatic cartridge selection** from source content + design context
- **Reliability-first generation** with deterministic cartridge mechanics
- **Quality harness** with syntax checks, static checks, and runtime smoke tests
- **Automatic fallback to custom game code** when no cartridge fit is strong
- **Automatic repair loop** for freeform fallback code generation
- **Structured progress + validation visibility** in the web UI
- **Health endpoints** for liveness/readiness checks

## Setup

1. Clone the repository
2. Create a `.env` file with your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```
3. Run the startup script:
   ```bash
   ./start_server.sh
   ```
4. Open your browser to `http://localhost:8000`

## Usage

### Web Interface (Recommended)

1. Start the server: `./start_server.sh`
2. Open `http://localhost:8000` in your browser
3. Paste your study notes into the text area
4. Click "Generate Game"
5. Wait for the generation to complete
6. Click "Launch Game" to play

### API Helpers

- `GET /api/cartridges` returns the current cartridge catalog used for routing.

## Project Structure

```
├── app.py                     # FastAPI application + generation pipeline
├── agents.py                  # AI agents (design/levels/selection/spec/code/repair)
├── cartridge_builder.py       # JSON extraction + cartridge selection + wrapper generation
├── quality_harness.py         # Syntax/static/runtime validation harness
├── cartridges/
│   ├── catalog.py             # Cartridge metadata + heuristic ranker
│   ├── common.py              # Shared cartridge utilities
│   ├── quiz_runner.py         # Falling catch mechanic
│   ├── lane_sort_runner.py    # Lane routing mechanic
│   ├── orbit_hunt_runner.py   # Orbit targeting mechanic
│   ├── memory_matrix_runner.py # Grid reveal mechanic
│   ├── concept_defense_runner.py # Turret defense mechanic
│   └── sequence_sprint_runner.py # Sliding decision mechanic
├── gemini_client.py           # Gemini API wrapper
├── orchestrator_gemini.py     # CLI orchestrator (legacy helper)
├── start_server.sh            # Startup script
├── templates/
│   └── index.html             # Web UI template
├── static/
│   ├── style.css              # Styles
│   └── script.js              # Frontend logic
└── pygames/                   # Generated games directory
```

## Requirements

- Python 3.12+
- Google API Key (Gemini)
- PyGame
- FastAPI
- See `requirements.txt` for full list

## How It Works

1. **Input**: User provides study notes about any topic
2. **Game Design Agent**: Creates an interactive game concept based on the notes
3. **Level Design Agent**: Designs 3 progressive difficulty levels
4. **Cartridge Selection Agent + Heuristic Ranker**: Chooses best-fit cartridge from catalog
5. **Cartridge Spec Agent**: Produces strict JSON content tailored to selected mechanic
6. **Cartridge Build**: Server generates deterministic game wrapper code
7. **Quality Harness**: Runs syntax + static + runtime validation
8. **Fallback (if needed)**: If no cartridge fits (or validation fails), use freeform generation with auto-repair attempts
9. **Output**: Validated Python game file that can be launched immediately

## Cartridge Catalog

- `concept_sprint_v2`
- `misconception_meteor_v1`
- `lane_sort_lab_v1`
- `category_cascade_v1`
- `orbit_hunt_v1`
- `signal_chase_v1`
- `memory_matrix_v1`
- `flash_grid_v1`
- `concept_defense_v1`
- `sequence_sprint_v1`
- `theorem_turret_v1`

## Environment Flags

- `ENABLE_CARTRIDGE_PIPELINE` (`1` by default)
- `ENABLE_RUNTIME_SMOKE_TEST` (`1` by default)
- `MAX_CODE_ATTEMPTS` (`3` by default)
- `SMOKE_TEST_TIMEOUT_SEC` (`8` by default)
- `MAX_TASK_HISTORY` (`200` by default)

## Example Topics

- Data Structures (Stacks, Queues, Trees)
- Science Concepts (Photosynthesis, Newton's Laws)
- Math Topics (Geometry, Algebra)
- Programming Concepts
- Any educational topic!

## Tech Stack

- **Backend**: FastAPI, Python 3.12
- **Frontend**: Vanilla JS, CSS3, Jinja2
- **AI**: Google Gemini 2.5 Flash
- **Game Engine**: PyGame
- **Async Tasks**: BackgroundTasks


## Architecture Diagram

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────┐
│   FastAPI       │
│   Web Server    │
└────────┬────────┘
         │
         ▼
┌────────────────────────────┐
│  Background Task Queue     │
│  (Generation Pipeline)     │
└────────┬───────────────────┘
         │
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Game    │ │ Level   │ │ Code    │
│ Design  │ │ Design  │ │ Gen     │
│ Agent   │ │ Agent   │ │ Agent   │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     └───────────┴───────────┘
                 │
                 ▼
          ┌──────────────┐
          │ Gemini 2.0   │
          │ Flash API    │
          └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │  Generated   │
          │  Game Code   │
          │  (.py file)  │
          └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │   PyGame     │
          │   Runtime    │
          └──────────────┘
```


## License

MIT
