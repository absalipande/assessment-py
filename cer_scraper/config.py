from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
    drive_folder_id: Optional[str]


def load_settings() -> Settings:
    load_dotenv()
    root = project_root()

    output_dir = Path(os.getenv("CER_OUTPUT_DIR", "data/downloads"))
    manifest_path = Path(os.getenv("CER_MANIFEST_PATH", "data/manifests/manifest.jsonl"))

    return Settings(
        base_url=os.getenv("CER_BASE_URL", "https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced"),
        headless=os.getenv("CER_HEADLESS", "true").lower() in {"1", "true", "yes"},
        timeout_ms=int(os.getenv("CER_TIMEOUT_MS", "90000")),
        output_dir=output_dir if output_dir.is_absolute() else root / output_dir,
        manifest_path=manifest_path if manifest_path.is_absolute() else root / manifest_path,
        application_types_path=root / "config" / "application_types.txt",
        drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None,
    )


def load_application_types(path: Path) -> List[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
