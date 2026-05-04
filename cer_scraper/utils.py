from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse


def safe_filename(value: str, default: str = "document") -> str:
    value = unquote(value).strip()
    value = re.sub(r"[^\w.\-() ]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or default


def filename_from_url(url: str, fallback: str = "document.pdf") -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.rsplit("/", 1)[-1] if path else fallback
    name = safe_filename(name, fallback)
    return name if "." in Path(name).name else f"{name}.pdf"


def month_folder_name(from_date: str, to_date: str) -> str:
    return f"{from_date}_to_{to_date}"

