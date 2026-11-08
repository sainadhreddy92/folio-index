# Folio Index

Folio maintains a searchable, local catalog of documents. Use it to index a documentation tree, a collection of notes, or records exported by another application. Each collection has its own document IDs. One SQLite file can hold several collections.

## Quick start

Requires Python 3.10 or newer. From this checkout, install with `python -m pip install -e .`.

```python
from folio import Catalog, Document, Query

with Catalog("docs.sqlite") as catalog:
    catalog.put(Document("guides", "setup", "Install Folio", "Install with pip.", ("python",)))
    hits = catalog.search(Query("guides", "install"))
    print([(hit.document.key, hit.score) for hit in hits])
    # [('setup', 4)]
```

A write replaces the record with the same collection and key. A deletion returns whether a record existed. To integrate a batch writer, use the transaction context on the catalog. If a write raises, earlier writes in that transaction roll back.

## Search

Terms are case-insensitive and must all occur in the title or body. Each title occurrence adds three points and each body occurrence adds one. Repeated query terms count once. Ties sort by document key in ascending order. A tag filter uses the same normalization as stored tags. An empty search returns documents in key order.

## JSON Lines interchange

`folio.exchange` converts documents to and from newline-delimited JSON. The required string fields are collection, key, title, and body. Tags are optional. Blank lines are ignored. Parsing is lazy and errors include a one-based physical line number.

## Development

The catalog API is in `folio/catalog.py`. SQL and transaction ownership live in `folio/store.py`. Ranking is independent of SQLite and lives in `folio/search.py`. Run `python -m unittest discover -v` from the repository root. Tests use temporary or in-memory databases.
