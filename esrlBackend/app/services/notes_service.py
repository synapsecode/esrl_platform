from typing import Dict
import os
import json
from google import genai

MODEL_NAME = "gemini-2.5-flash"


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def generate_quick_notes(text: str) -> Dict:
    client = _get_client()
    prompt = (
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        "  \"flashcards\": [{\"question\": \"...\", \"answer\": \"...\"}],\n"
        "  \"cheat_sheet\": \"...\",\n"
        "  \"mcqs\": [{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": \"A\"}],\n"
        "  \"interview_questions\": [\"...\"]\n"
        "}\n\n"
        "Create quick study notes from the text:\n"
        "- 5 flashcards (Q/A)\n"
        "- One-page cheat sheet\n"
        "- 5 MCQs with answers\n"
        "- 5 interview questions\n\n"
        f"Text:\n{text[:4000]}"
    )
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    raw = response.text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"notes": raw}
