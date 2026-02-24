import asyncio
import json
import os
import subprocess
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from playwright.async_api import Browser, async_playwright
from pydub import AudioSegment

MODEL_NAME = "gemini-2.5-flash"


# =====================================================
# Utility
# =====================================================

def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
        return max(1, value)
    except ValueError:
        return default


def _sanitize_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:80] or "document"


def _ensure_dirs(base_dir: str = "media") -> Dict[str, str]:
    dirs = {
        "base": base_dir,
        "audio": os.path.join(base_dir, "audio"),
        "html": os.path.join(base_dir, "html"),
        "video": os.path.join(base_dir, "video"),
        "images": os.path.join(base_dir, "images"),
    }
    for path in dirs.values():
        Path(path).mkdir(parents=True, exist_ok=True)
    return dirs


def _create_run_dirs(document_id: str) -> Dict[str, str]:
    run_id = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{_sanitize_name(document_id)}_{uuid.uuid4().hex[:8]}"
    base = os.path.join("media", "runs", run_id)
    dirs = _ensure_dirs(base)
    dirs["run_id"] = run_id
    return dirs


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _clean_json_response(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
    return text.strip()


def _normalize_ids(raw_ids: Any) -> List[str]:
    if raw_ids is None:
        return []
    if isinstance(raw_ids, list) and raw_ids and isinstance(raw_ids[0], list):
        return [str(x) for x in raw_ids[0]]
    if isinstance(raw_ids, list):
        return [str(x) for x in raw_ids]
    return []


def _normalize_metadatas(raw_metadatas: Any) -> List[Dict[str, Any]]:
    if raw_metadatas is None:
        return []
    if isinstance(raw_metadatas, list) and raw_metadatas and isinstance(raw_metadatas[0], list):
        raw_metadatas = raw_metadatas[0]
    if isinstance(raw_metadatas, list):
        return [m if isinstance(m, dict) else {} for m in raw_metadatas]
    return []


def normalize_chroma_images(chroma_response):
    if not chroma_response:
        return []

    if isinstance(chroma_response, list):
        return chroma_response

    ids = _normalize_ids(chroma_response.get("ids"))
    metadatas = _normalize_metadatas(chroma_response.get("metadatas"))
    images = []

    for idx, image_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        images.append(
            {
                "id": image_id,
                "caption": metadata.get("caption", ""),
                "path": metadata.get("path", ""),
                "page": metadata.get("page", 0),
                "ocr": metadata.get("ocr", ""),
            }
        )

    return images


def _save_pcm_as_wav(pcm_data: bytes, slide_id: int, audio_dir: str = "media/audio"):
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(audio_dir, f"slide_{slide_id}.wav")

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)

    return output_path


def _generate_silent_wav(slide_id: int, duration_seconds: float = 6.0, audio_dir: str = "media/audio"):
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(audio_dir, f"slide_{slide_id}.wav")
    silence = AudioSegment.silent(duration=max(int(duration_seconds * 1000), 1000))
    silence.export(output_path, format="wav")
    return output_path


# =====================================================
# STEP 1 - Slide Plan
# =====================================================

