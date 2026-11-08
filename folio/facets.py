"""Facet counts over a ranked result set."""
from collections import Counter
from dataclasses import dataclass

from .models import Hit


@dataclass(frozen=True)
class Bucket:
    tag: str
    count: int


@dataclass(frozen=True)
class SearchSummary:
    hits: tuple[Hit, ...]
    total: int
    tags: tuple[Bucket, ...]


def summarize(hits, hit_limit, tag_limit):
    for value in (hit_limit, tag_limit):
        if type(value) is not int or value < 0:
            raise ValueError("limits must be nonnegative integers")
    counts = Counter()
    for hit in hits:
        counts.update(hit.document.tags)
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return SearchSummary(
        hits=tuple(hits[:hit_limit]),
        total=len(hits),
        tags=tuple(Bucket(tag, count) for tag, count in ordered[:tag_limit]),
    )
