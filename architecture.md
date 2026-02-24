# eSRL Architecture Reference

## 1) System Overview

eSRL is a multi-service learning platform that converts an uploaded PDF into:
- Retrieval-augmented chat and contextual image answers
- Quick notes + structured summaries
- An auto-generated explainer video
- An auto-generated educational game

Current repository layout:
- `esrl-app/`: primary Next.js frontend (student-facing app)
- `esrlBackend/`: FastAPI orchestration + document processing + RAG + notes + video generation
- `game-engine/`: separate FastAPI service that generates and launches PyGame files from study notes
- `start_esrl.sh`: macOS script that starts all three services in separate Terminal tabs

## 2) Runtime Topology

Typical local startup (`start_esrl.sh`):
- `game-engine` on `http://0.0.0.0:8000`
- `esrlBackend` on `http://0.0.0.0:5140`
- `esrl-app` on `http://localhost:3000`

Integration path used by the app:
1. User opens Next.js UI (`esrl-app`)
2. Frontend calls backend APIs (`NEXT_PUBLIC_API_URI`)
3. Backend calls `game-engine` for game generation/launch (`GAME_ENGINE_API_URL`)

Port/config alignment:
- Frontend now resolves API base through `esrl-app/lib/api.js` with default `http://127.0.0.1:5140`.
- `start_esrl.sh` exports `NEXT_PUBLIC_API_URI` explicitly so UI/backend point to the same origin in local runs.

## 3) Core Data Flow

### 3.1 PDF Ingestion and Indexing

Entry endpoint: `POST /upload_pdf` (backend)

Flow:
1. Save PDF to disk (`storage/pdfs/...`)
2. Create `document_id` (`doc_<timestamp>_<filename>`)
3. Extract page text with PyMuPDF (`fitz`)
4. Detect scanned pages (`is_scanned`) and OCR with Tesseract where needed
5. Clean/structure text into sections (`clean_text`, heading heuristics)
6. Classify section discourse type (rule-based: definition/example/procedure/...)
7. Chunk text sections (`MAX_CHARS=800`, overlap `120`, skip tiny paragraphs)
8. Embed chunks (SentenceTransformers `all-MiniLM-L6-v2`) and upsert into ChromaDB
9. Extract PDF images, caption with BLIP, OCR image text, upsert image vectors into ChromaDB
10. Persist "last uploaded" pointer in `storage/last_uploaded.json`

Output:
- `document_id`
- counts for text chars/chunks/images

### 3.2 RAG Chat

Entry endpoints:
- `POST /chat` (OpenAI-style message list input, uses last user message)
- `POST /rag` (direct query)

Flow:
1. Embed query
2. Retrieve top text chunks from Chroma (`query_similar`)
   - Supports optional `document_id` filter to keep retrieval scoped to the active document
3. Rank retrieved blocks with additional keyword scoring + discourse weighting
4. Generate answer using Gemini (`gemini-2.5-flash`) constrained to provided context
5. Retrieve related image vectors for same `document_id`
6. Attach image metadata + nearby page text snippet for richer assistant response

Response includes:
- `answer` (Markdown)
- raw retrieval `context`
- `images` (caption/ocr/page/context/path)

### 3.3 Notes and Summary

Endpoints:
- `POST /notes`
- `POST /notes/summary`

Behavior:
- If request body has `document_id`, backend builds source text from that document’s stored chunks.
- If request body has no `text` and no `document_id`, backend falls back to the most recently uploaded PDF (`last_uploaded.json`).
- Notes generation prompt asks Gemini for JSON with:
  - `flashcards`
  - `cheat_sheet`
  - `mcqs`
  - `interview_questions`
- Summary endpoint requests 3-level summary (TL;DR, concept bullets, beginner-friendly)

### 3.4 Video Generation

Endpoint: `POST /generate_video/{document_id}`

Flow:
1. Load document text chunks + document images from Chroma
2. Ask Gemini for slide plan JSON (up to 7 slides)
3. Prepare slide assets in parallel (bounded concurrency):
   - Generate TTS audio (`gemini-2.5-flash-preview-tts`, PCM -> WAV)
   - Render themed slide HTML
4. Render/mux slides in parallel (bounded concurrency):
   - Record each slide as WebM using Playwright Chromium
   - Mux WebM + WAV into MP4 with FFmpeg
5. Sort successful slides by `slide_index` and stitch with FFmpeg concat into final MP4
6. Emit run-scoped terminal progress logs per slide (`[video:<run_id>] ...`) for easier debugging

