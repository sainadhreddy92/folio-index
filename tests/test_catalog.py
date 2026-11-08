import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from folio import Catalog, Document, Query


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.addCleanup(self.catalog.close)
        self.a = Document("notes", "a", "Local search", "fast", (" Dev ", "dev"))
        self.b = Document("notes", "b", "Archive", "local search")
        for doc in (self.b, self.a, Document("other", "a", "local", "")):
            self.catalog.put(doc)

    def test_weighted_search(self):
        hits = self.catalog.search(Query("notes", "LOCAL local search"))
        self.assertEqual([(h.document.key, h.score) for h in hits], [("a", 6), ("b", 2)])

    def test_tag_filter(self):
        hits = self.catalog.search(Query("notes", tag=" DEV "))
        self.assertEqual([h.document for h in hits], [self.a])

    def test_missing_term(self):
        self.assertEqual(self.catalog.search(Query("notes", "local missing")), [])

    def test_replace_and_remove(self):
        self.catalog.put(Document("notes", "a", "updated", ""))
        self.assertEqual(self.catalog.get("notes", "a").title, "updated")
        self.assertTrue(self.catalog.remove("notes", "a"))
        self.assertFalse(self.catalog.remove("notes", "a"))
        self.assertIsNotNone(self.catalog.get("other", "a"))

    def test_rollback(self):
        with self.assertRaises(ValueError):
            with self.catalog.transaction():
                self.catalog.remove("notes", "a")
                raise ValueError("abort")
        self.assertEqual(self.catalog.get("notes", "a"), self.a)

    def test_reopen(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "index.sqlite"
            with Catalog(path) as first:
                first.put(self.a)
            with Catalog(path) as second:
                self.assertEqual(second.get("notes", "a"), self.a)
