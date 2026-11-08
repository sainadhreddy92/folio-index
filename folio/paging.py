"""Continuation tokens for ranked catalog results."""
import base64
import hashlib
import json
from dataclasses import dataclass

from .models import Hit, Query


@dataclass(frozen=True)
class Page:
    hits: tuple[Hit, ...]
    next_cursor: str | None


def fingerprint(query: Query) -> str:
    fields = json.dumps([query.collection, query.text, query.tag])
    return hashlib.sha256(fields.encode()).hexdigest()[:20]


def encode(query, hit):
    fields = [1, fingerprint(query), hit.score, hit.document.key]
    return base64.urlsafe_b64encode(json.dumps(fields).encode()).decode("ascii")


def decode(query, cursor):
    try:
        version, scope, score, key = json.loads(base64.urlsafe_b64decode(cursor))
        if version != 1 or scope != fingerprint(query):
            raise ValueError("cursor does not match this query")
        if type(score) is not int or not isinstance(key, str):
            raise ValueError("invalid cursor fields")
        return score, key
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid search cursor") from exc


def paginate(hits, query, size, cursor):
    if type(size) is not int or not 1 <= size <= 100:
        raise ValueError("page size must be between 1 and 100")
    if cursor is not None:
        last_score, last_key = decode(query, cursor)
        hits = [hit for hit in hits if hit.score < last_score]
    window = tuple(hits[:size])
    continuation = encode(query, window[-1]) if len(hits) > size else None
    return Page(window, continuation)
