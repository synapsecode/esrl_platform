from typing import Dict, List, Tuple
import os
from google import genai

from app.services.embedding_service import query_similar

MODEL_NAME = "gemini-2.5-flash"


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def retrieve_context(query: str, top_k: int = 5) -> Dict:
    return query_similar(query, top_k=top_k)


def _score_block(query_terms: List[str], doc: str, meta: Dict) -> int:
    text = doc.lower()
    score = 0
    for term in query_terms:
        if term in text:
            score += 2
    heading = (meta.get("heading") or "").lower()
    for term in query_terms:
        if term in heading:
            score += 3
    if meta.get("discourse_type") == "definition":
        score += 2
    return score


def _build_context_blocks(query: str, context: Dict, max_items: int = 8) -> List[Tuple[str, Dict]]:
    documents: List[str] = (context.get("documents") or [[]])[0]
    metadatas: List[Dict] = (context.get("metadatas") or [[]])[0]
    items: List[Tuple[str, Dict]] = []

    for doc, meta in zip(documents, metadatas):
        items.append((doc, meta or {}))

    query_terms = [t for t in query.lower().split() if len(t) > 2]
    items.sort(key=lambda item: _score_block(query_terms, item[0], item[1]), reverse=True)

    return items[:max_items]


def generate_answer(query: str, context: Dict) -> str:
    client = _get_client()
    blocks = _build_context_blocks(query, context)
    if not blocks:
        return "Not found in the provided notes. Try rephrasing or upload more pages."

    formatted_blocks = []
    for index, (doc, meta) in enumerate(blocks, start=1):
        heading = meta.get("heading") or "Source"
        page = meta.get("page")
        page_tag = f"page {page}" if page is not None else "page ?"
        discourse = meta.get("discourse_type") or "unknown"
        formatted_blocks.append(
            f"[{index}] ({page_tag}, {heading}, {discourse})\n{doc}"
        )

    prompt = (
        "Answer the question using only the context. "
        "If the answer is not in the context, say 'Not found in the provided notes.' "
        "Write the answer in Markdown with clear sections. "
        "Use this structure when applicable:\n"
        "- Title (single line)\n"
        "- Intro (1-2 sentences)\n"
        "- Definition (only if asked for a definition)\n"
        "- Key Points (bullets)\n"
        "- Examples (if present in context)\n"
        "- Sources (cite like [1][3])\n\n"
        "Keep it concise and include the source numbers you used like [1][3].\n\n"
        "Context:\n"
        + "\n\n".join(formatted_blocks)
        + "\n\nQuestion: "
        + query
    )
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text
