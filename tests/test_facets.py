import unittest
from folio import Catalog, Document, Query
from folio.facets import Bucket


class FacetTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.addCleanup(self.catalog.close)
        for key, tags in (("a", ["red", "beta"]), ("b", ["red", "alpha"]), ("c", [])):
            self.catalog.put(Document("docs", key, "guide", "", tags))
        self.catalog.put(Document("other", "a", "guide", "", ["blue"]))
        self.catalog.put(Document("docs", "d", "appendix", "", ["blue"]))

    def test_counts_include_hits_beyond_preview(self):
        result = self.catalog.search_summary(Query("docs", "guide"), hit_limit=1)
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.total, 3)
        self.assertEqual(result.tags, (Bucket("red", 2), Bucket("alpha", 1), Bucket("beta", 1)))

    def test_filtered_preview(self):
        result = self.catalog.search_summary(Query("docs", tag="RED"), hit_limit=0, tag_limit=1)
        self.assertEqual(result.hits, ())
        self.assertEqual(result.total, 2)
        self.assertEqual(result.tags, (Bucket("red", 2),))

    def test_bad_limit(self):
        with self.assertRaises(ValueError):
            self.catalog.search_summary(Query("docs"), tag_limit=-1)
