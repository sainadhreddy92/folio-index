import io
import unittest
from folio import Document
from folio.exchange import RecordError, read_documents, write_documents


class ExchangeTests(unittest.TestCase):
    def test_round_trip(self):
        doc = Document("guides", "a", "Café", "one\ntwo", ("intro",))
        stream = io.StringIO()
        self.assertEqual(write_documents([doc], stream), 1)
        self.assertEqual(list(read_documents(stream.getvalue().splitlines())), [doc])

    def test_invalid_record_location(self):
        with self.assertRaises(RecordError) as caught:
            list(read_documents(["\n", '{"title": 2}']))
        self.assertEqual(caught.exception.line_number, 2)
