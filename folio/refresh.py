"""Load remote documents concurrently, then apply the results on the caller thread."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from itertools import islice

from .models import Document


@dataclass(frozen=True)
class RefreshReport:
    processed: int
    distinct: int


def refresh(catalog, sources, loader, workers):
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be positive")
    sources = iter(sources)
    touched = set()
    processed = 0
    with catalog.transaction(), ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            window = list(islice(sources, workers))
            if not window:
                break
            futures = [pool.submit(loader, source) for source in window]
            for future in as_completed(futures):
                doc = future.result()
                if not isinstance(doc, Document):
                    raise ValueError("loader must return a Document")
                catalog.put(doc)
                touched.add((doc.collection, doc.key))
                processed += 1
    return RefreshReport(processed, len(touched))