def generate_slide_plan(chunks, images):
    client = _get_client()
    _ensure_dirs()

    context_text = "\n".join([c["text"] for c in chunks[:20]])
    image_info = "\n".join([f"Image ID: {img['id']}, Caption: {img.get('caption', '')}" for img in images])

    prompt = f"""
Create professional educational slides.

TEXT:
{context_text}

IMAGES:
{image_info}

Rules:
- Max slides: 7
- Each slide:
    - title
    - as many bullet points as required, including at least 3 or 4 points
    - keep the text in bullet points very minimal and can restrict each point to a few words
    - Ensure text and image fits within a 1280x720 slide
    - no need to select images for slides like table of contents
    - no need of images for slides with no relevant images
    - 60-80 word natural conversational explanation
    - relevant image ids (array)

Return JSON list with:
- title
- bullet_points
- explanation
- image_ids
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    clean_text = _clean_json_response(response.text)
    return json.loads(clean_text)


# =====================================================
# STEP 2 - Voice Generation
# =====================================================

def generate_voice(text: str, slide_id: int, audio_dir: str = "media/audio"):
    client = _get_client()
    retries = 3

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="puck")
                        )
                    ),
                ),
            )

            audio_bytes = response.candidates[0].content.parts[0].inline_data.data
            return _save_pcm_as_wav(audio_bytes, slide_id, audio_dir=audio_dir)
        except Exception as exc:
            if attempt == retries - 1:
                print(
                    f"TTS failed for slide {slide_id} after {retries} attempts. "
                    f"Falling back to silence. Error: {exc}"
                )
                return _generate_silent_wav(slide_id, duration_seconds=6.0, audio_dir=audio_dir)
            wait_seconds = 2**attempt
            print(f"TTS attempt {attempt + 1}/{retries} failed for slide {slide_id}. Retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)


def get_audio_duration(audio_path: str) -> float:
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000


# =====================================================
# STEP 3 - Image Resolver
# =====================================================

def resolve_image_path(slide, all_images):
    if len(all_images) == 0:
        return ""

    image_ids = slide.get("image_ids") or []
    if len(image_ids) == 0:
        return ""

    image_id = image_ids[0]

    for img in all_images:
        if img.get("id") == image_id:
            return img.get("path") or ""

    return ""


# =====================================================
# STEP 4 - HTML Slide Renderer
# =====================================================

def render_slide_html(slide, duration, slide_id, all_images, html_dir: str = "media/html"):
    _ensure_dirs()
    Path(html_dir).mkdir(parents=True, exist_ok=True)

    image_path = resolve_image_path(slide, all_images)
    abs_image_path = f"file:///{os.path.abspath(image_path)}" if image_path else ""

    themes = [
        {"name": "Deep Obsidian", "bg": "linear-gradient(135deg, #16161d 0%, #1f1f2e 100%)", "accent": "#ff0055"}
    ]
    theme = themes[slide_id % len(themes)]

    layout_type = slide_id % 3
    if layout_type == 0:
        layout_class = "row-layout"
    elif layout_type == 1:
        layout_class = "column-layout"
    else:
        layout_class = "center-layout"

    bullet_points = slide.get("bullet_points") or []
    text_length = len(" ".join(bullet_points))
    if text_length > 220:
        image_width = 420
        image_height = 300
    else:
        image_width = 520
        image_height = 360

    animation_type = slide_id % 3
    if animation_type == 0:
        animation_css = "fadeUp"
    elif animation_type == 1:
        animation_css = "slideIn"
    else:
        animation_css = "zoomIn"

    bullets_html = "".join([f"<li style='animation-delay:{1.5 + i * 1.5}s'>{b}</li>" for i, b in enumerate(bullet_points)])
    title = slide.get("title") or f"Slide {slide_id + 1}"

    html = f"""
<html>
<head>
<meta charset="UTF-8">
<style>

body {{
    margin:0;
    font-family: 'Segoe UI', sans-serif;
    background: {theme['bg']};
    color:white;
    height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow:hidden;
}}

.container {{
    width:95%;
    height:90%;
    display:flex;
    gap:40px;
}}

.row-layout {{
    flex-direction:row;
}}

.column-layout {{
    flex-direction:column;
    text-align:center;
}}

.center-layout {{
    flex-direction:column;
    justify-content:center;
    align-items:center;
    text-align:center;
}}

.text {{
    flex:1;
}}

