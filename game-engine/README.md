# eSRL Game Generator

AI-powered PyGame mini-game creator that transforms study notes into interactive educational games.

## Features

- **Reliability-first generation** with deterministic cartridge mechanics
- **Quality harness** with syntax checks, static checks, and runtime smoke tests
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

## Project Structure

```
├── app.py                     # FastAPI application + generation pipeline
├── agents.py                  # AI agents (design/levels/cartridge spec/code/repair)
├── cartridge_builder.py       # JSON extraction + deterministic wrapper generation
├── quality_harness.py         # Syntax/static/runtime validation harness
├── cartridges/
│   └── quiz_runner.py         # Shared gameplay mechanics cartridge
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
4. **Cartridge Spec Agent**: Produces strict JSON content for shared mechanics
5. **Cartridge Build**: Server generates deterministic game wrapper code
6. **Quality Harness**: Runs syntax + static + runtime validation
7. **Fallback (if needed)**: Freeform generation with auto-repair attempts
8. **Output**: Validated Python game file that can be launched immediately

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
