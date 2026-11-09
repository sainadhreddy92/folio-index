"""Application-facing catalog API."""
from .models import Document, Hit, Query
from .refresh import refresh
from .search import ranked
from .store import Store


class Catalog:
    def __init__(self, path=":memory:"):
        self._store = Store(path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        self._store.close()

    def transaction(self):
        return self._store.transaction()

    def put(self, document: Document) -> None:
        self._store.put(document)

    def get(self, collection: str, key: str) -> Document | None:
        return self._store.get(collection, key)

    def remove(self, collection: str, key: str) -> bool:
        return self._store.remove(collection, key)

    def search(self, query: Query) -> list[Hit]:
        return ranked(self._store.documents(query.collection), query)

    def refresh(self, sources, loader, *, workers=4, batch_size=100):
        """Fetch source records concurrently and save them in batches."""
        return refresh(self, sources, loader, workers, batch_size)
