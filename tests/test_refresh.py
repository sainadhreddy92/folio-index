import threading
import unittest
from folio import Catalog, Document


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.addCleanup(self.catalog.close)

    def test_fetches_overlap(self):
        barrier = threading.Barrier(2)
        def load(key):
            barrier.wait(timeout=5)
            return Document("docs", key, key.upper(), "")
        report = self.catalog.refresh(["a", "b"], load, workers=2)
        self.assertEqual((report.processed, report.distinct), (2, 2))
        self.assertEqual(self.catalog.get("docs", "a").title, "A")

    def test_serial_refresh(self):
        def load(title):
            return Document("docs", "a", title, "")
        report = self.catalog.refresh(["first", "last"], load, workers=1)
        self.assertEqual(report.distinct, 1)
        self.assertEqual(self.catalog.get("docs", "a").title, "last")

    def test_loader_failure(self):
        def load(key):
            if key == "b":
                raise OSError("source offline")
            return Document("docs", key, key, "")
        with self.assertRaises(OSError):
            self.catalog.refresh(["a", "b"], load, workers=1)
        self.assertIsNone(self.catalog.get("docs", "a"))
