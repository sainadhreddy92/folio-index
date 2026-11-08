"""Deterministic ranking for small local collections."""
import re
from collections import Counter
from collections.abc import Iterable

from .models import Document, Hit, Query


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def score(document: Document, terms: set[str]) -> int | None:
    title = Counter(tokens(document.title))
    body = Counter(tokens(document.body))
    if any(term not in title and term not in body for term in terms):
        return None
    return sum(3 * title[term] + body[term] for term in terms)


def ranked(documents: Iterable[Document], query: Query) -> list[Hit]:
    terms = set(tokens(query.text))
    hits = []
    for doc in documents:
        if doc.collection != query.collection:
            continue
        if query.tag is not None and query.tag not in doc.tags:
            continue
        points = score(doc, terms)
        if points is not None:
            hits.append(Hit(doc, points))
    return sorted(hits, key=lambda hit: (-hit.score, hit.document.key))
