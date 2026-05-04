from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional


DocumentStatus = Literal["discovered", "downloaded", "uploaded", "failed", "skipped"]


@dataclass
class SearchJob:
    from_date: str
    to_date: str
    application_type: str


@dataclass
class DocumentRecord:
    application_type: str
    date_range: str
    result_url: str
    document_url: str
    title: Optional[str] = None
    filing_date: Optional[str] = None
    submitter: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    drive_link: Optional[str] = None
    status: DocumentStatus = "discovered"
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json_dict(self) -> dict:
        return asdict(self)

    @property
    def local_file(self) -> Optional[Path]:
        if not self.local_path:
            return None
        return Path(self.local_path)
