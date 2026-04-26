# eSRL Game Generator

AI-powered PyGame mini-game creator that transforms study notes into interactive educational games.

## Features

- **AI-Powered Generation**: Uses the local Claude Code CLI (default) or Gemini API to create game designs, level progressions, and PyGame code
- **Web Interface**: Beautiful, modern UI built with FastAPI and Jinja2
- **Real-time Progress**: Watch your game being generated in real-time
- **Auto-Launch**: Automatically launches generated games
- **3-Phase Pipeline**:
  1. Game Design - Creates game concept from study notes
  2. Level Design - Designs progressive difficulty levels
  3. Code Generation - Generates complete PyGame code

## Setup

1. Clone the repository
2. Pick an LLM provider (default is the local Claude Code CLI):
   - **Claude Code CLI (default)** -- requires the `claude` binary on PATH
     and an authenticated Claude Code session (run `claude` once
     interactively to log in). No API key needed.
   - **Gemini** -- create a `.env` file with `GOOGLE_API_KEY=...` and set
     `GAME_LLM_PROVIDER=gemini`.
3. Run the startup script:
   ```bash
   ./start_server.sh
   ```
4. Open your browser to `http://localhost:8000`

### LLM provider configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `GAME_LLM_PROVIDER` | `claude_cli` | `claude_cli` or `gemini` |
| `CLAUDE_MODEL` | `claude-opus-4-7` | Model passed to `claude --model` |
| `CLAUDE_CLI_PATH` | `claude` | Override if `claude` is not on PATH |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Only used when provider is `gemini` |
| `GOOGLE_API_KEY` | _(unset)_ | Required only for the `gemini` provider |

## Usage

### Web Interface (Recommended)

1. Start the server: `./start_server.sh`
2. Open `http://localhost:8000` in your browser
3. Paste your study notes into the text area
4. Click "Generate Game"
5. Wait for the generation to complete
6. Click "Launch Game" to play

### Command Line

```bash
source venv/bin/activate
python run.py
```

## Project Structure

```
├── app.py                    # FastAPI application
├── agents.py                 # AI agents (game design, level design, code generation)
├── gemini_client.py          # Gemini API wrapper
├── orchestrator_gemini.py    # Workflow orchestrator
├── run.py                    # CLI runner
├── start_server.sh           # Startup script
├── templates/
│   └── index.html           # Web UI template
├── static/
│   ├── style.css            # Styles
│   └── script.js            # Frontend logic
└── pygames/                 # Generated games directory
```

## Requirements

- Python 3.12+
- Either the local `claude` CLI (default provider, no API key needed) or a `GOOGLE_API_KEY` for the Gemini fallback
- PyGame
- FastAPI
- See `requirements.txt` for full list

## How It Works

1. **Input**: User provides study notes about any topic
2. **Game Design Agent**: Creates an interactive game concept based on the notes
3. **Level Design Agent**: Designs 3 progressive difficulty levels
4. **Code Generation Agent**: Generates complete, runnable PyGame code
5. **Output**: Self-contained Python game file that can be launched immediately

## Example Topics

- Data Structures (Stacks, Queues, Trees)
- Science Concepts (Photosynthesis, Newton's Laws)
- Math Topics (Geometry, Algebra)
- Programming Concepts
- Any educational topic!

## Tech Stack

- **Backend**: FastAPI, Python 3.12
- **Frontend**: Vanilla JS, CSS3, Jinja2
- **AI**: Local Claude Code CLI (Opus 4.7) by default; Google Gemini 2.5 Flash as a fallback
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
