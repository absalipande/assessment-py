import asyncio
import json
import os
from pathlib import Path
from typing import Union

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveUploader:
    def __init__(
        self,
        folder_id: str,
        credentials_path: Union[str, Path],
    ) -> None:
        self.folder_id = folder_id
        self.credentials_path = Path(credentials_path)
        self._service = None

    async def upload(self, path: Union[str, Path]) -> str:
        path = Path(path)
        return await asyncio.to_thread(self._upload_sync, path)

    def _upload_sync(self, path: Path) -> str:
        service = self._get_service()
        metadata = {"name": path.name, "parents": [self.folder_id]}
        media = MediaFileUpload(str(path), mimetype="application/pdf", resumable=True)

        created = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        return created.get("webViewLink", "")

    def _get_service(self):
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build(
                "drive",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
        return self._service

    def _get_credentials(self):
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Google credentials file not found: {self.credentials_path}")

        with self.credentials_path.open("r", encoding="utf-8") as file:
            credential_data = json.load(file)

        if credential_data.get("type") == "service_account":
            raise ValueError(
                "Google Drive upload is configured with a service account JSON, "
                "but this project must use OAuth Desktop credentials. "
                "Set GOOGLE_SERVICE_ACCOUNT_JSON=credentials/oauth-client.json in .env. "
                f"Current credentials path: {self.credentials_path}"
            )

        print(f"Using OAuth credentials from: {self.credentials_path}")

        token_path = Path(os.getenv("GOOGLE_DRIVE_TOKEN_PATH", "credentials/token.json"))

        if token_path.exists():
            return Credentials.from_authorized_user_file(str(token_path), DRIVE_SCOPES)

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=DRIVE_SCOPES,
        )
        credentials = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

        return credentials
