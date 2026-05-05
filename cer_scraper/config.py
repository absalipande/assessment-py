from __future__ import annotations

import os
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "config" / "application_types.txt").exists():
        return cwd
    return PACKAGE_ROOT


@dataclass(frozen=True)
class Settings:
    base_url: str
    headless: bool
    timeout_ms: int
    output_dir: Path
    manifest_path: Path
    application_types_path: Path
    application_type_ids_path: Path
    drive_folder_id: Optional[str]
    google_credentials_path: Optional[Path]


def load_settings() -> Settings:
    load_dotenv()
    root = project_root()

    output_dir = Path(os.getenv("CER_OUTPUT_DIR", "data/downloads"))
    manifest_path = Path(os.getenv("CER_MANIFEST_PATH", "data/manifests/manifest.jsonl"))

    credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    credentials_path = Path(credentials) if credentials else None

    return Settings(
        base_url=os.getenv("CER_BASE_URL", "https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced"),
        headless=os.getenv("CER_HEADLESS", "true").lower() in {"1", "true", "yes"},
        timeout_ms=int(os.getenv("CER_TIMEOUT_MS", "90000")),
        output_dir=output_dir if output_dir.is_absolute() else root / output_dir,
        manifest_path=manifest_path if manifest_path.is_absolute() else root / manifest_path,
        application_types_path=root / "config" / "application_types.txt",
        application_type_ids_path=root / "config" / "application_type_ids.csv",
        drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None,
        google_credentials_path=(
            credentials_path
            if credentials_path is None or credentials_path.is_absolute()
            else root / credentials_path
        ),
    )


def load_application_types(path: Path) -> List[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_application_type_ids(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as file:
        return {row["label"]: row["id"] for row in csv.DictReader(file) if row.get("label") and row.get("id")}
