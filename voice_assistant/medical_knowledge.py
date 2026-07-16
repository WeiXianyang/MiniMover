"""Local, dependency-free retrieval for demo medical guidance."""

import json
import re
from pathlib import Path


class MedicalKnowledgeBase:
    """A small in-memory JSONL corpus with conservative text-overlap retrieval."""

    def __init__(self, texts=()):
        self._texts = tuple(text for text in texts if isinstance(text, str) and text.strip())
        self._index = tuple((text, _terms(text)) for text in self._texts)

    @classmethod
    def from_jsonl(cls, path):
        source = Path(path)
        if not source.is_file():
            return cls()
        texts = []
        try:
            with source.open("r", encoding="utf-8-sig") as handle:
                for line in handle:
                    try:
                        value = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    text = value.get("text") if isinstance(value, dict) else None
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
        except OSError:
            return cls()
        return cls(texts)

    def search(self, query, limit=3):
        """Return unique relevant text snippets without making medical claims."""
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 3
        query_terms = _terms(query)
        if not query_terms:
            return []

        scored = []
        for order, (text, text_terms) in enumerate(self._index):
            score = sum(1 for term in query_terms if term in text_terms)
            if score:
                scored.append((score, order, text))
        scored.sort(key=lambda item: (-item[0], item[1]))

        results = []
        seen = set()
        for _, _, text in scored:
            if text not in seen:
                results.append(text)
                seen.add(text)
            if len(results) >= limit:
                break
        return results


def _terms(value):
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(value or "").lower())
    if not normalized:
        return set()
    terms = {normalized} if len(normalized) <= 4 else set()
    for size in range(2, min(4, len(normalized)) + 1):
        terms.update(normalized[index:index + size] for index in range(len(normalized) - size + 1))
    return terms