Artifacts:
- Run-scoped outputs under `media/runs/<run_id>/`:
  - `audio/`, `html/`, `video/`
  - final output at `media/runs/<run_id>/video/final.mp4`
- Backend serves `/media` static route

### 3.5 Game Generation

Backend endpoints:
- `POST /game/generate/{document_id}`
- `GET /game/status/{task_id}`
- `POST /game/launch/{task_id}`

Backend responsibilities:
1. Build `study_notes` from retrieved text chunks for document (cap at ~12,000 chars)
2. Proxy to `game-engine` service

Game-engine (`game-engine/app.py`) flow:
1. Queue task in in-memory `generation_status`
2. Run background 3-phase pipeline:
   - Game design agent
   - Level design agent
   - Code generation agent
3. Save generated Python game file in `pygames/game_{task_id}.py`
4. Launch with `venv/bin/python` via `subprocess.Popen`

Frontend behavior (`esrl-app/app/chat/[id]/page.js`):
- Starts game generation immediately after loading document page
- Polls status every 4 seconds
- Auto-launches game when status becomes `completed`

## 4) Service and Module Boundaries

### 4.1 `esrl-app` (Next.js)

Key routes:
- `/` landing page
- `/chat` upload page
- `/chat/[id]` workspace with:
  - left panel: summary + notes
  - center panel: chat UI
  - right panel: game status + video player
- `/how-to-use`

Key integration points:
- Uses `NEXT_PUBLIC_API_URI` for backend requests
- Uses `react-markdown` to render assistant/summary/notes content
- Displays images returned by `/chat`

### 4.2 `esrlBackend` (FastAPI)

Main entry: `main.py`

Major service modules:
- `pdf_extraction_service.py`: file save, OCR fallback, image extraction, last-upload tracking
- `text_processing_service.py`: cleanup + section structuring
- `discourse_service.py`: heuristic discourse labels
- `chunk_service.py`: chunk creation and retrieval by document
- `embedding_service.py`: SentenceTransformer + ChromaDB persistence/query
- `rag_service.py`: context assembly + Gemini answer generation
- `notes_service.py`: structured study notes generation
- `summarizer_service.py`: layered summarization
- `image_service.py`: BLIP caption + OCR text extraction
- `video_gen_service.py`: slide plan + streaming parallelized TTS/render/mux pipeline with deterministic ordered stitching and per-slide terminal logs

Auxiliary UI:
- `streamlit_app.py` provides a parallel demo/testing interface for backend endpoints

### 4.3 `game-engine` (FastAPI)

Main entry: `app.py`

Responsibilities:
- Accept `study_notes`
- Run generation pipeline asynchronously (FastAPI `BackgroundTasks`)
- Track status in memory
- Persist generated game Python files
- Launch local PyGame process on demand

AI pipeline files:
- `agents.py`: three specialized agent prompts + wrappers
- `gemini_client.py`: Gemini client wrapper (`GOOGLE_API_KEY`)
- `orchestrator_gemini.py`: standalone orchestrator wrapper

Web UI mode:
- Server-rendered Jinja template + static JS/CSS at `/`
- Can be used standalone without Next.js frontend

## 5) API Surface (Current)

Backend (`esrlBackend/main.py`):
- `GET /`
- `GET /health`
- `POST /upload_pdf`
- `POST /rag`
- `POST /chat`
- `POST /notes`
- `POST /notes/summary`
- `GET /documents/last`
- `POST /generate_video/{document_id}` (returns `video_path`, `run_id`, slide counts/errors, and active concurrency settings)
- `POST /game/generate/{document_id}`
- `GET /game/status/{task_id}`
- `POST /game/launch/{task_id}`

Game-engine (`game-engine/app.py`):
- `GET /` (HTML UI)
- `GET /health`
- `POST /api/generate`
- `GET /api/status/{task_id}`
- `POST /api/launch/{task_id}`
- `GET /api/history`

## 6) Persistence and File System Layout

### Backend (`esrlBackend`)
- `storage/pdfs/`: uploaded PDFs
- `storage/images/`: extracted PDF images
- `storage/chroma/`: ChromaDB persistent store
- `storage/last_uploaded.json`: global pointer used by `/notes` and `/notes/summary`
- `media/runs/<run_id>/audio|html|video/`: run-isolated video intermediates + output

### Game-engine
- `pygames/`: generated game scripts
- In-memory task status map (`generation_status`) with thread-safe updates and bounded retention (`MAX_TASK_HISTORY`)

## 7) External Dependencies and Infra Requirements

