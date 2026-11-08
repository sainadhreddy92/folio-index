"""Import a JSON Lines archive into one collection."""
from dataclasses import dataclass
from itertools import islice

from .exchange import read_documents


@dataclass(frozen=True)
class ImportReport:
    created: int
    replaced: int


def batches(records, size):
    while True:
        batch = list(islice(records, size))
        if not batch:
            return
        yield batch


def import_archive(store, collection, lines, batch_size):
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be positive")
    created = replaced = 0
    records = read_documents(lines)
    for batch in batches(records, batch_size):
        with store.transaction():
            for doc in batch:
                if doc.collection != collection:
                    raise ValueError(f"unexpected collection: {doc.collection}")
                if store.get(collection, doc.key) is None:
                    created += 1
                else:
                    replaced += 1
                store.put(doc)
    return ImportReport(created, replaced)
