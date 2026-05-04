from __future__ import annotations

import json
from pathlib import Path

from cer_scraper.models import DocumentRecord


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: DocumentRecord) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_json_dict(), ensure_ascii=False) + "\n")

    def seen_document_urls(self) -> set:
        if not self.path.exists():
            return set()

        seen = set()
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                document_url = payload.get("document_url")
                if isinstance(document_url, str):
                    seen.add(document_url)
        return seen