### AI/ML APIs
- Gemini via `google-genai`:
  - backend uses `GEMINI_API_KEY`
  - game-engine uses `GOOGLE_API_KEY`

### Local system dependencies
- Tesseract OCR binary (required by `pytesseract`)
- FFmpeg (required by video mux/stitch)
- Playwright + Chromium dependencies (for HTML slide capture)
- PyGame runtime (for launched games)

### Python/ML libraries
- `sentence-transformers` for embeddings
- `chromadb` for vector persistence/query
- `transformers` BLIP model for image captioning
- `spacy` model usage exists (`en_core_web_sm`) in `concept_service.py` (currently not part of main API flow)

## 8) Configuration and Environment Variables

Backend:
- `GEMINI_API_KEY`: required for chat/notes/summary/video
- `GAME_ENGINE_API_URL`: default `http://127.0.0.1:8000`
- `GAME_ENGINE_TIMEOUT_SECONDS`: default `30`
- `VIDEO_TTS_MAX_CONCURRENCY`: max parallel TTS tasks (default `5`)
- `VIDEO_RENDER_MAX_CONCURRENCY`: max parallel Playwright render tasks (default `3`)
- `VIDEO_FFMPEG_MAX_CONCURRENCY`: max parallel FFmpeg mux tasks (default `3`)

Frontend:
- `NEXT_PUBLIC_API_URI`: backend base URL (should point to `http://127.0.0.1:5140` in current local setup)

Game-engine:
- `GOOGLE_API_KEY`: required for game generation agents
- `MAX_TASK_HISTORY`: max in-memory retained tasks for `/api/history` and status storage (default `200`)

## 9) Current Architectural Characteristics

Strengths:
- Clear modular service split in backend
- Feature-complete end-user pipeline from one PDF upload
- Multi-modal retrieval (text + images + OCR)
- Local-first persistence for quick experimentation

Tradeoffs / constraints:
- No authentication or tenant isolation (`allow_origins=["*"]`, global state)
- `last_uploaded.json` introduces cross-user/session coupling
- Chroma uses single collection (`knowledge`) with filtering by metadata
- Game status is in-memory; restart loses task history/state
- OCR/model inference/video generation still run inside API process (even though video slides are parallelized)
- Weak failure isolation for long-running pipelines

## 10) Known Risks and Gaps (for future roadmap)

1. Multi-user correctness:
- `/notes` and `/notes/summary` can read wrong document under concurrent users due to global `last_uploaded` fallback.

2. Operational robustness:
- Video generation and model inference can be long-running and resource-intensive with no queue/worker separation.

3. Config inconsistency:
- Frontend default backend URL conflicts with startup script topology.

4. State durability:
- Game task lifecycle is not persisted; failures/restarts lose status.

5. Security posture:
- No auth/rate-limiting/input size controls; permissive CORS.

6. Prompt/response hardening:
- JSON parsing in notes handles malformed model output minimally.

## 11) Suggested Evolution Path

Near-term:
1. Introduce explicit `document_id` for all notes/summary/chat requests (remove global fallback dependency).
2. Standardize env naming (`GEMINI_API_KEY` vs `GOOGLE_API_KEY`) and startup configuration.
3. Add request validation limits (PDF size/pages, timeout caps, payload constraints).
4. Persist game task metadata in a DB (SQLite/Postgres/Redis) instead of process memory.

Medium-term:
1. Move heavy jobs (video, OCR, game generation) to worker queue (Celery/RQ/Temporal/etc.).
2. Add auth + tenant scoping for storage and vector retrieval.
3. Split vector collections or namespaces per tenant/document lifecycle.
4. Add observability (structured logs, tracing, job metrics, failure reasons).

Long-term:
1. Deploy service mesh/API gateway model for backend + game-engine with stable internal contracts.
2. Add model routing policy (cost/performance fallback for generation endpoints).
3. Add artifact lifecycle management (cleanup/retention policy for media and generated games).

## 12) Quick Reference: End-to-End Sequence

1. User uploads PDF in Next.js UI.
2. Backend processes PDF into text/image embeddings in Chroma.
3. User lands on document workspace `/chat/{document_id}`.
4. Frontend concurrently requests summary, notes, video generation, and game generation.
5. Chat interactions use RAG over stored chunks and can return related document images.
6. Video becomes available when slide render + FFmpeg stitch completes.
   - Internally this now runs with bounded parallel stages and deterministic ordering.
7. Game status is polled until completion; frontend auto-launches generated PyGame.

---
This document is intentionally implementation-specific and reflects the current codebase behavior in this repository.
