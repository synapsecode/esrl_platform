import os
from typing import Any, Dict, List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.services.pdf_service import (
    save_pdf,
    extract_text_from_pdf,
    extract_images_from_pdf,
    generate_document_id,
    record_last_uploaded,
    get_last_uploaded
)
from app.services.text_processing_service import clean_text, structure_pages
from app.services.discourse_service import classify_discourse
from app.services.chunk_service import chunk_sections, get_chunks_for_document
from app.services.embedding_service import (
    get_images_for_document,
    upsert_chunks,
    upsert_images,
    query_similar,
    query_images_for_document,
    get_text_for_page
)
from app.services.image_service import generate_caption, extract_text
from app.services.rag_service import generate_answer
from app.services.notes_service import generate_quick_notes
from app.services.summarizer_service import summarize_text_levels
from app.services.video_gen_service import generate_slide_plan, generate_voice, get_audio_duration, html_to_video, image_audio_to_video, normalize_chroma_images, render_slide_html, stitch_videos
import requests
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
GAME_ENGINE_API_URL = os.getenv("GAME_ENGINE_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GAME_ENGINE_TIMEOUT_SECONDS", "30"))

os.makedirs("storage", exist_ok=True)
os.makedirs("media", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    path = await save_pdf(file)

    document_id = generate_document_id(path)
    full_text, pages_text = extract_text_from_pdf(path)
    cleaned = clean_text(full_text)
    sections = structure_pages(pages_text)
    sections = classify_discourse(sections)

    for section in sections:
        section["document_id"] = document_id

    chunks = chunk_sections(sections, document_id)
    upsert_chunks(chunks)

    images = extract_images_from_pdf(path, document_id)
    if images:
        image_chunks = []
        for image in images:
            try:
                caption = generate_caption(image["path"])
            except Exception:
                caption = "Image"
            try:
                ocr_text = extract_text(image["path"])
            except Exception:
                ocr_text = ""
            if ocr_text:
                ocr_snippet = ocr_text[:400]
                caption = f"{caption}. OCR: {ocr_snippet}"
            image_chunks.append({
                "id": image["id"],
                "caption": caption,
                "ocr": ocr_text,
                "page": image.get("page"),
                "document_id": image.get("document_id"),
                "path": image.get("path")
            })
        upsert_images(image_chunks)

    record_last_uploaded(path, document_id)

    return {
        "message": "PDF processed",
        "document_id": document_id,
        "characters_extracted": len(cleaned),
        "chunks": len(chunks),
        "images": len(images)
    }


@app.post("/rag")
async def rag_query(payload: dict):
    query = payload.get("query", "")
    context = query_similar(query, top_k=8)
    answer = generate_answer(query, context)
    images = []
    metadatas = (context.get("metadatas") or [[]])[0]
    document_ids = [m.get("document_id") for m in metadatas if m]
    if document_ids:
        image_context = query_images_for_document(query, document_ids[0], limit=5)
        image_docs = (image_context.get("documents") or [[]])[0]
        image_metas = (image_context.get("metadatas") or [[]])[0]
        for doc, meta in zip(image_docs, image_metas):
            meta = meta or {}
            context_snippet = ""
            page = meta.get("page")
            if page is not None:
                page_context = get_text_for_page(document_ids[0], page, limit=1)
                page_docs = page_context.get("documents") or []
                page_docs = page_docs[0] if page_docs and isinstance(page_docs[0], list) else page_docs
                if page_docs:
                    context_snippet = page_docs[0][:400]
            images.append({
                "path": meta.get("path"),
                "url": meta.get("path"),
                "caption": meta.get("caption") or doc or "Image",
                "ocr": meta.get("ocr") or "",
                "context": context_snippet,
                "page": meta.get("page"),
                "document_id": meta.get("document_id")
            })
    return {"answer": answer, "context": context, "images": images}

@app.post("/chat")
async def chat_query(payload: Dict[str, Any]):
    messages: List[Dict[str, Any]] = payload.get("messages") or []
    user_query = ""

    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            user_query = (message.get("content") or "").strip()
            if user_query:
                break

    if not user_query:
        raise HTTPException(status_code=400, detail="Missing user query in messages.")

    return await rag_query({"query": user_query})


@app.post("/notes")
async def notes_query(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        last_uploaded = get_last_uploaded()
        if not last_uploaded:
            raise HTTPException(status_code=400, detail="No text provided and no uploaded PDF found.")

        pdf_path = last_uploaded.get("path")
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=400, detail="Last uploaded PDF not found.")

        full_text, _ = extract_text_from_pdf(pdf_path)
        text = clean_text(full_text)
    notes = generate_quick_notes(text)
    return notes


@app.post("/notes/summary")
async def notes_summary(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        last_uploaded = get_last_uploaded()
        if not last_uploaded:
            raise HTTPException(status_code=400, detail="No text provided and no uploaded PDF found.")

        pdf_path = last_uploaded.get("path")
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=400, detail="Last uploaded PDF not found.")

        full_text, _ = extract_text_from_pdf(pdf_path)
        text = clean_text(full_text)
    return summarize_text_levels(text)


def _build_study_notes_from_document(document_id: str) -> str:
    chunks = get_chunks_for_document(document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail=f"No chunks found for document_id: {document_id}")

    combined = []
    total_chars = 0
    max_chars = 12000
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        if total_chars + len(text) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 0:
                combined.append(text[:remaining])
            break
        combined.append(text)
        total_chars += len(text)

    study_notes = "\n\n".join(combined).strip()
    if not study_notes:
        raise HTTPException(status_code=400, detail="Could not build study notes from document chunks.")
    return study_notes


def _proxy_game_engine(method: str, path: str, payload: Dict[str, Any] | None = None):
    url = f"{GAME_ENGINE_API_URL}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        else:
            response = requests.post(url, json=payload or {}, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect to game-engine at {GAME_ENGINE_API_URL}: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=data)
    return data


@app.post("/game/generate/{document_id}")
async def generate_game(document_id: str):
    study_notes = _build_study_notes_from_document(document_id)
    payload = {"study_notes": study_notes}
    result = _proxy_game_engine("POST", "/api/generate", payload)
    return {"document_id": document_id, **result}


@app.get("/game/status/{task_id}")
async def game_status(task_id: str):
    return _proxy_game_engine("GET", f"/api/status/{task_id}")


@app.post("/game/launch/{task_id}")
async def game_launch(task_id: str):
    return _proxy_game_engine("POST", f"/api/launch/{task_id}")


@app.post("/generate_video/{document_id}")
async def generate_video(document_id: str):

    text_chunks = get_chunks_for_document(document_id)
    raw_images = get_images_for_document(document_id)
    image_chunks = normalize_chroma_images(raw_images)


    if not text_chunks:
        return {"error": "No text chunks found for document"}

    slides = generate_slide_plan(text_chunks, image_chunks)

    # print(slides)

    if not slides:
        return {"error": "Slide generation failed"}

    video_paths = []
    slide_errors = []

    for i, slide in enumerate(slides):
        print(f"Generating slide {i+1}/{len(slides)}")
        try:
            voice_text = slide.get("voiceover") or slide.get("explanation")
            if not voice_text:
                slide_errors.append({"slide": i, "error": "Missing voice text"})
                continue

            audio_path = generate_voice(voice_text, i)
            print(audio_path)
            duration = get_audio_duration(audio_path)

            html_path = render_slide_html(
                slide,
                duration=5,
                slide_id=i,
                all_images=image_chunks
            )

            webm_path = await html_to_video(html_path, i, duration)
            print("WEBM EXISTS:", os.path.exists(webm_path))
            print("AUDIO EXISTS:", os.path.exists(audio_path))
            video_path = image_audio_to_video(webm_path, audio_path, duration, i)
            video_paths.append(video_path)
        except Exception as exc:
            slide_errors.append({"slide": i, "error": str(exc)})
            print(f"Slide {i} failed: {exc}")
            continue

    if not video_paths:
        return {"error": "Video generation failed", "slide_errors": slide_errors}

    final_video = stitch_videos(video_paths)

    return {
        "message": "Video generated successfully",
        "video_path": final_video,
        "slides_generated": len(video_paths),
        "slides_requested": len(slides),
        "slide_errors": slide_errors
    }
