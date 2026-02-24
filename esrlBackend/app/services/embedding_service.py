from typing import Dict, List

from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_DIR = "storage/chroma"
COLLECTION_NAME = "knowledge"

_model = None
_client = None
_collection = None


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_chroma_collection():
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    if _collection is None:
        _collection = _client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedder()
    return model.encode(texts).tolist()


def upsert_chunks(chunks: List[Dict]) -> None:
    if not chunks:
        return

    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(texts)
    ids = [chunk["id"] for chunk in chunks]
    metadatas = [
        {
            "heading": chunk.get("heading"),
            "document_id": chunk.get("document_id"),
            "page": chunk.get("page"),
            "discourse_type": chunk.get("discourse_type"),
            "difficulty": chunk.get("difficulty"),
            "type": "text"
        }
        for chunk in chunks
    ]

    collection = get_chroma_collection()
    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )


def upsert_images(image_chunks: List[Dict]) -> None:
    if not image_chunks:
        return

    texts = [chunk["caption"] for chunk in image_chunks]
    embeddings = embed_texts(texts)
    ids = [chunk["id"] for chunk in image_chunks]
    metadatas = [
        {
            "page": chunk.get("page"),
            "type": "image",
            "document_id": chunk.get("document_id"),
            "path": chunk.get("path"),
            "caption": chunk.get("caption"),
            "ocr": chunk.get("ocr")
        }
        for chunk in image_chunks
    ]

    collection = get_chroma_collection()
    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )


def query_similar(text: str, top_k: int = 5) -> Dict:
    collection = get_chroma_collection()
    embedding = embed_texts([text])[0]
    return collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )


def get_images_for_document(document_id: str, limit: int = 5) -> Dict:
    collection = get_chroma_collection()
    return collection.get(
        where={"$and": [{"document_id": document_id}, {"type": "image"}]},
        limit=limit,
        include=["documents", "metadatas"]
    )


def query_images_for_document(query: str, document_id: str, limit: int = 5) -> Dict:
    collection = get_chroma_collection()
    embedding = embed_texts([query])[0]
    return collection.query(
        query_embeddings=[embedding],
        n_results=limit,
        where={"$and": [{"document_id": document_id}, {"type": "image"}]},
        include=["documents", "metadatas", "distances"]
    )


def get_text_for_page(document_id: str, page: int, limit: int = 1) -> Dict:
    collection = get_chroma_collection()
    return collection.get(
        where={"$and": [{"document_id": document_id}, {"type": "text"}, {"page": page}]},
        limit=limit,
        include=["documents", "metadatas"]
    )
