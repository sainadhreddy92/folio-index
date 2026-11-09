import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from folio import Catalog, Document
from folio.store import Store


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

    def test_later_source_wins_when_it_finishes_first(self):
        # Both sources describe document "a". The earlier source finishes last,
        # but the later source must still win, exactly as in a serial refresh.
        later_done = threading.Event()

        def load(title):
            if title == "original":
                later_done.wait(timeout=5)
                time.sleep(0.1)
            else:
                later_done.set()
            return Document("docs", "a", title, "")

        # batch_size=1 saves "refund" in its own batch before "original" arrives.
        for batch_size in (1, 100):
            with self.subTest(batch_size=batch_size):
                later_done.clear()
                report = self.catalog.refresh(
                    ["original", "refund"], load, workers=2, batch_size=batch_size
                )
                self.assertEqual((report.processed, report.distinct), (2, 1))
                self.assertEqual(self.catalog.get("docs", "a").title, "refund")

    def test_free_worker_starts_next_source_without_waiting(self):
        # "slow" can only finish once "c" has started. With round-by-round
        # fetching, "c" would wait for "slow", so this would time out.
        c_started = threading.Event()

        def load(key):
            if key == "slow" and not c_started.wait(timeout=2):
                raise TimeoutError("next source never started")
            if key == "c":
                c_started.set()
            return Document("docs", key, key, "")

        report = self.catalog.refresh(["slow", "b", "c"], load, workers=2)
        self.assertEqual((report.processed, report.distinct), (3, 3))

    def test_outstanding_fetches_never_exceed_workers(self):
        # Count every submitted load that has not finished yet, including loads
        # queued inside the pool, which a plain "running" counter cannot see.
        lock = threading.Lock()
        submitted = finished = peak = 0

        class CountingPool(ThreadPoolExecutor):
            def submit(self, fn, /, *args, **kwargs):
                nonlocal submitted, peak
                with lock:
                    submitted += 1
                    peak = max(peak, submitted - finished)
                return super().submit(fn, *args, **kwargs)

        def load(key):
            nonlocal finished
            time.sleep(0.005)
            with lock:
                finished += 1  # happens before the load's result is visible
            return Document("docs", key, key, "")

        with mock.patch("folio.refresh.ThreadPoolExecutor", CountingPool):
            report = self.catalog.refresh([str(n) for n in range(30)], load, workers=3)
        self.assertEqual(report.processed, 30)
        self.assertLessEqual(peak, 3)

    def test_failed_batch_is_discarded_and_earlier_batches_kept(self):
        # Three batches of two. "4" loads fine but is still unsaved when "5",
        # the second load of the third batch, fails, so "4" must be discarded.
        def load(key):
            if key == "5":
                raise OSError("source offline")
            return Document("docs", key, key, "")

        with self.assertRaises(OSError):
            self.catalog.refresh(
                [str(n) for n in range(6)], load, workers=1, batch_size=2
            )
        for key in "0123":
            self.assertIsNotNone(self.catalog.get("docs", key), key)
        for key in "45":
            self.assertIsNone(self.catalog.get("docs", key), key)

    def test_failure_in_first_batch_saves_nothing(self):
        def load(key):
            if key == "b":
                raise OSError("source offline")
            return Document("docs", key, key, "")

        with self.assertRaises(OSError):
            self.catalog.refresh(["a", "b"], load, workers=1)
        self.assertIsNone(self.catalog.get("docs", "a"))

    def test_catalog_not_locked_while_fetching(self):
        # While "b" is loading, batch "a" must already be committed and another
        # connection must be able to write at once, without a long busy wait.
        path = os.path.join(tempfile.mkdtemp(), "catalog.sqlite")
        self.addCleanup(shutil.rmtree, os.path.dirname(path))

        def load(key):
            if key == "b":
                other = sqlite3.connect(path, timeout=0.2)
                try:
                    for _ in range(100):  # wait up to ~1s for batch "a"
                        try:
                            if other.execute(
                                "SELECT 1 FROM documents WHERE key = 'a'"
                            ).fetchone():
                                break
                        except sqlite3.OperationalError:
                            pass
                        time.sleep(0.01)
                    else:
                        raise AssertionError("batch 'a' was not committed")
                    with other:
                        other.execute(
                            "INSERT INTO documents VALUES"
                            " ('docs', 'outside', 'meanwhile', '', '[]')"
                        )
                finally:
                    other.close()
            return Document("docs", key, key, "")

        with Catalog(path) as catalog:
            catalog.refresh(["a", "b"], load, workers=1, batch_size=1)
            self.assertIsNotNone(catalog.get("docs", "outside"))
            self.assertIsNotNone(catalog.get("docs", "b"))

    def test_failure_stops_new_fetches(self):
        started = []

        def load(key):
            started.append(key)
            if key == "1":
                raise OSError("source offline")
            return Document("docs", key, key, "")

        with self.assertRaises(OSError):
            self.catalog.refresh([str(n) for n in range(100)], load, workers=2)
        self.assertLess(len(started), 100)
        self.assertIsNone(self.catalog.get("docs", "0"))

    def test_rejects_non_document(self):
        with self.assertRaises(ValueError):
            self.catalog.refresh(["a"], lambda key: {"key": key}, workers=1)

    def test_rejects_bad_worker_count(self):
        with self.assertRaises(ValueError):
            self.catalog.refresh(["a"], lambda key: None, workers=0)

    def test_sources_failing_midway_keeps_saved_batches(self):
        # The source list itself breaks after four items: batch [0, 1] is
        # saved, and the loaded-but-unsaved [2, 3] is discarded.
        def sources():
            yield from ["0", "1", "2", "3"]
            raise RuntimeError("source list broken")

        def load(key):
            return Document("docs", key, key, "")

        with self.assertRaisesRegex(RuntimeError, "source list broken"):
            self.catalog.refresh(sources(), load, workers=1, batch_size=2)
        for key in "01":
            self.assertIsNotNone(self.catalog.get("docs", key), key)
        for key in "23":
            self.assertIsNone(self.catalog.get("docs", key), key)

    def test_failed_batch_save_rolls_back_whole_batch(self):
        # Saving the second batch fails on its second document. Its first
        # document, already written inside that batch, must be rolled back too.
        real_put = Store.put

        def failing_put(store, doc):
            if doc.key == "3":
                raise sqlite3.OperationalError("disk I/O error")
            real_put(store, doc)

        def load(key):
            return Document("docs", key, key, "")

        with (
            mock.patch.object(Store, "put", failing_put),
            self.assertRaisesRegex(sqlite3.OperationalError, "disk I/O"),
        ):
            self.catalog.refresh(
                [str(n) for n in range(6)], load, workers=1, batch_size=2
            )
        for key in "01":
            self.assertIsNotNone(self.catalog.get("docs", key), key)
        for key in "2345":
            self.assertIsNone(self.catalog.get("docs", key), key)
        self.assertFalse(self.catalog._store.db.in_transaction)

    def test_large_source_list(self):
        # 100,000 sources; each run of 10 neighbouring sources shares one key,
        # and some loads are slowed so later neighbours overtake them. Each key
        # must keep its last source, results must be saved in batches of
        # batch_size, and loads must stay within workers.
        total, per_key, batch_size, workers = 100_000, 10, 500, 8
        keys = total // per_key
        lock = threading.Lock()
        submitted = finished = peak = 0
        commits = 0
        real_transaction = self.catalog.transaction

        def counting_transaction():
            nonlocal commits
            commits += 1
            return real_transaction()

        class CountingPool(ThreadPoolExecutor):
            def submit(self, fn, /, *args, **kwargs):
                nonlocal submitted, peak
                with lock:
                    submitted += 1
                    peak = max(peak, submitted - finished)
                return super().submit(fn, *args, **kwargs)

        def load(n):
            nonlocal finished
            if n % 97 == 0:
                time.sleep(0.001)
            with lock:
                finished += 1
            return Document("docs", f"k{n // per_key}", str(n), "")

        self.catalog.transaction = counting_transaction
        with mock.patch("folio.refresh.ThreadPoolExecutor", CountingPool):
            report = self.catalog.refresh(
                range(total), load, workers=workers, batch_size=batch_size
            )
        self.assertEqual((report.processed, report.distinct), (total, keys))
        self.assertEqual(commits, total // batch_size)
        self.assertLessEqual(peak, workers)
        for k in range(keys):
            self.assertEqual(
                self.catalog.get("docs", f"k{k}").title, str(k * per_key + per_key - 1)
            )

    def test_rejects_open_transaction_before_loading(self):
        started = []

        def load(key):
            started.append(key)
            return Document("docs", key, key, "")

        with self.catalog.transaction(), self.assertRaises(RuntimeError):
            self.catalog.refresh(["a", "b"], load)
        self.assertEqual(started, [])

    def test_rejects_bad_batch_size(self):
        with self.assertRaises(ValueError):
            self.catalog.refresh(["a"], lambda key: None, batch_size=0)


if __name__ == "__main__":
    unittest.main()
