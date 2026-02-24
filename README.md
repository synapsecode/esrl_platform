# eSRL Platform Monorepo

This repository contains the full eSRL stack:

- `esrl-app/`: Next.js student UI
- `esrlBackend/`: FastAPI document processing + RAG + notes + video generation
- `game-engine/`: FastAPI game-generation service (Gemini -> PyGame)

## Quick Start (Local)

1. Set required API keys in your shell or `.env` files:
   - Backend: `GEMINI_API_KEY`
   - Game engine: `GOOGLE_API_KEY`
   - Reference files:
     - `esrlBackend/.env.example`
     - `game-engine/.env.example`
     - `esrl-app/env.local.example`
2. Run:
   - `./start_esrl.sh`
3. Open:
   - Frontend: `http://localhost:3000`

The startup script aligns service URLs by exporting:
- `NEXT_PUBLIC_API_URI` (frontend -> backend)
- `GAME_ENGINE_API_URL` (backend -> game engine)

## Video Generation Tuning

Backend supports configurable concurrency:

- `VIDEO_TTS_MAX_CONCURRENCY` (default `5`)
- `VIDEO_RENDER_MAX_CONCURRENCY` (default `3`)
- `VIDEO_FFMPEG_MAX_CONCURRENCY` (default `3`)

Generated artifacts are isolated per run under:

- `esrlBackend/media/runs/<run_id>/audio`
- `esrlBackend/media/runs/<run_id>/html`
- `esrlBackend/media/runs/<run_id>/video`

## Backend API Notes

- `POST /chat` accepts `messages` and optional `document_id`
- `POST /rag` accepts `query` and optional `document_id`
- `POST /notes` and `POST /notes/summary` accept optional `document_id`
- `GET /documents/last` returns metadata for the most recently uploaded PDF
- `GET /health` endpoints are available in both backend services

Detailed system design is documented in:
- `architecture.md`
