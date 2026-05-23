"""Google Drive へ podcast.mp3 をアップロードする"""

import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import DRIVE_FOLDER_NAME

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_credentials() -> Credentials:
    """環境変数から OAuth2.0 認証情報を構築する"""
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """指定名のフォルダを検索し、なければ作成してフォルダ ID を返す"""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(
        q=query, spaces="drive", fields="files(id, name)", pageSize=1
    ).execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
        print(f"フォルダ '{name}' が見つかりました (ID: {folder_id})")
        return folder_id

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    print(f"フォルダ '{name}' を作成しました (ID: {folder_id})")
    return folder_id


def upload_to_drive(mp3_path: str, version: str, date: str) -> str:
    """podcast.mp3 を Google Drive の Podcasts/{version}_{date}/ にアップロードする"""
    print("Google Drive への認証中...")
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)

    podcasts_id = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
    subfolder_name = f"v{version}_{date}"
    subfolder_id = _get_or_create_folder(service, subfolder_name, parent_id=podcasts_id)

    file_metadata = {
        "name": "podcast.mp3",
        "parents": [subfolder_id],
    }
    media = MediaFileUpload(mp3_path, mimetype="audio/mpeg", resumable=True)

    print(f"podcast.mp3 をアップロード中 → {DRIVE_FOLDER_NAME}/{subfolder_name}/...")
    file = service.files().create(
        body=file_metadata, media_body=media, fields="id, webViewLink"
    ).execute()

    link = file.get("webViewLink", "")
    print(f"アップロード完了: {link}")
    return link
