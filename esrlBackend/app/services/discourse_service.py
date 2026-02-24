from typing import List, Dict


def classify_discourse(sections: List[Dict]) -> List[Dict]:
    # Placeholder: rule-based heuristics only
    for section in sections:
        content = section.get("content", "").lower()
        discourse_type = "explanation"

        if "definition" in content or " is " in content[:80]:
            discourse_type = "definition"
        elif "example" in content:
            discourse_type = "example"
        elif "steps" in content or "procedure" in content:
            discourse_type = "procedure"
        elif "conclusion" in content:
            discourse_type = "conclusion"

        section["discourse_type"] = discourse_type

    return sections
