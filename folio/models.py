"""Value types shared by storage and search."""
from dataclasses import dataclass


def identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty identifier")
    return value


def normalize_tag(value: str) -> str:
    return identifier(value).strip().casefold()


@dataclass(frozen=True)
class Document:
    collection: str
    key: str
    title: str
    body: str
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.collection)
        identifier(self.key)
        if not isinstance(self.title, str) or not isinstance(self.body, str):
            raise ValueError("title and body must be strings")
        if not isinstance(self.tags, (tuple, list)):
            raise ValueError("tags must be a sequence of strings")
        normalized = {normalize_tag(tag) for tag in self.tags}
        object.__setattr__(self, "tags", tuple(sorted(normalized)))


@dataclass(frozen=True)
class Query:
    collection: str
    text: str = ""
    tag: str | None = None

    def __post_init__(self):
        identifier(self.collection)
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if self.tag is not None:
            object.__setattr__(self, "tag", normalize_tag(self.tag))


@dataclass(frozen=True)
class Hit:
    document: Document
    score: int
