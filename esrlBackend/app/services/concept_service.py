from typing import Dict, List
import spacy

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def extract_concepts(sections: List[Dict]) -> List[Dict]:
    nlp = _get_nlp()
    concepts: List[Dict] = []

    for section in sections:
        doc = nlp(section.get("content", ""))
        key_terms = [chunk.text for chunk in doc.noun_chunks][:5]
        for term in key_terms:
            concepts.append({
                "concept": term,
                "definition": "",
                "prerequisites": [],
                "related_concepts": [],
                "heading": section.get("heading"),
                "document_id": section.get("document_id")
            })

    return concepts
