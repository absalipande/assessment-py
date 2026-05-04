from __future__ import annotations

from pathlib import Path
from typing import Optional


class DriveUploader:
    def __init__(self, folder_id: Optional[str]) -> None:
        self.folder_id = folder_id

    async def upload(self, path: Path) -> Optional[str]:
        if not self.folder_id:
            return None

        raise NotImplementedError(
            "Google Drive upload is not wired yet. Add credentials and implement this method with "
            "google-api-python-client or swap this class for rclone."
        )