.image {{
    width: {image_width}px;
    height: {image_height}px;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.image img {{
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 20px;
}}


h1 {{
    font-size:48px;
    margin-bottom:20px;
    color:{theme['accent']};
    animation:{animation_css} 1s ease forwards;
}}

ul {{
    list-style:none;
    padding:0;
    font-size:22px;
}}

li {{
    opacity:0;
    margin-bottom:15px;
    animation:{animation_css} 0.8s ease forwards;
}}

@keyframes fadeUp {{
    from {{opacity:0; transform:translateY(20px);}}
    to {{opacity:1; transform:translateY(0);}}
}}

@keyframes slideIn {{
    from {{opacity:0; transform:translateX(-40px);}}
    to {{opacity:1; transform:translateX(0);}}
}}

@keyframes zoomIn {{
    from {{opacity:0; transform:scale(0.8);}}
    to {{opacity:1; transform:scale(1);}}
}}

</style>
</head>

<body>
<div class="container {layout_class}">

    <div class="text">
        <h1>{title}</h1>
        <ul>
            {bullets_html}
        </ul>
    </div>

    {"<div class='image'><img src='" + abs_image_path + "'></div>" if image_path else ""}

</div>
</body>
</html>
"""

    path = os.path.join(html_dir, f"slide_{slide_id}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return path


# =====================================================
# STEP 5 - HTML -> VIDEO (Playwright)
# =====================================================

async def _record_html_video(browser: Browser, html_path: str, video_dir: str, duration: float) -> str:
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=video_dir,
        record_video_size={"width": 1280, "height": 720},
    )

    page = await context.new_page()
    abs_path = os.path.abspath(html_path)
    await page.goto(f"file:///{abs_path}")
    await page.wait_for_timeout(int(max(duration, 1.0) * 1000))
    video = page.video

    await context.close()
    return await video.path()


async def html_to_video(
    html_path: str,
    slide_id: int,
    duration: float,
    video_dir: str = "media/video",
    browser: Optional[Browser] = None,
):
    _ensure_dirs()
    Path(video_dir).mkdir(parents=True, exist_ok=True)

    if browser is not None:
        return await _record_html_video(browser, html_path, video_dir, duration)

    async with async_playwright() as p:
        tmp_browser = await p.chromium.launch()
        try:
            return await _record_html_video(tmp_browser, html_path, video_dir, duration)
        finally:
            await tmp_browser.close()


# =====================================================
# STEP 6 - Image + Audio -> Video
# =====================================================

def image_audio_to_video(webm_path, audio_path, duration, slide_id, video_dir: str = "media/video"):
    Path(video_dir).mkdir(parents=True, exist_ok=True)
    output = os.path.join(video_dir, f"slide_{slide_id}.mp4")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        webm_path,
        "-i",
        audio_path,
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-shortest",
        output,
    ]

    subprocess.run(cmd, check=True)
    return output


# =====================================================
# STEP 7 - Stitch Videos
# =====================================================

def stitch_videos(video_paths, output_dir: str = "media/video", final_name: str = "final.mp4"):
    _ensure_dirs()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    concat_file = os.path.join(output_dir, "concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for video_path in video_paths:
            f.write(f"file '{os.path.abspath(video_path)}'\n")

    final_path = os.path.join(output_dir, final_name)
    cmd = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        "-y",
        final_path,
    ]
    subprocess.run(cmd, check=True)
    return final_path


# =====================================================
# Parallel Orchestrator
# =====================================================

async def _prepare_slide_assets(
    slide_id: int,
    slide: Dict[str, Any],
    all_images: List[Dict[str, Any]],
    audio_dir: str,
    html_dir: str,
    tts_semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    voice_text = slide.get("voiceover") or slide.get("explanation")
    if not voice_text:
        return {"slide": slide_id, "ok": False, "stage": "prepare", "error": "Missing voice text"}

    try:
        async with tts_semaphore:
            audio_path = await asyncio.to_thread(generate_voice, voice_text, slide_id, audio_dir)
        duration = await asyncio.to_thread(get_audio_duration, audio_path)
        html_path = await asyncio.to_thread(render_slide_html, slide, duration, slide_id, all_images, html_dir)
        return {
            "slide": slide_id,
            "ok": True,
            "audio_path": audio_path,
            "duration": duration,
            "html_path": html_path,
        }
    except Exception as exc:
        return {"slide": slide_id, "ok": False, "stage": "prepare", "error": str(exc)}


async def _render_and_mux_slide(
    prepared: Dict[str, Any],
    browser: Browser,
    render_semaphore: asyncio.Semaphore,
    mux_semaphore: asyncio.Semaphore,
    video_dir: str,
) -> Dict[str, Any]:
    slide_id = prepared["slide"]
    try:
        async with render_semaphore:
            webm_path = await html_to_video(
                prepared["html_path"],
                slide_id=slide_id,
                duration=prepared["duration"],
                video_dir=video_dir,
                browser=browser,
            )

        async with mux_semaphore:
            mp4_path = await asyncio.to_thread(
                image_audio_to_video,
                webm_path,
                prepared["audio_path"],
                prepared["duration"],
                slide_id,
                video_dir,
            )

        return {"slide": slide_id, "ok": True, "video_path": mp4_path}
    except Exception as exc:
        return {"slide": slide_id, "ok": False, "stage": "render_or_mux", "error": str(exc)}


async def generate_video_parallel(slides: List[Dict[str, Any]], image_chunks: List[Dict[str, Any]], document_id: str):
    if not slides:
        return {"error": "Slide generation failed", "slides_requested": 0, "slides_generated": 0, "slide_errors": []}

    run_dirs = _create_run_dirs(document_id=document_id)
    audio_dir = run_dirs["audio"]
    html_dir = run_dirs["html"]
    video_dir = run_dirs["video"]
    run_id = run_dirs["run_id"]

    tts_max = _safe_int_env("VIDEO_TTS_MAX_CONCURRENCY", 5)
    render_max = _safe_int_env("VIDEO_RENDER_MAX_CONCURRENCY", 3)
    mux_max = _safe_int_env("VIDEO_FFMPEG_MAX_CONCURRENCY", 3)

    tts_semaphore = asyncio.Semaphore(tts_max)
    render_semaphore = asyncio.Semaphore(render_max)
    mux_semaphore = asyncio.Semaphore(mux_max)

    prepare_tasks = [
        _prepare_slide_assets(i, slide, image_chunks, audio_dir, html_dir, tts_semaphore)
        for i, slide in enumerate(slides)
    ]
    prepared_results = await asyncio.gather(*prepare_tasks)

    slide_errors = []
    prepared_ok = []
    for result in prepared_results:
        if result.get("ok"):
            prepared_ok.append(result)
        else:
            slide_errors.append({"slide": result.get("slide"), "stage": result.get("stage"), "error": result.get("error")})

    if not prepared_ok:
        return {
            "error": "Video generation failed",
            "slides_requested": len(slides),
            "slides_generated": 0,
            "slide_errors": slide_errors,
            "run_id": run_id,
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            render_tasks = [
                _render_and_mux_slide(item, browser, render_semaphore, mux_semaphore, video_dir)
                for item in prepared_ok
            ]
            render_results = await asyncio.gather(*render_tasks)
        finally:
            await browser.close()

    videos_ok = []
    for result in render_results:
        if result.get("ok"):
            videos_ok.append(result)
        else:
            slide_errors.append({"slide": result.get("slide"), "stage": result.get("stage"), "error": result.get("error")})

    if not videos_ok:
        return {
            "error": "Video generation failed",
            "slides_requested": len(slides),
            "slides_generated": 0,
            "slide_errors": slide_errors,
            "run_id": run_id,
        }

    videos_ok.sort(key=lambda item: item["slide"])
    ordered_paths = [item["video_path"] for item in videos_ok]
    final_video = await asyncio.to_thread(stitch_videos, ordered_paths, video_dir, "final.mp4")

    return {
        "message": "Video generated successfully",
        "video_path": final_video,
        "slides_generated": len(ordered_paths),
        "slides_requested": len(slides),
        "slide_errors": slide_errors,
        "run_id": run_id,
        "concurrency": {"tts": tts_max, "render": render_max, "ffmpeg": mux_max},
    }
