import json
import unittest
from folio import Catalog
from folio.exchange import RecordError


def record(key, title, collection="docs"):
    return json.dumps(dict(collection=collection, key=key, title=title, body=""))


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.addCleanup(self.catalog.close)

    def test_repeated_keys_and_batches(self):
        rows = (record(key, title) for key, title in [("a", "one"), ("b", "two"), ("a", "new")])
        report = self.catalog.import_lines("docs", rows, batch_size=2)
        self.assertEqual((report.created, report.replaced), (2, 1))
        self.assertEqual(self.catalog.get("docs", "a").title, "new")

    def test_invalid_line(self):
        with self.assertRaises(RecordError):
            self.catalog.import_lines("docs", [record("a", "one"), "{"])
        self.assertIsNone(self.catalog.get("docs", "a"))

    def test_wrong_collection(self):
        with self.assertRaises(ValueError):
            self.catalog.import_lines("docs", [record("a", "one"), record("b", "two", "work")])
        self.assertIsNone(self.catalog.get("docs", "a"))
