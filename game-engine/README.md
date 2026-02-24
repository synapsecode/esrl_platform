# eSRL Game Generator

AI-powered PyGame mini-game creator that transforms study notes into interactive educational games.

## Features

- **AI-Powered Generation**: Uses Gemini AI to create game designs, level progressions, and PyGame code
- **Web Interface**: Beautiful, modern UI built with FastAPI and Jinja2
- **Real-time Progress**: Watch your game being generated in real-time
- **Auto-Launch**: Automatically launches generated games
- **3-Phase Pipeline**:
  1. Game Design - Creates game concept from study notes
  2. Level Design - Designs progressive difficulty levels
  3. Code Generation - Generates complete PyGame code

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
- Google API Key (Gemini)
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
