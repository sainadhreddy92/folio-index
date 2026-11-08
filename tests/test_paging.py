import unittest
from folio import Catalog, Document, Query


class SearchPageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.addCleanup(self.catalog.close)
        for key, count in (("x", 3), ("y", 2), ("z", 1)):
            self.catalog.put(Document("books", key, "", "word " * count))
        self.query = Query("books", "word")

    def test_walk_pages(self):
        first = self.catalog.search_page(self.query, size=2)
        second = self.catalog.search_page(self.query, size=2, cursor=first.next_cursor)
        self.assertEqual([h.document.key for h in first.hits + second.hits], ["x", "y", "z"])
        self.assertIsNone(second.next_cursor)

    def test_token_scope(self):
        page = self.catalog.search_page(self.query, size=1)
        with self.assertRaises(ValueError):
            self.catalog.search_page(Query("other", "word"), cursor=page.next_cursor)

    def test_bad_size(self):
        with self.assertRaises(ValueError):
            self.catalog.search_page(self.query, size=0)
