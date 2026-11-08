"""Streaming JSON Lines interchange for document archives."""
import json
from dataclasses import asdict

from .models import Document


class RecordError(ValueError):
    def __init__(self, line_number, reason):
        self.line_number = line_number
        super().__init__(f"line {line_number}: {reason}")


def read_documents(lines):
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            fields = json.loads(line)
            if not isinstance(fields, dict):
                raise ValueError("expected an object")
            yield Document(**fields)
        except (TypeError, ValueError) as exc:
            raise RecordError(number, str(exc)) from exc


def write_documents(documents, stream):
    count = 0
    for document in documents:
        stream.write(json.dumps(asdict(document), ensure_ascii=False))
        stream.write("\n")
        count += 1
    return count
