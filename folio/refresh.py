"""Load remote documents concurrently, then apply the results on the caller thread."""

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .models import Document

if TYPE_CHECKING:
    from .catalog import Catalog


@dataclass(frozen=True)
class RefreshReport:
    processed: int
    distinct: int


def refresh(
    catalog: "Catalog",
    sources: Iterable[Any],
    loader: Callable[[Any], Document],
    workers: int,
    batch_size: int,
) -> RefreshReport:
    """Load every source and save the results in batches.

    Up to ``workers`` loads run at once, and a new load starts as soon as any
    one finishes. Every ``batch_size`` loaded documents are saved in their own
    transaction, so the catalog is only locked while a batch is written. If a
    load fails, batches already saved stay saved and the unsaved results are
    discarded before the error is raised.

    Loads may finish in any order, so each document keeps the result of its
    latest source position, even across batches. A refresh that completes
    therefore leaves the catalog the same as a serial refresh of the sources.

    Batches fill in the order loads finish, not in source order. After a
    failure, the saved documents are therefore not necessarily a prefix of
    the sources, and the error does not say which were saved. Running the
    same refresh again is safe and completes the catalog.
    """
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be positive")
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be positive")
    if catalog._store.db.in_transaction:
        # Fail before any load runs rather than at the first batch.
        raise RuntimeError("refresh cannot run inside a transaction")
    numbered: Iterator[tuple[int, Any]] = enumerate(sources)
    # (collection, key) -> source position of the version saved so far
    latest: dict[tuple[str, str], int] = {}
    unsaved: list[tuple[int, Document]] = []
    processed = 0

    def save_batch() -> None:
        staged = dict(latest)
        with catalog.transaction():
            for position, doc in unsaved:
                identity = (doc.collection, doc.key)
                if staged.get(identity, -1) < position:
                    catalog.put(doc)
                    staged[identity] = position
        latest.update(staged)  # only after the batch has committed
        unsaved.clear()

    pool = ThreadPoolExecutor(max_workers=workers)
    pending: dict[Future[Document], int] = {}
    try:

        def start_next() -> None:
            for position, source in numbered:
                pending[pool.submit(loader, source)] = position
                return

        for _ in range(workers):
            start_next()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                position = pending.pop(future)
                doc = future.result()
                if not isinstance(doc, Document):
                    raise ValueError("loader must return a Document")
                unsaved.append((position, doc))
                processed += 1
                start_next()
                if len(unsaved) >= batch_size:
                    save_batch()
        if unsaved:
            save_batch()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return RefreshReport(processed, len(latest))
